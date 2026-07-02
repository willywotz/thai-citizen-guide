# pg_trgm-only similarity cache — design

**Date:** 2026-07-02
**Status:** Approved (design), pending spec review
**Branch:** `refactor/pg-trgm-only-cache`

## Goal

Collapse the chat similarity-cache to a **single search path**: Postgres `pg_trgm` text similarity (`_similarity_search`). Remove the pgvector path (`_vector_search`) and the fuzzystrmatch path (`_levenshtein_search`), and tear out the entire embedding subsystem that existed only to feed vector search. Ship the `pg_trgm` extension migration that is currently missing, so the cache actually functions.

## Background

The cache (`app/services/similarity.py`) currently has three search branches selected in `find_similar_question`:

- `_vector_search` — pgvector cosine, used when an embedding is supplied.
- `_text_fallback_search` → `_similarity_search` (pg_trgm) and/or `_levenshtein_search` (fuzzystrmatch), selected by `SIMILARITY_FALLBACK`.

The `2026-07-02-chat-cache-audit.md` audit found: (a) `pg_trgm`/`fuzzystrmatch` extensions are never created by any migration, so the text paths silently die; (b) `_vector_search` is unguarded and can 500; (c) the vector path requires a whole embedding subsystem (`embedding.py`, `store_embedding`, `Message.embedding`, pgvector index/extension, 5 `EMBEDDING_*` settings). Standardising on `pg_trgm` removes the 500 path and the embedding machinery, at the cost of dropping semantic (vector) matching in favour of lexical similarity.

## Non-goals

- No behaviour change to caching semantics beyond the search algorithm (window, flush cutoff, success ratchet, copy-on-hit, ConnectionLog join all unchanged).
- Not addressing the other audit findings (`/stream` re-seed, follow-up poisoning) here — tracked separately.

## Design

### 1. Search layer — `app/services/similarity.py`

- **Delete** `_vector_search`, `_levenshtein_search`, and the `_text_fallback_search` wrapper.
- **`find_similar_question(query: str)`** — remove the `embedding` parameter. Body becomes:
  1. if `not settings.SIMILARITY_CACHE_ENABLED`: return `None`  *(single enable/disable gate — see §6)*
  2. `threshold = settings.SIMILARITY_THRESHOLD`
  3. `cutoff = await effective_cutoff(now() - timedelta(seconds=settings.SIMILARITY_WINDOW_SECONDS))`
  4. `match = await _similarity_search(query, threshold, cutoff)`
  5. if `match is None`: return `None`
  6. else resolve via `_fetch_answer_by_match` (unchanged).
