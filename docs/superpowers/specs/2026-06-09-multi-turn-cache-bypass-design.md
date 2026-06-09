# Multi-Turn Cache Bypass with Session Warm-Up

## Problem

`chat_external` and `chat_stream` both use a vector similarity cache. The cache searches across all conversations, so a multi-turn user on turn 2+ can receive a cached answer from a different user's conversation — one that has no awareness of the current conversation's context. This breaks multi-turn coherence.

Additionally, when turn 1 is served from cache, OneChat never processes it, leaving `external_session_id` null. If turn 2 is then sent to OneChat, it arrives without session context.

## Requirements

1. Turn 1: cache applies as normal.
2. Turn 2+: always bypass cache and call OneChat directly.
3. If turn 1 was cached (`external_session_id` is null when turn 2 arrives): replay turn 1 to OneChat first, wait for completion, store `external_session_id`, then send turn 2.
4. Store `external_session_id` from the warm-up response; discard its response content.

## Solution: Shared `ensure_session_warmed()` Service

### New file: `backend/app/services/session.py`

```python
async def ensure_session_warmed(
    conversation: Conversation,
    client: httpx.AsyncClient,
    onechat_url: str,
    mcp_endpoint_url: str,
) -> None:
    if conversation.external_session_id is not None:
        return

    first_msg = await Message.filter(
        conversation_id=conversation.id,
        role="user"
    ).order_by("created_at").first()

    if first_msg is None:
        return

    payload = {
        "query": first_msg.content,
        "mcp_endpoint_url": mcp_endpoint_url,
        "session_id": str(conversation.id),
    }
    resp = await client.post(onechat_url, json=payload, timeout=60)
    resp.raise_for_status()

    conversation.external_session_id = str(conversation.id)
    await conversation.save(update_fields=["external_session_id"])
```

### Changes to `chat_external` and `chat_stream`

Cache lookup is gated on `message_count == 1`. Both endpoints already increment `message_count` before the cache check, so no new state tracking is needed.

**`chat_external`:**
```python
if message_count == 1:
    cached = await find_similar_question(...)
    if cached:
        ...return cached response...

if message_count > 1:
    await ensure_session_warmed(conversation, client, settings.ONECHAT_V3_URL, settings.MCP_ENDPOINT_URL)

resp = await client.post(settings.ONECHAT_V3_URL, json=payload, ...)
```

**`chat_stream`:**
```python
if message_count == 1:
    cached = await find_similar_question(...)
    if cached:
        ...return cached SSE stream...

if message_count > 1:
    await ensure_session_warmed(conversation, client, settings.ONECHAT_V3_URL, settings.MCP_ENDPOINT_URL)

async with client.stream("POST", settings.ONECHAT_V4_URL, json=payload, ...) as stream_resp:
```

## Data Flow

```
Turn 1
  cache hit  → return cached answer (external_session_id stays null)
  cache miss → call OneChat → store external_session_id

Turn 2+
  skip cache
  ensure_session_warmed():
    external_session_id set?  → no-op
    external_session_id null? → fetch first user msg → POST to OneChat
                                 → await → store external_session_id
  call OneChat with external_session_id
  return response to user
```

## Files Changed

| File | Change |
|------|--------|
| `backend/app/services/session.py` | New — `ensure_session_warmed()` |
| `backend/app/routers/chat.py` | Gate cache on `message_count == 1`; call `ensure_session_warmed` on turn 2+ |

## Testing

- Turn 1 cache hit: response is cached, `external_session_id` remains null
- Turn 1 cache miss: `external_session_id` is set after OneChat call
- Turn 2 after cache hit: warm-up fires, `external_session_id` is set, turn 2 response returned
- Turn 2 after cache miss: warm-up is no-op, turn 2 response returned
- Turn 3+: warm-up is always no-op (session already established)
