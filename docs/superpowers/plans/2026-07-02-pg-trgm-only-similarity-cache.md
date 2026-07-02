# pg_trgm-only Similarity Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the chat similarity-cache to a single pg_trgm text-similarity path, remove the pgvector and levenshtein paths and the entire embedding subsystem, add a runtime enable/disable toggle, and ship the missing `pg_trgm` extension migration.

**Architecture:** `find_similar_question(query)` becomes a single-path function gated by `SIMILARITY_CACHE_ENABLED` and backed only by `_similarity_search` (pg_trgm). The embedding module, its writers, its settings, and the `Message.embedding` column/index are deleted. Tasks are ordered inside-out so the test suite stays green after every task (importers stop importing `embedding.py` before it is deleted).

**Tech Stack:** Python, FastAPI, Tortoise ORM, aerich migrations, pytest (asyncio), Postgres (prod) / in-memory SQLite (tests).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-02-pg-trgm-only-similarity-cache-design.md`.
- Branch: `refactor/pg-trgm-only-cache` (already checked out).
- Run everything from `backend/`: `cd backend`.
- Test runner is the venv Python: `.venv/bin/python -m pytest` (do NOT use `rtk pytest` — it fails to spawn in this env).
- TDD mandatory: write failing test → confirm it fails → minimal code → confirm it passes → commit.
- Timezone-aware "now" comes from `app.utils.now` — never `datetime.now()`.
- Keep imports sorted (stdlib, third-party, `app.*`).
- Every commit message ends with the trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Migration SQL is Postgres-only; SQLite tests build schema from the models via `Tortoise.generate_schemas()`, so removing a model field is sufficient for tests.
- `CREATE EXTENSION IF NOT EXISTS pg_trgm` is REQUIRED — it is the only remaining search path's dependency.
- After each task, run the full suite (`.venv/bin/python -m pytest -q`) and confirm green before moving on.

---

### Task 1: Add `SIMILARITY_CACHE_ENABLED` setting + enable/disable gate

Additive change: introduces the toggle and the short-circuit gate without touching the search algorithm yet. Keeps the current `find_similar_question(query, embedding=None)` signature.

**Files:**
- Modify: `backend/app/config.py` (settings + group list)
- Modify: `backend/app/services/similarity.py` (`find_similar_question` gate)
- Test: `backend/tests/services/test_similarity.py` (add one test)

**Interfaces:**
- Produces: `settings.SIMILARITY_CACHE_ENABLED: bool` (default `True`); `find_similar_question` returns `None` immediately when it is `False`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/services/test_similarity.py`:

```python
@pytest.mark.asyncio
async def test_find_similar_returns_none_when_cache_disabled():
    from app.config import settings
    from app.services import similarity

    with patch.object(settings, "SIMILARITY_CACHE_ENABLED", False), \
         patch.object(similarity, "_similarity_search", new=AsyncMock()) as msearch:
        result = await similarity.find_similar_question("q")

    assert result is None
    msearch.assert_not_awaited()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_similarity.py::test_find_similar_returns_none_when_cache_disabled -v`
Expected: FAIL — `AttributeError: SIMILARITY_CACHE_ENABLED` (setting does not exist yet).

- [ ] **Step 3: Add the setting**

In `backend/app/config.py`, immediately after the `SIMILARITY_FALLBACK` line (currently `SIMILARITY_FALLBACK: str = "both"  # ...`):

```python
    SIMILARITY_CACHE_ENABLED: bool = True
```

And append `"SIMILARITY_CACHE_ENABLED"` to the `"Embedding / similarity"` group list in `SETTINGS_GROUPS` so it is UI/DB-overridable:

```python
    "Embedding / similarity": ["EMBEDDING_API_URL", "EMBEDDING_API_KEY", "EMBEDDING_MODEL", "EMBEDDING_DIMENSIONS", "EMBEDDING_TIMEOUT", "SIMILARITY_THRESHOLD", "SIMILARITY_WINDOW_SECONDS", "SIMILARITY_FALLBACK", "SIMILARITY_CACHE_ENABLED"],
```

- [ ] **Step 4: Add the gate**

In `backend/app/services/similarity.py`, at the very top of `find_similar_question` body (before `threshold = settings.SIMILARITY_THRESHOLD`):

