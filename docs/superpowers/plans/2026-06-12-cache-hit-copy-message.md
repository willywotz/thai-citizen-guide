# Per-conversation Copies of Cached Answers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On a chat cache hit, persist a fresh copy of the answer owned by the current conversation (its own message id) so feedback is isolated, and thread the real DB message id through the SSE stream so streamed answers can be rated.

**Architecture:** Add a backend helper `_copy_cached_answer` used by the `/chat/internal` and `/chat/external` cache branches to create a new Conversation + user Message + assistant Message (no embedding, no ConnectionLog → copies never re-enter the cache). For streaming, `_save_stream_conversation` returns the new assistant id, emitted to the client in the `done` SSE event; the frontend stores it and uses it as the message id.

**Tech Stack:** Python 3.12 / FastAPI / Tortoise ORM (SQLite in tests) on the backend; TypeScript / React / Vitest on the frontend.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `backend/app/routers/chat.py` | New `_copy_cached_answer` helper; rewritten `/internal` + `/external` cache branches; `_save_stream_conversation` returns id; `event_generator` defers `done`; `cached_stream` adds `message_id`. |
| `backend/tests/routers/test_chat_cache.py` | New — cache-hit copy behavior for `/external` and `/internal`. |
| `backend/tests/routers/test_chat_stream_message_id.py` | New — streaming returns/emits the DB message id. |
| `frontend/src/shared/types/chat.ts` | `DoneEvent.message_id`, `StreamingState.messageId`. |
| `frontend/src/features/chat/chatHelpers.ts` | `INITIAL_STREAMING_STATE.messageId`; `applyDoneEvent` captures id; `buildAiMessageFromState` uses it. |
| `frontend/src/features/chat/chatHelpers.test.ts` | New cases for the above. |

---

## Task 1: Backend — `_copy_cached_answer` + `/external` cache branch

