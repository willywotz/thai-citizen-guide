# Multi-Turn Cache Bypass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bypass the similarity cache for turn 2+ messages and ensure OneChat has session context by replaying turn 1 if it was served from cache.

**Architecture:** A new `ensure_session_warmed()` service function checks whether the conversation's `external_session_id` is set (meaning OneChat has already seen turn 1). If not, it fetches the first user message from DB, POSTs it to OneChat v3, and stores the returned session ID. Both `chat_external` and `chat_stream` call this before their OneChat call on turn 2+, and skip the cache check entirely on turn 2+.

**Tech Stack:** Python 3.12, FastAPI, Tortoise ORM, httpx, pytest, pytest-asyncio

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/services/session.py` | Create | `ensure_session_warmed()` — lazy session warm-up |
| `backend/app/routers/chat.py` | Modify | Gate cache on turn 1; call warm-up on turn 2+ in `chat_external` and `chat_stream` |
| `backend/tests/__init__.py` | Create | Make tests a package |
| `backend/tests/services/__init__.py` | Create | Make services test sub-package |
| `backend/tests/services/test_session.py` | Create | Unit tests for `ensure_session_warmed()` |

---

### Task 1: Create `ensure_session_warmed()` with failing tests

**Files:**
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/services/__init__.py`
- Create: `backend/tests/services/test_session.py`
- Create: `backend/app/services/session.py`

- [ ] **Step 1: Create test package files**

```bash
touch /path/to/backend/tests/__init__.py
touch /path/to/backend/tests/services/__init__.py
```

(Replace `/path/to/backend` with the actual path.)

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/services/test_session.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.fixture
def mock_conversation():
    conv = MagicMock()
    conv.id = "conv-123"
    conv.external_session_id = None
    conv.save = AsyncMock()
    return conv


@pytest.fixture
def mock_first_message():
    msg = MagicMock()
    msg.content = "What documents do I need?"
    return msg


@pytest.mark.asyncio
async def test_no_op_when_session_already_warmed(mock_conversation):
    """If external_session_id is set, function returns immediately without DB or HTTP calls."""
    mock_conversation.external_session_id = "existing-session"

    with patch("app.services.session.Message") as MockMessage:
        from app.services.session import ensure_session_warmed
        await ensure_session_warmed(mock_conversation, "http://onechat/v3", "http://mcp/")

    MockMessage.filter.assert_not_called()
    mock_conversation.save.assert_not_called()


@pytest.mark.asyncio
async def test_no_op_when_no_first_message(mock_conversation):
    """If conversation has no user messages, function returns without calling OneChat."""
    mock_qs = MagicMock()
    mock_qs.order_by = MagicMock(return_value=MagicMock(first=AsyncMock(return_value=None)))

    with patch("app.services.session.Message") as MockMessage:
        MockMessage.filter.return_value = mock_qs
        from app.services.session import ensure_session_warmed
        await ensure_session_warmed(mock_conversation, "http://onechat/v3", "http://mcp/")

    mock_conversation.save.assert_not_called()


@pytest.mark.asyncio
async def test_warms_session_and_stores_session_id(mock_conversation, mock_first_message):
    """Replays first message to OneChat, stores returned session_id on conversation."""
    mock_qs = MagicMock()
    mock_qs.order_by = MagicMock(
        return_value=MagicMock(first=AsyncMock(return_value=mock_first_message))
    )

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": {"session_id": "warmed-session-abc"}}

    with patch("app.services.session.Message") as MockMessage, \
         patch("app.services.session.httpx.AsyncClient") as MockClient:

        MockMessage.filter.return_value = mock_qs
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.services.session import ensure_session_warmed
        await ensure_session_warmed(mock_conversation, "http://onechat/v3", "http://mcp/")

    mock_client_instance.post.assert_called_once_with(
        "http://onechat/v3",
        json={
            "query": "What documents do I need?",
            "mcp_endpoint_url": "http://mcp/",
            "session_id": "conv-123",
        },
    )
    assert mock_conversation.external_session_id == "warmed-session-abc"
    mock_conversation.save.assert_called_once_with(update_fields=["external_session_id"])


@pytest.mark.asyncio
async def test_falls_back_to_conversation_id_when_no_session_in_response(mock_conversation, mock_first_message):
    """If OneChat response has no session_id, falls back to conversation.id."""
    mock_qs = MagicMock()
    mock_qs.order_by = MagicMock(
        return_value=MagicMock(first=AsyncMock(return_value=mock_first_message))
    )

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": {}}

    with patch("app.services.session.Message") as MockMessage, \
         patch("app.services.session.httpx.AsyncClient") as MockClient:

        MockMessage.filter.return_value = mock_qs
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.services.session import ensure_session_warmed
        await ensure_session_warmed(mock_conversation, "http://onechat/v3", "http://mcp/")

    assert mock_conversation.external_session_id == "conv-123"
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd backend && python -m pytest tests/services/test_session.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services.session'`

- [ ] **Step 4: Create `backend/app/services/session.py`**

