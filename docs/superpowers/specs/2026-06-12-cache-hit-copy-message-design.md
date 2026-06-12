# Per-conversation copies of cached answers + real message id over SSE

**Date:** 2026-06-12
**Status:** Approved — ready for planning
**Branch:** `fix/cache-hit-copy-message`

## Problem

On a cache hit, `/chat/internal` (chat.py:55-70) and `/chat/external` (chat.py:160-176)
return the **original** assistant message's `id` and the **original** conversation's id,
and create no new database records.

Consequences:

1. **Feedback overwrites the original.** Rating the cached answer issues
   `PATCH /messages/{id}/rating` against the *original* message, so a rating in
   conversation B overwrites the `rating` / `feedback_text` saved in conversation A.
2. **Ambiguous origin question.** Feedback aggregation (feedback.py:208-228) resolves
   `parent_id` from that shared message and surfaces the wrong question for the rating.

Separately, the SSE path builds the assistant bubble with a client-generated id
(`generateUniqueId()`, chatHelpers.ts:77) and never receives the DB message id, so no
streamed answer can be rated against a real row.

The `/chat/stream` cache branch (chat.py:289-312) already copies — it calls
`_save_stream_conversation`, which creates fresh `user` + `assistant` records in the new
conversation — but it never returns the new id to the client.

## Goals

- On cache hit, the current conversation owns its own copy of the answer, with its own
  message id, so feedback is isolated per conversation and resolves the correct question.
- Streamed answers carry the real DB assistant message id so they can be rated.

## Non-goals

- Backfilling or repairing ratings already polluted by the old behavior.

## Design

### 1. Cache-hit copy (`/internal`, `/external`)

Add a shared helper:

```python
async def _copy_cached_answer(
    *, query, conversation_id, user, user_msg, asst_msg,
) -> Message:
```

It:

- creates a fresh `Conversation` with the already-generated `conversation_id`, owned by
  the current user (`title`/`preview` from `query`, `status="success"`,
  `message_count=2`, `response_time=0`);
- creates a `user` `Message` (copy of the query);
- creates an `assistant` `Message` copying `content`, `sources`, `agency_ids`, and
  `agent_steps`, with `parent_id` → the new user message;
- returns the new assistant `Message`.

Each endpoint's cache branch calls the helper, then returns the **new** assistant
message id, the **new** `conversation_id`, and `cached: true`.

**Copies are never cache sources.** The helper deliberately skips:

- **embedding storage** — so vector search (`WHERE embedding IS NOT NULL`,
  similarity.py:107) cannot match a copy;
- **`ConnectionLog` creation** — so even if a text fallback search (`_similarity_search`
  / `_levenshtein_search`, which do not filter on embedding) matches a copy's user
  message, `find_similar_question` returns `None` at the `ConnectionLog.get` step
  (similarity.py:61) and skips it.

This keeps the semantic cache pointing only at original questions and prevents copies
from feeding the cache or bloating the DB.

### 2. Streaming message id (`/stream`)

- `_save_stream_conversation` returns the new assistant message's id.
- The id is emitted to the client in the `done` SSE event as `message_id`.
  - The **cached** branch already saves before yielding `done`, so it just includes the
    id in the done payload.
  - The **non-cached** `event_generator` currently forwards the upstream `done` inline
    (chat.py:366-367) before the save runs (chat.py:382). Defer it: capture the upstream
    `done` data, run the save after the stream loop, then yield a single `done` event
    that includes `message_id`. (`done` is the terminal event; nothing depends on it
    arriving mid-stream.)
- Frontend:
  - `applyDoneEvent` captures `message_id` into `StreamingState` (e.g. `messageId`).
  - `buildAiMessageFromState` uses `state.messageId ?? generateUniqueId()`.
  - `DoneEvent` / `StreamingState` types gain the optional `message_id` / `messageId`
    field.

## Components touched

| File | Change |
|------|--------|
| `backend/app/routers/chat.py` | Add `_copy_cached_answer`; rewrite `/internal` + `/external` cache branches to use it; `_save_stream_conversation` returns the assistant id; `event_generator` defers `done`; `cached_stream` includes `message_id` in `done`. |
| `frontend/src/features/chat/chatHelpers.ts` | `applyDoneEvent` captures `message_id`; `buildAiMessageFromState` prefers it. |
| `frontend/src/shared/types` (and SSE event types) | Add `message_id` to the done event and `messageId` to `StreamingState`. |

## Data flow — cache hit on `/external`

```
query
  → generate_embedding
  → find_similar_question → (user_msg, asst_msg, conn_log)
  → _copy_cached_answer:
        Conversation.create(id=new conversation_id, user=current)
        Message.create(role="user",      content=query)            # no embedding
        Message.create(role="assistant", content=asst_msg.content, # copy fields
                       sources, agency_ids, agent_steps,
                       parent_id=new user msg)                      # no ConnectionLog
  → return { message_id: <new assistant id>,
             conversation_id: <new id>,
             cached: true }
```

Rating the new id is isolated to the new conversation; aggregation resolves `parent_id`
to the new user message (the correct question).

## Testing (TDD — failing tests first)

**Backend**

- Cache hit on `/external` (and `/internal`) creates a new conversation and two new
  messages with ids distinct from the originals.
- The original message's `rating` / `feedback_text` are untouched after the cache hit.
- Rating the new assistant message id leaves the original message's rating unchanged.
- A copy has no `ConnectionLog` and no stored embedding, and is not returned by a
  subsequent `find_similar_question`.

**Streaming**

- The `done` event carries `message_id` equal to the saved assistant message.
- Rating that id updates the corresponding row.

**Frontend**

- `applyDoneEvent` stores `message_id` into state.
- `buildAiMessageFromState` uses `state.messageId` when present and falls back to a
  generated id otherwise.
