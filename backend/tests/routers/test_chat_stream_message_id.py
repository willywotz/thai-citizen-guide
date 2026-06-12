"""Streaming must expose the real DB assistant message id for feedback.

`_save_stream_conversation` returns the new assistant id, and the `done` SSE
event carries it as `message_id`, so a streamed answer can be rated against a
real row instead of a client-generated id.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks

from app.models.conversation import Conversation, Message
from app.routers import chat as chat_router
from app.schemas.chat import ChatRequest


@pytest.mark.asyncio
async def test_save_stream_conversation_returns_assistant_id(db):
    conv_id = str(__import__("uuid").uuid4())
    asst_id = await chat_router._save_stream_conversation(
        query="q",
        conversation_id=conv_id,
        answer_data={"answer": "คำตอบ", "errors": [], "sections": []},
        session_id=None,
        total_ms=0,
        latency_ms=0,
        user=None,
        background_tasks=BackgroundTasks(),
    )
    saved = await Message.get(id=asst_id)
    assert saved.role == "assistant"
    assert saved.content == "คำตอบ"


@pytest.mark.asyncio
async def test_cached_stream_emits_message_id_in_done(db):
    conv = await Conversation.create(status="success")
    user_msg = await Message.create(conversation=conv, role="user", content="q")
    asst_msg = await Message.create(
        parent_id=user_msg.id, conversation=conv, role="assistant", content="cached answer"
    )
    conn_log = MagicMock(response_body=json.dumps({"answer": "cached answer"}))

    with patch.object(chat_router, "generate_embedding", new=AsyncMock(return_value=[0.1])), \
         patch.object(chat_router, "find_similar_question",
                      new=AsyncMock(return_value=(user_msg, asst_msg, conn_log))):
        resp = await chat_router.chat_stream(ChatRequest(query="q"), MagicMock(), BackgroundTasks(), None)
        chunks = [c async for c in resp.body_iterator]

    text = "".join(c if isinstance(c, str) else c.decode() for c in chunks)
    new_asst = await Message.filter(role="assistant").exclude(id=asst_msg.id).first()
    assert new_asst is not None
    assert "event: done" in text
    assert str(new_asst.id) in text