**Files:**
- Create: `backend/tests/routers/test_chat_cache.py`
- Modify: `backend/app/routers/chat.py` (add helper; rewrite cache branch at chat.py:160-176)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/routers/test_chat_cache.py`:

```python
"""Cache-hit must copy the answer into a fresh per-conversation message.

On a cache hit the endpoint previously returned the ORIGINAL message id and
conversation, so rating the answer overwrote the original message's feedback.
These tests pin the fix: a hit creates new records and leaves the original
untouched. They run against the in-memory SQLite `db` fixture.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks

from app.models.connection_log import ConnectionLog
from app.models.conversation import Conversation, Message
from app.routers import chat as chat_router
from app.routers import messages as messages_router
from app.schemas.chat import ChatRequest
from app.schemas.conversation import RatingUpdate


async def _origin_answer():
    conv = await Conversation.create(status="success")
    user_msg = await Message.create(conversation=conv, role="user", content="คำถามเดิม")
    asst_msg = await Message.create(
        parent_id=user_msg.id,
        conversation=conv,
        role="assistant",
        content="คำตอบที่แคชไว้",
        sources=[{"title": "src"}],
        agency_ids=["a1"],
    )
    return conv, user_msg, asst_msg


@pytest.mark.asyncio
async def test_external_cache_hit_copies_into_new_conversation(db):
    conv, user_msg, asst_msg = await _origin_answer()

    with patch.object(chat_router, "generate_embedding", new=AsyncMock(return_value=[0.1])), \
         patch.object(chat_router, "find_similar_question",
                      new=AsyncMock(return_value=(user_msg, asst_msg, MagicMock()))):
        res = await chat_router.chat_external(ChatRequest(query="คำถามใหม่"), BackgroundTasks(), None)

    data = res["data"]
    assert data["cached"] is True
    assert data["message_id"] != asst_msg.id
    assert res["conversation_id"] != str(conv.id)

    new = await Message.get(id=data["message_id"])
    assert new.role == "assistant"
    assert new.content == asst_msg.content
    assert new.sources == asst_msg.sources
    assert new.agency_ids == asst_msg.agency_ids
    assert str(new.conversation_id) == res["conversation_id"]
    assert new.parent_id is not None
    # copies are not cache sources
    assert new.embedding is None
    assert await ConnectionLog.filter(assistant_message_id=new.id).count() == 0


@pytest.mark.asyncio
async def test_external_cache_hit_rating_does_not_touch_origin(db):
    conv, user_msg, asst_msg = await _origin_answer()

    with patch.object(chat_router, "generate_embedding", new=AsyncMock(return_value=[0.1])), \
         patch.object(chat_router, "find_similar_question",
                      new=AsyncMock(return_value=(user_msg, asst_msg, MagicMock()))):
        res = await chat_router.chat_external(ChatRequest(query="คำถามใหม่"), BackgroundTasks(), None)

    new_id = uuid.UUID(str(res["data"]["message_id"]))
    await messages_router.update_rating(message_id=new_id, body=RatingUpdate(rating="down"))

    assert (await Message.get(id=new_id)).rating == "down"
    assert (await Message.get(id=asst_msg.id)).rating is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/routers/test_chat_cache.py -v`
Expected: FAIL — `chat_external` returns the original `asst_msg.id` (so `message_id != asst_msg.id` and `conversation_id != str(conv.id)` assertions fail; `Message.get(id=data["message_id"])` returns the original, and rating the original sets `asst_msg.rating`).

- [ ] **Step 3: Add the `_copy_cached_answer` helper**

In `backend/app/routers/chat.py`, add this helper in the HTTP-helpers section (e.g. directly above `_save_stream_conversation`):

```python
async def _copy_cached_answer(
    *,
    query: str,
    conversation_id: str,
    user: User | None,
    user_msg: Message,
    asst_msg: Message,
) -> Message:
    """Copy a cached answer into a fresh message owned by `conversation_id`.

    Copies are intentionally NOT cache sources: no embedding is stored and no
    ConnectionLog is created, so neither vector search (filters on
    embedding IS NOT NULL) nor the text fallback (requires a ConnectionLog in
    find_similar_question) will ever resurface a copy.
    """
    try:
        conv = await Conversation.get(id=conversation_id)
        conv.message_count += 2  # 1 user + 1 assistant message per turn
        conv.updated_at = now()
        await conv.save()
    except DoesNotExist:
        await Conversation.create(
            id=conversation_id,
            title=query[:settings.TITLE_MAX_LENGTH],
            preview=query[:settings.PREVIEW_MAX_LENGTH],
            agencies=[],
            status="success",
            message_count=2,  # 1 user + 1 assistant message per turn
            response_time=0,
            user_id=user.id if user else None,
        )

    new_user_msg = await Message.create(
        conversation_id=conversation_id,
        role="user",
        content=query,
        category=user_msg.category,
    )
    return await Message.create(
        parent_id=new_user_msg.id,
        conversation_id=conversation_id,
        role="assistant",
        content=asst_msg.content,
        sources=asst_msg.sources,
        agent_steps=asst_msg.agent_steps,
        agency_ids=asst_msg.agency_ids,
        response_time=0,
    )
```

- [ ] **Step 4: Rewrite the `/external` cache branch**

In `backend/app/routers/chat.py`, replace the existing cache branch (chat.py:160-176):

```python
            if cached:
                user_msg, asst_msg, _ = cached
                span.set_attribute("cache_hit", True)
                return {
                    "success": True,
                    "data": {
                        "message_id": asst_msg.id,
                        "answer": asst_msg.content,
                        "references": asst_msg.sources if asst_msg.sources else [],
                        "agentSteps": asst_msg.agent_steps if asst_msg.agent_steps else [],
                        "agencies": [],
                        "confidence": settings.SIMILARITY_THRESHOLD,
                        "cached": True,
                    },
                    "conversation_id": str(user_msg.conversation_id),
                    "responseTime": 0,
                }
```

with:

```python
            if cached:
                user_msg, asst_msg, _ = cached
                span.set_attribute("cache_hit", True)
                new_asst_msg = await _copy_cached_answer(
                    query=query,
                    conversation_id=conversation_id,
                    user=user,
                    user_msg=user_msg,
                    asst_msg=asst_msg,
                )
                return {
                    "success": True,
                    "data": {
                        "message_id": new_asst_msg.id,
                        "answer": asst_msg.content,
                        "references": asst_msg.sources if asst_msg.sources else [],
                        "agentSteps": asst_msg.agent_steps if asst_msg.agent_steps else [],
                        "agencies": [],
                        "confidence": settings.SIMILARITY_THRESHOLD,
                        "cached": True,
                    },
                    "conversation_id": conversation_id,
                    "responseTime": 0,
                }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/routers/test_chat_cache.py -v`
Expected: PASS (both tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/chat.py backend/tests/routers/test_chat_cache.py
git commit -m "fix(chat): copy cached answer into a new conversation on /external cache hit"
```

---

## Task 2: Backend — `/internal` cache branch

**Files:**
- Modify: `backend/app/routers/chat.py` (rewrite cache branch at chat.py:55-70)
- Modify: `backend/tests/routers/test_chat_cache.py` (add `/internal` case)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/routers/test_chat_cache.py`:

```python
@pytest.mark.asyncio
async def test_internal_cache_hit_copies_into_new_conversation(db):
    conv, user_msg, asst_msg = await _origin_answer()

    with patch.object(chat_router, "generate_embedding", new=AsyncMock(return_value=[0.1])), \
         patch.object(chat_router, "find_similar_question",
                      new=AsyncMock(return_value=(user_msg, asst_msg, MagicMock()))):
        res = await chat_router.chat_internal(ChatRequest(query="คำถามใหม่"), None)

    data = res["data"]
    assert data["cached"] is True
    assert data["message_id"] != asst_msg.id
    assert res["conversation_id"] != str(conv.id)

    new = await Message.get(id=data["message_id"])
    assert new.content == asst_msg.content
    assert new.parent_id is not None
    assert (await Message.get(id=asst_msg.id)).rating is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/routers/test_chat_cache.py::test_internal_cache_hit_copies_into_new_conversation -v`
Expected: FAIL — `chat_internal` returns the original `asst_msg.id` and `str(user_msg.conversation_id)`.

- [ ] **Step 3: Rewrite the `/internal` cache branch**

In `backend/app/routers/chat.py`, replace the existing cache branch (chat.py:55-70):

```python
    cached = await find_similar_question(query=query, embedding=embedding)
    if cached:
        user_msg, asst_msg, _ = cached
        return {
            "success": True,
            "data": {
                "message_id": asst_msg.id,
                "answer": asst_msg.content,
                "references": asst_msg.sources if asst_msg.sources else [],
                "agentSteps": asst_msg.agent_steps if asst_msg.agent_steps else [],
                "agencies": [],
                "confidence": settings.SIMILARITY_THRESHOLD,
                "cached": True,
            },
            "conversation_id": str(user_msg.conversation_id),
            "responseTime": 0,
        }
```

with:

```python
    cached = await find_similar_question(query=query, embedding=embedding)
    if cached:
        user_msg, asst_msg, _ = cached
        conversation_id = body.conversation_id or str(generate_uuid())
        new_asst_msg = await _copy_cached_answer(
            query=query,
            conversation_id=conversation_id,
            user=user,
            user_msg=user_msg,
            asst_msg=asst_msg,
        )
        return {
            "success": True,
            "data": {
                "message_id": new_asst_msg.id,
                "answer": asst_msg.content,
                "references": asst_msg.sources if asst_msg.sources else [],
                "agentSteps": asst_msg.agent_steps if asst_msg.agent_steps else [],
                "agencies": [],
                "confidence": settings.SIMILARITY_THRESHOLD,
                "cached": True,
            },
            "conversation_id": conversation_id,
            "responseTime": 0,
        }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/routers/test_chat_cache.py -v`
Expected: PASS (all three tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/chat.py backend/tests/routers/test_chat_cache.py
git commit -m "fix(chat): copy cached answer into a new conversation on /internal cache hit"
```

---

## Task 3: Backend — streaming returns & emits the DB message id

**Files:**
- Create: `backend/tests/routers/test_chat_stream_message_id.py`
- Modify: `backend/app/routers/chat.py` (`_save_stream_conversation` return; `cached_stream` done payload; `event_generator` deferred done)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/routers/test_chat_stream_message_id.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/routers/test_chat_stream_message_id.py -v`
Expected: FAIL — `_save_stream_conversation` returns `None` (so `Message.get(id=None)` raises), and the cached `done` event does not contain the new message id.

- [ ] **Step 3: Make `_save_stream_conversation` return the assistant id**

In `backend/app/routers/chat.py`, change the signature return annotation from `-> None:` to `-> Any:` and add a return at the end. The final lines of the function become:

```python
    background_tasks.add_task(classify_message_category, str(query_msg.id), query, answer)
    background_tasks.add_task(store_embedding, str(query_msg.id), query)

    return assistant_msg.id
```

- [ ] **Step 4: Emit `message_id` in the cached stream's `done` event**

In `cached_stream` (chat.py:299-310), capture the returned id and add it to the `done` payload:

```python
                    assistant_id = await _save_stream_conversation(
                        query=query,
                        conversation_id=conversation_id,
                        answer_data=answer_data,
                        session_id=None,
                        total_ms=0,
                        latency_ms=0,
                        user=user,
                        background_tasks=background_tasks,
                    )
                    yield _sse_event("answer", {"answer": asst_msg.content})
                    yield _sse_event("done", {"session_id": conversation_id, "total_ms": 0, "message_id": str(assistant_id)})
```

- [ ] **Step 5: Defer the non-cached `done` event until after save**

In `event_generator`, add `done_event_data = None` to the initial variables (alongside `answer_data = None`):

```python
            answer_data = None
            session_id = None
            total_ms = None
            done_event_data = None
            start_ns = time.perf_counter_ns()
            log_latency_ms = 0
```

Replace the event-dispatch block (chat.py:358-369):

```python
                                if event_name == "answer":
                                    answer_data = event_data
                                elif event_name == "done":
                                    session_id = event_data.get("session_id")
                                    total_ms = event_data.get("total_ms")
                                with tracer.start_as_current_span("event") as event_span:
                                    event_span.set_attribute("stream_event", event_name)
                                    event_span.set_attribute("event_data", json.dumps(event_data)[:500])
                                if event_name == "done":
                                    yield _sse_event(event_name, {**event_data, "session_id": conversation_id})
                                else:
                                    yield _sse_event(event_name, event_data)
```

with (capture `done`, don't yield it inline):

```python
                                if event_name == "answer":
                                    answer_data = event_data
                                elif event_name == "done":
                                    session_id = event_data.get("session_id")
                                    total_ms = event_data.get("total_ms")
                                    done_event_data = event_data
                                with tracer.start_as_current_span("event") as event_span:
                                    event_span.set_attribute("stream_event", event_name)
                                    event_span.set_attribute("event_data", json.dumps(event_data)[:500])
                                if event_name != "done":
                                    yield _sse_event(event_name, event_data)
```

Replace the post-loop save block (chat.py:382-392):

```python
            if answer_data:
                await _save_stream_conversation(
                    query=query,
                    conversation_id=conversation_id,
                    answer_data=answer_data,
                    session_id=session_id,
                    total_ms=total_ms,
                    latency_ms=log_latency_ms,
                    user=user,
                    background_tasks=background_tasks,
                )
```

with (save, then emit the deferred `done` with the id):

```python
            if answer_data:
                assistant_id = await _save_stream_conversation(
                    query=query,
                    conversation_id=conversation_id,
                    answer_data=answer_data,
                    session_id=session_id,
                    total_ms=total_ms,
                    latency_ms=log_latency_ms,
                    user=user,
                    background_tasks=background_tasks,
                )
                yield _sse_event("done", {**(done_event_data or {}), "session_id": conversation_id, "message_id": str(assistant_id)})
            elif done_event_data is not None:
                yield _sse_event("done", {**done_event_data, "session_id": conversation_id})
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/routers/test_chat_stream_message_id.py -v`
Expected: PASS (both tests).

- [ ] **Step 7: Run the full backend chat test set (no regressions)**

Run: `cd backend && uv run pytest tests/routers/test_chat_cache.py tests/routers/test_chat_stream_message_id.py tests/services/test_similarity.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/chat.py backend/tests/routers/test_chat_stream_message_id.py
git commit -m "fix(chat): expose DB assistant message id in stream done event"
```

---

## Task 4: Frontend — store and use the streamed message id

**Files:**
- Modify: `frontend/src/shared/types/chat.ts` (DoneEvent + StreamingState)
- Modify: `frontend/src/features/chat/chatHelpers.ts` (INITIAL_STREAMING_STATE, applyDoneEvent, buildAiMessageFromState)
- Modify: `frontend/src/features/chat/chatHelpers.test.ts`

- [ ] **Step 1: Write the failing tests**

In `frontend/src/features/chat/chatHelpers.test.ts`, add a case to the existing `applyDoneEvent` describe block (after the test at line 327):

```ts
  it('stores message_id when the done event includes it', () => {
    const next = applyDoneEvent(baseState(), { session_id: 'sess-1', total_ms: 1, message_id: 'db-msg-1' });
    expect(next.messageId).toBe('db-msg-1');
  });
```

And add a case to the existing `buildAiMessageFromState` describe block (after the test at line 382):

```ts
  it('uses the DB messageId as the message id when present', () => {
    const state = applyAnswerEvent(
      applyDoneEvent(baseState(), { session_id: 'sess-1', total_ms: 1, message_id: 'db-msg-1' }),
      { answer: 'hi', sections: [], errors: [], debug: null },
    );
    const msg = buildAiMessageFromState(state);
    expect(msg!.id).toBe('db-msg-1');
  });
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/features/chat/chatHelpers.test.ts`
Expected: FAIL — `message_id` is not a valid `DoneEvent` field (type error / undefined), `next.messageId` is undefined, and `buildAiMessageFromState` returns a generated id.

- [ ] **Step 3: Extend the types**

In `frontend/src/shared/types/chat.ts`, update `DoneEvent` (chat.ts:96-99):

```ts
export interface DoneEvent {
  session_id: string;
  total_ms: number;
  message_id?: string;
}
```

And add `messageId` to `StreamingState` (inside the interface at chat.ts:123-136, next to `sessionId`):

```ts
  sessionId: string | null;
  messageId: string | null;
  totalMs: number | null;
  done: boolean;
```

- [ ] **Step 4: Update the initial state and helpers**

In `frontend/src/features/chat/chatHelpers.ts`, add `messageId: null` to `INITIAL_STREAMING_STATE` (next to `sessionId: null`):

```ts
  sessionId: null,
  messageId: null,
  totalMs: null,
  done: false,
};
```

Update `applyDoneEvent` (chatHelpers.ts:190-192):

```ts
export function applyDoneEvent(prev: StreamingState, event: DoneEvent): StreamingState {
  return { ...prev, sessionId: event.session_id, totalMs: event.total_ms, messageId: event.message_id ?? prev.messageId, done: true };
}
```

Update the `id` line in `buildAiMessageFromState` (chatHelpers.ts:77):

```ts
    id: state.messageId ?? generateUniqueId(),
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/features/chat/chatHelpers.test.ts`
Expected: PASS (existing cases plus the two new ones).

- [ ] **Step 6: Type-check & lint**

Run: `cd frontend && npx tsc --noEmit && npx eslint src/features/chat/chatHelpers.ts src/shared/types/chat.ts`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/shared/types/chat.ts frontend/src/features/chat/chatHelpers.ts frontend/src/features/chat/chatHelpers.test.ts
git commit -m "fix(chat): use DB message id from stream done event for feedback"
```

---

## Notes for the implementer

- The JSON fallback path in `useChat.ts` (line 234) already reads `response.data.message_id`; Tasks 1–2 make that the new copy's id automatically — no `useChat.ts` change is needed.
- `now`, `DoesNotExist`, `generate_uuid`, `settings`, `User`, `Conversation`, `Message` are all already imported in `chat.py`.
- Copies deliberately store no embedding and create no `ConnectionLog`, which is what keeps them out of `find_similar_question` results — do not "helpfully" add either.