```python
    if not settings.SIMILARITY_CACHE_ENABLED:
        return None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_similarity.py::test_find_similar_returns_none_when_cache_disabled -v`
Expected: PASS.

- [ ] **Step 6: Run full suite + commit**

Run: `cd backend && .venv/bin/python -m pytest -q`  → expect all green.

```bash
git add backend/app/config.py backend/app/services/similarity.py backend/tests/services/test_similarity.py
git commit -m "feat(cache): add SIMILARITY_CACHE_ENABLED toggle + gate"
```

---

### Task 2: Collapse search to pg_trgm-only

Remove the vector and levenshtein branches, drop the `embedding` parameter, and update the two `chat.py` read sites. `embedding.py` is NOT deleted yet (still used by the write path), so the suite stays green.

**Files:**
- Modify: `backend/app/services/similarity.py`
- Modify: `backend/app/routers/chat.py` (two read sites + import)
- Test: `backend/tests/services/test_similarity.py` (replace file)
- Test: `backend/tests/services/test_similarity_join.py` (repoint patches)
- Test: `backend/tests/services/test_similarity_window_pg.py` (rewrite for pg_trgm-only)
- Test: `backend/tests/routers/test_chat_cache.py` (drop `generate_embedding` patches)
- Test: `backend/tests/routers/test_chat_stream_message_id.py` (drop `generate_embedding` patch)

**Interfaces:**
- Consumes: `settings.SIMILARITY_CACHE_ENABLED` (Task 1).
- Produces: `find_similar_question(query: str) -> tuple[Message, Message, ConnectionLog] | None` (no `embedding` param). `_similarity_search`, `_fetch_answer_by_match`, `effective_cutoff` unchanged.

- [ ] **Step 1: Replace the similarity test file with the single-path suite**

Overwrite `backend/tests/services/test_similarity.py` with:

```python
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_FIXED_CUTOFF = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _patch_cutoff(similarity):
    return patch.object(
        similarity, "effective_cutoff", new=AsyncMock(return_value=_FIXED_CUTOFF)
    )


@pytest.mark.asyncio
async def test_find_similar_returns_none_when_cache_disabled():
    from app.config import settings
    from app.services import similarity

    with patch.object(settings, "SIMILARITY_CACHE_ENABLED", False), \
         patch.object(similarity, "_similarity_search", new=AsyncMock()) as msearch:
        result = await similarity.find_similar_question("q")

    assert result is None
    msearch.assert_not_awaited()


@pytest.mark.asyncio
async def test_find_similar_uses_pg_trgm_similarity_search():
    from app.services import similarity

    match_msg = MagicMock(id="m1", conversation_id="c1")
    assistant = MagicMock(id="a1")
    conn_log = MagicMock()

    with _patch_cutoff(similarity), \
         patch.object(similarity, "_similarity_search", new=AsyncMock(return_value=match_msg)) as msearch, \
         patch.object(similarity, "_fetch_answer_by_match",
                      new=AsyncMock(return_value=(assistant, conn_log))):
        result = await similarity.find_similar_question("q")

    msearch.assert_awaited_once()
    assert result == (match_msg, assistant, conn_log)


@pytest.mark.asyncio
async def test_find_similar_returns_none_when_no_match():
    from app.services import similarity

    with _patch_cutoff(similarity), \
         patch.object(similarity, "_similarity_search", new=AsyncMock(return_value=None)):
        result = await similarity.find_similar_question("q")

    assert result is None


@pytest.mark.asyncio
async def test_find_similar_returns_none_when_answer_unresolvable():
    from app.services import similarity

    match_msg = MagicMock(id="m1", conversation_id="c1")
    with _patch_cutoff(similarity), \
         patch.object(similarity, "_similarity_search", new=AsyncMock(return_value=match_msg)), \
         patch.object(similarity, "_fetch_answer_by_match", new=AsyncMock(return_value=None)):
        result = await similarity.find_similar_question("q")

    assert result is None


@pytest.mark.asyncio
async def test_similarity_search_returns_none_on_extension_error():
    from app.services import similarity

    mock_conn = MagicMock()
    mock_conn.execute_query_dict = AsyncMock(side_effect=Exception("function similarity does not exist"))

    with patch.object(similarity.Tortoise, "get_connection", return_value=mock_conn):
        result = await similarity._similarity_search("hello world", 0.95, None)

    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_similarity.py -v`
