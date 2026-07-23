"""Postgres-backed reproduction of the similarity-cache *window* ("cache time").

The rest of the suite runs on in-memory SQLite, which cannot execute the
pg_trgm SQL that `find_similar_question` relies on. These tests connect to a
real Postgres (set TEST_PG_URL) and drive the actual pg_trgm text path.

Skipped automatically when TEST_PG_URL is unset.
"""

import os
from datetime import timedelta

import pytest_asyncio
import pytest
from tortoise import Tortoise

from app.config import settings
from app.models.connection_log import ConnectionLog
from app.models.conversation import Conversation, Message
from app.services.similarity import find_similar_question
from app.utils import now

PG_URL = os.environ.get("TEST_PG_URL")

pytestmark = pytest.mark.skipif(
    not PG_URL, reason="TEST_PG_URL not set; Postgres-backed window test skipped"
)

QUESTION = "ขอหนังสือเดินทางต้องใช้เอกสารอะไรบ้าง"
ANSWER = "ต้องใช้บัตรประชาชนและรูปถ่าย"


@pytest_asyncio.fixture(scope="function")
async def pg_db():
    await Tortoise.init(db_url=PG_URL, modules={"models": ["app.models"]})
    await Tortoise.generate_schemas(safe=True)
    conn = Tortoise.get_connection("default")
    await conn.execute_query(
        "TRUNCATE messages, connection_logs, conversations, settings CASCADE"
    )
    try:
        yield conn
    finally:
        await conn.execute_query(
            "TRUNCATE messages, connection_logs, conversations, settings CASCADE"
        )
        await Tortoise.close_connections()


async def _seed_cached_answer(conn, *, age: timedelta) -> None:
    """Create a success conversation with a cached Q/A whose question is `age` old."""
    conv = await Conversation.create(status="success")
    user_msg = await Message.create(conversation=conv, role="user", content=QUESTION)
    asst_msg = await Message.create(
        parent_id=user_msg.id, conversation=conv, role="assistant", content=ANSWER
    )
    await ConnectionLog.create(
        action="query",
        connection_type="external_chat",
        status="success",
        message_id=user_msg.id,
        assistant_message_id=asst_msg.id,
        response_body="{}",
    )
    # auto_now_add ignores any created_at passed to create(); backdate via raw SQL.
    await conn.execute_query(
        "UPDATE messages SET created_at = $1 WHERE id = $2",
        [now() - age, str(user_msg.id)],
    )


async def test_in_window_question_is_cached(pg_db):
    """Control: a recent identical question must be served from cache."""
    await _seed_cached_answer(pg_db, age=timedelta(minutes=1))

    result = await find_similar_question(QUESTION)

    assert result is not None, "recent identical question should hit the cache"
    _, asst_msg, _ = result
    assert asst_msg.content == ANSWER


async def test_out_of_window_question_is_not_cached(pg_db):
    """A question older than SIMILARITY_WINDOW_SECONDS must NOT be served."""
    age = timedelta(seconds=settings.SIMILARITY_WINDOW_SECONDS) + timedelta(days=1)
    await _seed_cached_answer(pg_db, age=age)

    result = await find_similar_question(QUESTION)

    assert result is None, (
        "question older than the cache window was still served from cache — "
        "the window ('cache time') is not being respected"
    )