```python
import httpx

from app.models.conversation import Conversation, Message


async def ensure_session_warmed(
    conversation: Conversation,
    onechat_url: str,
    mcp_endpoint_url: str,
) -> None:
    if conversation.external_session_id is not None:
        return

    first_msg = await Message.filter(
        conversation_id=conversation.id,
        role="user",
    ).order_by("created_at").first()

    if first_msg is None:
        return

    payload = {
        "query": first_msg.content,
        "mcp_endpoint_url": mcp_endpoint_url,
        "session_id": str(conversation.id),
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(onechat_url, json=payload)
        resp.raise_for_status()

    data = resp.json().get("data", {})
    conversation.external_session_id = data.get("session_id") or str(conversation.id)
    await conversation.save(update_fields=["external_session_id"])
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
cd backend && python -m pytest tests/services/test_session.py -v
```

Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
rtk git add backend/app/services/session.py backend/tests/__init__.py backend/tests/services/__init__.py backend/tests/services/test_session.py
rtk git commit -m "feat: add ensure_session_warmed service for multi-turn context"
```

---

### Task 2: Gate cache on turn 1 in `chat_external`, add warm-up on turn 2+

**Files:**
- Modify: `backend/app/routers/chat.py:489-522`

The key detection: `body.conversation_id is None` → turn 1 (new conversation). `body.conversation_id` is set → turn 2+.

- [ ] **Step 1: Locate the cache block in `chat_external`**

Open `backend/app/routers/chat.py`. The cache check is at lines 503–522:

```python
# Check for similar question in cache
embedding = await generate_embedding(query)
cached = await find_similar_question(query=query, embedding=embedding)
if cached:
    user_msg, asst_msg = cached
    span.set_attribute("cache_hit", True)
    return {
        ...
        "cached": True,
        ...
    }
```

- [ ] **Step 2: Add import for `ensure_session_warmed`**

At line 37 (alongside other service imports), add:

```python
from app.services.session import ensure_session_warmed
```

- [ ] **Step 3: Replace the cache block with turn-gated version**

Replace lines 503–522 (the cache block) with:

```python
        # Cache applies only on turn 1 (new conversation)
        if not body.conversation_id:
            embedding = await generate_embedding(query)
            cached = await find_similar_question(query=query, embedding=embedding)
            if cached:
                user_msg, asst_msg = cached
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
        else:
            # Turn 2+: ensure OneChat has session context from turn 1
            await ensure_session_warmed(conv, settings.ONECHAT_V3_URL, settings.MCP_ENDPOINT_URL)
```

- [ ] **Step 4: Confirm the file is syntactically valid**

```bash
cd backend && python -c "import app.routers.chat"
```

Expected: no output (no errors)

- [ ] **Step 5: Commit**

```bash
rtk git add backend/app/routers/chat.py
rtk git commit -m "feat: bypass cache on turn 2+ and warm session in chat_external"
```

---

### Task 3: Gate cache on turn 1 in `chat_stream`, add warm-up on turn 2+

**Files:**
- Modify: `backend/app/routers/chat.py:618-644`

- [ ] **Step 1: Locate the cache block in `chat_stream`**

Open `backend/app/routers/chat.py`. The cache check is at lines 627–636:

```python
    # Check for similar question in cache
    embedding = await generate_embedding(query)
    cached = await find_similar_question(query=query, embedding=embedding)
    if cached:
        user_msg, asst_msg = cached
        async def cached_stream():
            await asyncio.sleep(0.01)
            yield _sse_event("answer", {"answer": asst_msg.content})
            yield _sse_event("done", {"session_id": conversation_id, "total_ms": 0})
        return StreamingResponse(cached_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

And lines 638–642 (existing conv load, inside a bare try/except):

```python
    if body.conversation_id:
        try:
            await Conversation.get(id=conversation_id)
        except Exception:
            pass
```

- [ ] **Step 2: Replace both blocks**

Replace lines 627–642 with:

```python
    # Cache applies only on turn 1 (new conversation)
    if not body.conversation_id:
        embedding = await generate_embedding(query)
        cached = await find_similar_question(query=query, embedding=embedding)
        if cached:
            user_msg, asst_msg = cached
            async def cached_stream():
                await asyncio.sleep(0.01)
                yield _sse_event("answer", {"answer": asst_msg.content})
                yield _sse_event("done", {"session_id": conversation_id, "total_ms": 0})
            return StreamingResponse(cached_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    else:
        # Turn 2+: ensure OneChat has session context from turn 1
        conv = await Conversation.get(id=conversation_id)
        await ensure_session_warmed(conv, settings.ONECHAT_V3_URL, settings.MCP_ENDPOINT_URL)
```

- [ ] **Step 3: Confirm the file is syntactically valid**

```bash
cd backend && python -c "import app.routers.chat"
```

Expected: no output (no errors)

- [ ] **Step 4: Commit**

```bash
rtk git add backend/app/routers/chat.py
rtk git commit -m "feat: bypass cache on turn 2+ and warm session in chat_stream"
```

---

### Task 4: Smoke test end-to-end

- [ ] **Step 1: Run the full test suite**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 2: Start the dev server and verify manually**

```bash
cd backend && uvicorn app.main:app --reload
```

Scenarios to verify with a REST client (curl / Postman / Bruno):

1. **Turn 1 (new conversation, cache miss)** — POST `/api/v1/chat` with `{"query": "unique question xyz"}`, no `conversation_id`. Should call OneChat, return answer, set `external_session_id` in DB.

2. **Turn 1 (new conversation, cache hit)** — POST same or similar query again. Should return `"cached": true`, no OneChat call.

3. **Turn 2 after cache hit** — Take the `conversation_id` from step 2's response. POST `/api/v1/chat` with that `conversation_id` and a follow-up query. Should warm session (replay turn 1 to OneChat), then send turn 2 to OneChat, return real answer.

4. **Turn 2 after cache miss** — Take `conversation_id` from step 1. POST follow-up. Should skip warm-up (session already set), call OneChat directly, return answer.

5. **Same scenarios via `/api/v1/chat/stream`** — Verify SSE events come through correctly.

- [ ] **Step 3: Final commit if any fixes were needed**

```bash
rtk git add -p
rtk git commit -m "fix: <describe what was fixed during smoke test>"
```