Expected: FAIL — `find_similar_question()` still requires the old signature / references removed helpers; `TypeError` or attribute errors on `_vector_search`.

- [ ] **Step 3: Rewrite `find_similar_question` and delete the extra search functions**

In `backend/app/services/similarity.py`:

Remove the import `from app.services.embedding import encode_embedding` (top of file).

Replace the body of `find_similar_question` and its signature with:

```python
async def find_similar_question(
    query: str,
) -> tuple[Message, Message, ConnectionLog] | None:
    """Find a similar prior question within SIMILARITY_WINDOW_SECONDS via pg_trgm.

    Returns (user_message, assistant_message, connection_log) if a match above
    threshold exists in a successful conversation, else None. Never raises —
    DB/extension errors degrade to a cache miss.
    """
    if not settings.SIMILARITY_CACHE_ENABLED:
        return None

    threshold = settings.SIMILARITY_THRESHOLD
    cutoff = await effective_cutoff(now() - timedelta(seconds=settings.SIMILARITY_WINDOW_SECONDS))

    match = await _similarity_search(query, threshold, cutoff)
    if match is None:
        return None

    answer = await _fetch_answer_by_match(match)
    if answer is None:
        return None

    assistant_msg, conn_log = answer
    return (match, assistant_msg, conn_log)
```

Delete the functions `_text_fallback_search`, `_vector_search`, and `_levenshtein_search` entirely. Keep `_similarity_search` and `_fetch_answer_by_match` unchanged.

- [ ] **Step 4: Update the two `chat.py` read sites**

In `backend/app/routers/chat.py`:

Remove the import line `from app.services.embedding import generate_embedding`.

In the `/external` handler, replace:
```python
            embedding = await generate_embedding(query)
            cached = await find_similar_question(query=query, embedding=embedding)
```
with:
```python
            cached = await find_similar_question(query=query)
```

In the `/stream` handler, replace:
```python
            embedding = await generate_embedding(query)
            cached = await find_similar_question(query=query, embedding=embedding)
```
with:
```python
            cached = await find_similar_question(query=query)
```

- [ ] **Step 5: Drop the `generate_embedding` patches from router tests**

In `backend/tests/routers/test_chat_cache.py`, remove both occurrences of the line:
```python
    with patch.object(chat_router, "generate_embedding", new=AsyncMock(return_value=[0.1])), \
```
so each `with` block starts directly at `patch.object(chat_router, "find_similar_question", ...)`. (Two spots: `test_external_cache_hit_copies_into_new_conversation` and `test_external_cache_hit_rating_does_not_touch_origin`.)

In `backend/tests/routers/test_chat_stream_message_id.py`, in `test_cached_stream_emits_message_id_in_done`, remove the line:
```python
    with patch.object(chat_router, "generate_embedding", new=AsyncMock(return_value=[0.1])), \
```
so the block starts at `patch.object(chat_router, "find_similar_question", ...)`.

- [ ] **Step 6: Repoint `test_similarity_join.py` from `_text_fallback_search` to `_similarity_search`**

In `backend/tests/services/test_similarity_join.py`, replace every occurrence (7 total) of:
```python
        similarity, "_text_fallback_search", new=AsyncMock(return_value=user_msg)
```
with:
```python
        similarity, "_similarity_search", new=AsyncMock(return_value=user_msg)
```
and the one occurrence of:
```python
        similarity, "_text_fallback_search", new=AsyncMock(return_value=None)
```
with:
```python
        similarity, "_similarity_search", new=AsyncMock(return_value=None)
```
(The return contract is identical — both return the matched user `Message` or `None` — and `_fetch_answer_by_match` still runs against the live SQLite db, so behavior is unchanged.)

- [ ] **Step 7: Rewrite `test_similarity_window_pg.py` for the pg_trgm-only API**

This file has a module-level `from app.services.embedding import encode_embedding` (fails to import once `embedding.py` is deleted in Task 4) and drives the removed vector path. Overwrite the whole file with:

```python
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
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_similarity.py tests/services/test_similarity_join.py tests/routers/test_chat_cache.py tests/routers/test_chat_stream_message_id.py -q`
Expected: PASS. (`test_similarity_window_pg.py` is skipped without `TEST_PG_URL`.)

- [ ] **Step 9: Run full suite + commit**