- `_similarity_search`, `_fetch_answer_by_match` retained unchanged. `_similarity_search` already wraps its SQL in `try/except → None`, so no unguarded path remains (audit #5 resolved for the surviving code).
- **Remove** the `from app.services.embedding import encode_embedding` import and all `SIMILARITY_FALLBACK` references.

### 2. Embedding subsystem — delete entirely

- Delete `app/services/embedding.py` (module, TTL/LRU cache, `generate_embedding`, `encode_embedding`, `decode_embedding`, `_cache_get/_cache_set/_cache_clear`).
- Delete `store_embedding` from `app/services/chat/llm.py`; remove its `encode_embedding, generate_embedding` import. Keep `classify_message_category`.
- `app/routers/chat.py`:
  - `/external`: remove `embedding = await generate_embedding(query)` and the `store_embedding` background task; call `find_similar_question(query=query)`.
  - `/stream`: same removals in the cached branch and `_save_stream_conversation`.
  - Drop the `generate_embedding` and `store_embedding` imports.
- `app/models/conversation.py`: remove the `Message.embedding` field and its comment.

### 3. Config — `app/config.py`

- Remove settings: `EMBEDDING_API_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`, `EMBEDDING_TIMEOUT`, `SIMILARITY_FALLBACK`.
- Add setting `SIMILARITY_CACHE_ENABLED: bool = True` (see §6).
- Update the `"Embedding / similarity"` settings-group list to keep `SIMILARITY_THRESHOLD`, `SIMILARITY_WINDOW_SECONDS`, `SIMILARITY_CACHE_ENABLED` (rename group to `"Similarity"`).
- Remove `EMBEDDING_API_KEY` from `SECRET_FIELD_NAMES`.
- Keep `SIMILARITY_THRESHOLD`, `SIMILARITY_WINDOW_SECONDS`.

### 6. Enable/disable toggle — `SIMILARITY_CACHE_ENABLED`

- **Setting:** `SIMILARITY_CACHE_ENABLED: bool = True` in `app/config.py`, included in the `"Similarity"` settings group so it is DB-overridable via `apply_overrides` / `load_settings_from_db` and toggleable from the Settings UI (same mechanism as the existing flush control).
- **Semantics:** read-side gate only. When `False`, `find_similar_question` returns `None` immediately (step 1 in §1), so no cached answer is ever served and every query flows to the upstream LLM. Conversation history and `ConnectionLog` persistence are unchanged — disabling never drops normal data, it only stops *serving* cached hits.
- **Single gate:** the check lives inside `find_similar_question`, so both `/external` and `/stream` honour it without endpoint-level branching.
- **Default ON:** the cache now functions (pg_trgm migration lands in the same change), so it ships enabled; admins can disable at runtime.

### 4. Migration — new `19_*`

Postgres upgrade:
- `CREATE EXTENSION IF NOT EXISTS pg_trgm;`  **(required — the sole remaining search path depends on `similarity()`)**
- `DROP INDEX IF EXISTS idx_messages_embedding_cosine;`
- `ALTER TABLE "messages" DROP COLUMN "embedding";`
- Keep the `vector` extension (harmless; nothing depends on it after the column/index drop).

Downgrade (reverse):
- `ALTER TABLE "messages" ADD "embedding" VARCHAR(50000);`
- recreate `idx_messages_embedding_cosine` (HNSW, `vector_cosine_ops`, partial `role='user' AND embedding IS NOT NULL`);
- `DROP EXTENSION IF EXISTS pg_trgm;`

Generate via `aerich migrate` (for the column drop + MODELS_STATE), then hand-add the `CREATE EXTENSION pg_trgm` and the index drop/recreate (the index was created by raw SQL in migration 9, so aerich does not track it). Tests use `Tortoise.generate_schemas()` from the model, so removing the model field is sufficient for SQLite; the extension/index SQL only affects Postgres.

### 5. Tests (TDD)

- **Delete** `tests/services/test_embedding.py`, `tests/services/test_embedding_cache.py`.
- **Rework** `tests/services/test_similarity.py`: drop vector-search and levenshtein cases; keep/extend `_similarity_search` cases against the new single-path `find_similar_question(query)` API.
- **Add** a toggle test: with `SIMILARITY_CACHE_ENABLED=False`, `find_similar_question(query)` returns `None` and runs no DB query even when a matching Q/A exists; with it `True`, the same query hits.
- **Check/adjust** `tests/services/test_similarity_join.py` (join behaviour — should be unaffected) and `tests/services/test_similarity_window_pg.py` (Postgres, may reference vector — update to pg_trgm).
- **Update** `tests/routers/test_chat_cache.py`, `tests/services/test_chat_turn.py`, `tests/routers/test_chat_stream_message_id.py`: stop patching the removed `generate_embedding` / `store_embedding`.

## Data flow (after)

```
POST /chat (first turn) ─► find_similar_question(query)
                              └─► _similarity_search (pg_trgm) ─► _fetch_answer_by_match
                                    (window clamped by effective_cutoff; success-conv + ConnectionLog join)
seed: save_turn (+ ConnectionLog)      # no embedding write anymore
```

## Risks / trade-offs

- **Semantic → lexical matching.** pg_trgm matches on trigram overlap, not meaning; paraphrases that vector search would catch will now miss. Accepted per decision.
- **Destructive migration.** Dropping `messages.embedding` is irreversible in effect (downgrade recreates an empty column). Acceptable — the data only served vector search.
- **pg_trgm performance.** No `gin_trgm_ops` index on `content` yet (audit #13); acceptable for the current window size, revisit if volume grows.

## Acceptance criteria

- `find_similar_question(query)` returns a cached answer via pg_trgm when a similar prior successful Q/A exists within the window; `None` otherwise; never raises on DB/extension errors.
- `SIMILARITY_CACHE_ENABLED=False` makes `find_similar_question` return `None` without querying; `True` restores hits. The setting is runtime-toggleable via the Settings UI.
- No references to `_vector_search`, `_levenshtein_search`, `embedding.py`, `store_embedding`, `EMBEDDING_*`, or `SIMILARITY_FALLBACK` remain in `app/`.
- Migration 19 creates `pg_trgm` and drops the embedding column + index; `aerich upgrade`/`downgrade` succeed.
- Full backend suite green.
