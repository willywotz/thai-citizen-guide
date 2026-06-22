"""Characterization tests for chat save behavior BEFORE and AFTER the save_turn refactor.

These pin current observable behavior for unchanged paths (_copy_cached_answer,
_save_stream_conversation) and assert the NEW intended behavior for save_turn.
SQLite-portable: no external HTTP, no Postgres-only SQL.
"""
import uuid

import pytest
from fastapi import BackgroundTasks

from app.models.conversation import Conversation, Message
from app.routers.chat import _copy_cached_answer, _save_stream_conversation


async def _make_conv() -> Conversation:
    return await Conversation.create(title="t", preview="p")


@pytest.mark.usefixtures("db")
async def test_copy_cached_answer_creates_two_messages_and_links_parent():
    """_copy_cached_answer creates a fresh conv (status=success, message_count=2) when conv does not exist."""
    source_conv = await _make_conv()
    user_msg = await Message.create(
        conversation=source_conv,
        role="user",
        content="q",
        category="cat",
    )
    asst_msg = await Message.create(
        conversation=source_conv,
        role="assistant",
        content="a",
        sources=[{"x": 1}],
        parent_id=user_msg.id,
    )

    new_conversation_id = str(uuid.uuid4())
    new_asst = await _copy_cached_answer(
        query="q again",
        conversation_id=new_conversation_id,
        user=None,
        user_msg=user_msg,
        asst_msg=asst_msg,
    )

    assert new_asst.role == "assistant"
    assert new_asst.content == "a"
    assert new_asst.sources == [{"x": 1}]

    conv = await Conversation.get(id=new_conversation_id)
    assert conv.status == "success"       # CURRENT behavior — pinned
    assert conv.message_count == 2        # CURRENT behavior — pinned


@pytest.mark.usefixtures("db")
async def test_save_stream_conversation_success_status_current():
    """_save_stream_conversation creates a fresh conv (status=success, message_count=2) when conv does not exist."""
    cid = str(uuid.uuid4())
    assistant_id = await _save_stream_conversation(
        query="q",
        conversation_id=cid,
        answer_data={"answer": "hello", "sections": []},
        session_id=None,
        total_ms=10,
        latency_ms=5,
        user=None,
        background_tasks=BackgroundTasks(),
    )

    conv = await Conversation.get(id=cid)
    assert conv.status == "success"       # CURRENT behavior — pinned
    assert conv.message_count == 2        # CURRENT behavior — pinned
    assert await Message.filter(conversation_id=cid, role="assistant").count() == 1
    assert str(assistant_id)


# ─── New tests for save_turn (BC #1, #3) ─────────────────────────────────────

@pytest.mark.usefixtures("db")
async def test_save_turn_marks_failed_when_outcome_failed():
    from app.services.chat.turn import save_turn
    cid = str(__import__("uuid").uuid4())
    res = await save_turn(
        query="q", conversation_id=cid, answer="", references=[], category=None,
        agency_ids=[], response_time=0, user=None, succeeded=False,
    )
    conv = await Conversation.get(id=cid)
    assert conv.status == "failed"
    assert res.assistant_message_id


@pytest.mark.usefixtures("db")
async def test_save_turn_is_transactional_message_count():
    from app.services.chat.turn import save_turn
    cid = str(__import__("uuid").uuid4())
    await save_turn(query="q", conversation_id=cid, answer="a", references=[],
                    category=None, agency_ids=[], response_time=1, user=None, succeeded=True)
    conv = await Conversation.get(id=cid)
    assert conv.status == "success"
    assert conv.message_count == 2