Run: `cd backend && .venv/bin/python -m pytest -q` → expect green.

```bash
git add backend/app/services/similarity.py backend/app/routers/chat.py backend/tests/services/test_similarity.py backend/tests/services/test_similarity_join.py backend/tests/services/test_similarity_window_pg.py backend/tests/routers/test_chat_cache.py backend/tests/routers/test_chat_stream_message_id.py
git commit -m "refactor(cache): pg_trgm-only search, drop vector/levenshtein paths"
```

---

### Task 3: Remove the embedding write path

Stop writing embeddings. After this task nothing in `app/` imports `embedding.py`.

**Files:**
- Modify: `backend/app/routers/chat.py` (two `store_embedding` tasks + import)
- Modify: `backend/app/services/chat/llm.py` (remove `store_embedding` + imports)

**Interfaces:**
- Consumes: nothing new.
- Produces: `llm.py` no longer exports `store_embedding`; `chat.py` no longer schedules it.

- [ ] **Step 1: Remove `store_embedding` scheduling from `chat.py`**

In `backend/app/routers/chat.py`:

Change the llm import from:
```python
from app.services.chat.llm import classify_message_category, store_embedding
```
to:
```python
from app.services.chat.llm import classify_message_category
```

Remove both lines that schedule it (in `/external` and in `_save_stream_conversation`):
```python
        background_tasks.add_task(store_embedding, saved.user_message_id, query)
```

- [ ] **Step 2: Remove `store_embedding` from `llm.py`**

In `backend/app/services/chat/llm.py`:

Remove the import:
```python
from app.services.embedding import encode_embedding, generate_embedding
```

Delete the function:
```python
async def store_embedding(message_id: str, query: str) -> None:
    embedding = await generate_embedding(query)
    if embedding is not None:
        encoded = encode_embedding(embedding)
        await Message.filter(id=message_id).update(embedding=encoded)
```

- [ ] **Step 3: Verify no live references to `embedding.py` remain**

Run: `cd backend && grep -rn "services.embedding\|store_embedding\|generate_embedding\|encode_embedding\|decode_embedding" app/`
Expected: no output (empty).

- [ ] **Step 4: Run full suite**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: all green (embedding.py now orphaned but still present, so its own tests still pass).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/chat.py backend/app/services/chat/llm.py
git commit -m "refactor(cache): remove embedding write path (store_embedding)"
```

---

### Task 4: Delete the embedding module + its tests + config

**Files:**
- Delete: `backend/app/services/embedding.py`
- Delete: `backend/tests/services/test_embedding.py`
- Delete: `backend/tests/services/test_embedding_cache.py`
- Modify: `backend/app/config.py`

**Interfaces:**
- Produces: `settings` no longer has `EMBEDDING_*` or `SIMILARITY_FALLBACK`; `"Similarity"` group = `SIMILARITY_THRESHOLD`, `SIMILARITY_WINDOW_SECONDS`, `SIMILARITY_CACHE_ENABLED`.

- [ ] **Step 1: Delete the module and its tests**

```bash
cd backend
git rm app/services/embedding.py tests/services/test_embedding.py tests/services/test_embedding_cache.py
```

- [ ] **Step 2: Remove `EMBEDDING_*` and `SIMILARITY_FALLBACK` from config**

In `backend/app/config.py`, delete these setting lines:
```python
    EMBEDDING_API_URL: str = "https://api.openai.com/v1/embeddings"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 384
    EMBEDDING_TIMEOUT: int = 5
```
and:
```python
    SIMILARITY_FALLBACK: str = "both"  # "similarity", "levenshtein", or "both"
```

Replace the group entry:
```python
    "Embedding / similarity": ["EMBEDDING_API_URL", "EMBEDDING_API_KEY", "EMBEDDING_MODEL", "EMBEDDING_DIMENSIONS", "EMBEDDING_TIMEOUT", "SIMILARITY_THRESHOLD", "SIMILARITY_WINDOW_SECONDS", "SIMILARITY_FALLBACK", "SIMILARITY_CACHE_ENABLED"],
```
with:
```python
    "Similarity": ["SIMILARITY_THRESHOLD", "SIMILARITY_WINDOW_SECONDS", "SIMILARITY_CACHE_ENABLED"],
```

Remove `"EMBEDDING_API_KEY"` from `SECRET_FIELD_NAMES` (leave the other names intact).

- [ ] **Step 3: Verify no dangling config references**

Run: `cd backend && grep -rn "EMBEDDING_\|SIMILARITY_FALLBACK" app/ tests/`
Expected: no output.

- [ ] **Step 4: Run full suite**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: green (the two embedding test files are gone; total count drops accordingly).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(cache): delete embedding module, tests, and EMBEDDING_* config"
```

---

### Task 5: Drop `Message.embedding` field + migration 19

**Files:**
- Modify: `backend/app/models/conversation.py` (remove field + comment)
- Create: `backend/migrations/models/19_<timestamp>_drop_embedding_add_pg_trgm.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Message` has no `embedding` attribute; Postgres schema drops the column + cosine index and gains the `pg_trgm` extension.

- [ ] **Step 1: Write the failing test**

Add `backend/tests/services/test_message_no_embedding.py`:

```python
import pytest

from app.models.conversation import Message


@pytest.mark.asyncio
async def test_message_has_no_embedding_field(db):
    assert "embedding" not in Message._meta.fields_map
    # Creating a message without embedding still works.
    from app.models.conversation import Conversation
    conv = await Conversation.create(status="success")
    msg = await Message.create(conversation=conv, role="user", content="hi")
    assert msg.id is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_message_no_embedding.py -v`
Expected: FAIL on `assert "embedding" not in Message._meta.fields_map` (field still present).

- [ ] **Step 3: Remove the field from the model**

In `backend/app/models/conversation.py`, delete the comment + field:
```python
    # JSON-encoded vector; stays TEXT so SQLite tests work. Indexed via idx_messages_embedding_cosine
    # (HNSW, vector_cosine_ops, dimensions fixed at EMBEDDING_DIMENSIONS=384) on Postgres.
    embedding = fields.CharField(max_length=50000, null=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_message_no_embedding.py -v`
Expected: PASS (SQLite schema is generated from the model, so the column is already gone there).

- [ ] **Step 5: Generate the migration and hand-edit the SQL**

Run: `cd backend && .venv/bin/aerich migrate --name drop_embedding_add_pg_trgm`
This creates `migrations/models/19_<timestamp>_drop_embedding_add_pg_trgm.py` with a correct `MODELS_STATE` and a generated `ALTER TABLE "messages" DROP COLUMN "embedding";`.

Then edit that file's `upgrade`/`downgrade` bodies to also handle the raw-SQL index (aerich does not track it) and create `pg_trgm`. Final bodies:

```python
async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE EXTENSION IF NOT EXISTS pg_trgm;
        DROP INDEX IF EXISTS idx_messages_embedding_cosine;
        ALTER TABLE "messages" DROP COLUMN "embedding";
        """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "messages" ADD "embedding" VARCHAR(50000);
        CREATE INDEX IF NOT EXISTS idx_messages_embedding_cosine
        ON messages USING hnsw (((embedding)::vector(384)) vector_cosine_ops)
        WHERE role = 'user' AND embedding IS NOT NULL;
        DROP EXTENSION IF EXISTS pg_trgm;
        """
```

Keep the auto-generated `MODELS_STATE` and `RUN_IN_TRANSACTION` lines as produced by aerich. (If `aerich migrate` cannot run in this environment, hand-write the file modeled on `migrations/models/18_20260623154428_agency_add_stats_reset_at.py`, using the two SQL bodies above, and note that `MODELS_STATE` must be regenerated by aerich before the next migration.)

- [ ] **Step 6: Run full suite**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/conversation.py backend/migrations/models/ backend/tests/services/test_message_no_embedding.py
git commit -m "refactor(cache): drop Message.embedding column, add pg_trgm migration"
```

---

## Final verification

- [ ] `cd backend && grep -rn "_vector_search\|_levenshtein_search\|_text_fallback_search\|services.embedding\|store_embedding\|EMBEDDING_\|SIMILARITY_FALLBACK" app/ tests/` → no output.
- [ ] `cd backend && .venv/bin/python -m pytest -q` → all green.
- [ ] `find_similar_question(query)` works single-path; `SIMILARITY_CACHE_ENABLED=False` disables hits.
- [ ] Migration 19 contains `CREATE EXTENSION IF NOT EXISTS pg_trgm`, the index drop, and the column drop.
