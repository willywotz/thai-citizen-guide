# Chat similarity-cache — deep audit

**Date:** 2026-07-02
**Scope:** The chat similarity-cache and everything that depends on it, across backend (FastAPI + Tortoise ORM, Postgres prod / SQLite tests) and frontend.
**Method:** Read-only audit via four parallel investigators (read path, write/seed path, config/DB layer, consumers/tests), cross-checked and de-duplicated.
**Context:** Performed right after removing the `/chat/internal` endpoint, `app/services/chat/graph.py`, and the `app/services/agency_directory.py` module — integrity-after-removal was an explicit check.

---

## The headline (compound failure)

Three independent findings chain into one systemic problem: **with shipped defaults the cache silently never hits, and the one configuration that "enables" it opens a 500 path.**

1. `EMBEDDING_API_KEY` defaults to `""` and isn't in `.env.example` → `generate_embedding` returns `None` → the vector path is never taken (`config.py:122`, `embedding.py:50`).
2. So every request falls to the **text fallback**, which needs `pg_trgm` + `fuzzystrmatch` — and **no migration creates them** (only `vector`, migration 9). Both branches throw → caught → silent cache-miss (`similarity.py:164,200,176-178,212-214`).
3. The moment an operator sets `EMBEDDING_API_KEY` to enable the vector path, `_vector_search` is the **only** search branch with no `try/except`, and `find_similar_question` is unguarded at both call sites — a missing extension / dimension mismatch / SQLite execution raises straight to **HTTP 500** (`similarity.py:135-148`, `chat.py:87,211`).

Net: out of the box the cache is a silent no-op; in prod it works only because pgvector is installed (mig 9) and `EMBEDDING_DIMENSIONS==384` matches the hard-coded index — both un-enforced invariants.

---

## Ranked findings

| # | Sev | Finding | Location |
|---|-----|---------|----------|
| 1 | **Critical** | `pg_trgm`/`fuzzystrmatch` never created by any migration → text fallback silently dead on any DB without out-of-band install | mig `9` only creates `vector` |
| 2 | **Critical** | `/stream` cache **hits re-seed** the cache: the hit path calls `_save_stream_conversation` (not a copy), minting a new success-conv + ConnectionLog + embedding with fresh `created_at`. Breaks the "no self-amplification" invariant `/external` upholds; popular/poisoned answers never age out of the window | `chat.py` cached_stream → `_save_stream_conversation` vs `_copy_cached_answer` |
| 3 | **High** | Cache poisoning: candidate queries filter only `role='user'`, no first-in-conversation restriction, so context-dependent **follow-up** turns (which every path still embeds+logs) become matchable by future single-turn queries. `parent_id IS NULL` isn't even a usable discriminator (all user msgs have null parent) | `similarity.py:140,167,205`; seeding `chat.py` /external+/stream |
| 4 | **High** | Cache disabled out-of-box: `EMBEDDING_API_KEY=""` default + absent from `.env.example` | `config.py:122`, `embedding.py:50` |
| 5 | **High** | `_vector_search` unguarded + `find_similar_question` not wrapped → 500 instead of graceful cache-miss on any pgvector error | `similarity.py:135-148`, `chat.py:87,211` |
| 6 | **Med** | Index dimension hard-coded `::vector(384)` but query uses `::vector({EMBEDDING_DIMENSIONS})`; any override → seq scan + wrong-length stored vectors, no assertion guards it | mig `9:10` vs `similarity.py:133` |
| 7 | **Med** | Postgres `levenshtein()` throws on >255-char args → broad `except` silently disables long-query matching (trgm has no such cap → inconsistent) | `similarity.py:202-214` |
| 8 | **Med** | Conversation-level status ratchet: a turn-2 failure flips the whole conversation to `failed`, de-seeding a still-valid turn-1 answer (and vice-versa) | `turn.py:44-48` × `similarity.py:62-64` |
| 9 | Low | Over-broad `except Exception` mislabels all failures as "extension not installed" | `similarity.py:176-178,212-214` |
| 10 | Low | Malformed 200 embedding response (`KeyError`/`IndexError`) escapes the retry loop unhandled | `embedding.py:74-82` |
| 11 | Low | `LIMIT 1` with no `ORDER BY` in the answer join → arbitrary pick among assistant retries | `similarity.py:60-68,73-81` |
| 12 | Low | Join gates on conv status but never checks `connection_logs.status='success'` — relies on an unenforced invariant | `similarity.py:63-64,76-77` |
| 13 | Low | Perf: no trgm GIN index on `content`; unindexed `assistant_message_id`/`parent_id` join; SELECTs pull the full (≤50k-char) `embedding` column when only `id` is used | migrations; `similarity.py:138,166,202` |
| 14 | Info | **`cached` flag is a dead output** — backend emits it on the JSON path only, frontend type omits it, nothing branches on it, SSE never sends it | `chat.py:101`, `schemas/chat.py:17`, `frontend/src/features/chat/chatApi.ts:15-27` |

---

## Dependency map

- **Read:** `find_similar_question` → `_vector_search` (pgvector) | `_text_fallback_search` → `_similarity_search` (pg_trgm) / `_levenshtein_search` (fuzzystrmatch) → `_fetch_answer_by_match` (inner-joins `connection_logs`, requires conversation `status='success'`). Window clamped by `effective_cutoff` = max(window, last flush).
- **Seed:** `save_turn` (one-way success/failed ratchet) + `store_embedding` (async background task) + `ConnectionLog` row. Driven **only** by `chat.py` `/external` and `/stream`; the MCP server and scheduler touch none of it.
- **Invalidate:** `flush_similarity_cache` — admin `POST /settings/cache/flush` (UI button in `SettingsPage.tsx`) + implicitly on agency create/update/delete (`crud.py:96,131`).
- **Config:** 10 knobs in `config.py:121-128,91-92` (threshold 0.95, window 3d=259200s, fallback "both", dims 384, embedding model/url/key/timeout, title/preview max length), all DB-overridable via `apply_overrides`.

### Config knobs

| Setting | Default | Used by |
|---|---|---|
| `EMBEDDING_API_URL` | `https://api.openai.com/v1/embeddings` | embedding.py:59 |
| `EMBEDDING_API_KEY` | `""` (disabled) | embedding.py:50 |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | embedding.py:54,65 |
| `EMBEDDING_DIMENSIONS` | `384` | embedding.py:67; similarity.py:133 |
| `EMBEDDING_TIMEOUT` | `5` | embedding.py:72 |
| `SIMILARITY_THRESHOLD` | `0.95` | similarity.py:29 |
| `SIMILARITY_WINDOW_SECONDS` | `259200` (3d) | similarity.py:30 |
| `SIMILARITY_FALLBACK` | `both` | similarity.py:107 |
| `TITLE_MAX_LENGTH` | `50` | turn.py:52; chat.py:375 |
| `PREVIEW_MAX_LENGTH` | `100` | turn.py:53; chat.py:376 |

### DB objects

| Object | Created by | Status |
|---|---|---|
| `vector` extension | mig `9:8` | OK |
| `idx_messages_embedding_cosine` (HNSW, `::vector(384)`, partial `role='user' AND embedding IS NOT NULL`) | mig `9:9-11` | OK, dim 384 |
| `idx_messages_role_created` | mig `17:9` | OK |
| `Message.embedding` (CharField ≤50000, cast to `::vector` at query) | `models/conversation.py:63` | present |
| `Conversation.status` (default success) | `models/conversation.py:16` | present |
| `ConnectionLog.assistant_message_id` / `message_id` | `models/connection_log.py:29,28` | present, unindexed |
| **`pg_trgm` extension** | — | **MISSING** |
| **`fuzzystrmatch` extension** | — | **MISSING** |

---

## Test coverage & the CI blind spot

Coverage is broad on the read primitives, embedding LRU cache, `save_turn` ratchet, and copy-on-hit. The real risks are the untested ones:

1. **Postgres paths skipped in default CI** — `_vector_search` and the `$1`-reuse join branch run only under `test_similarity_window_pg.py`, which is `skipif TEST_PG_URL` unset. The exact code that can 500 (#5) and the prod-only SQL are effectively **unverified in CI**.
2. **Multi-turn poisoning (#3) untested** — no test seeds a follow-up then matches it from a fresh query.
3. **Flush→exclusion untested end-to-end** — only `effective_cutoff` arithmetic is unit-tested; nothing asserts a flushed Q/A actually stops serving, nor that agency-mutation flush works.
4. **Flush HTTP happy-path untested** (only auditor-denial authz).
5. **`/stream` re-seed (#2) untested** — no test catches the self-amplification.

### Covered behaviors (for reference)

| Behavior | Test file |
|---|---|
| vector search when embedding present | `services/test_similarity.py:18` |
| text fallback when no embedding | `services/test_similarity.py:38` |
| returns None: no assistant / non-success conv / missing conn_log | `services/test_similarity.py:52,65,78`; `test_similarity_join.py` |
| ConnectionLog-required join | `services/test_similarity_join.py` |
| pg_trgm path / short-circuit / both-mode | `services/test_similarity.py:91,107,153,169` |
| levenshtein max-distance + extension-error fallback | `services/test_similarity.py:123,140` |
| window time boundary (Postgres only) | `services/test_similarity_window_pg.py` (skipif) |
| embedding LRU cache: hit/distinct/clear/mutation/TTL | `services/test_embedding_cache.py` |
| embedding generation (no key, retries, roundtrip) | `services/test_embedding.py` |
| save_turn ratchet / transactional count / empty→failed | `services/test_chat_turn.py:81,94,105` |
| _copy_cached_answer creates 2 msgs + parent link | `services/test_chat_turn.py:21` |
| external JSON cache hit copies into new conversation | `routers/test_chat_cache.py:38` |
| cache-hit rating does not touch origin | `routers/test_chat_cache.py:64` |
| stream cache hit emits message_id in `done` | `routers/test_chat_stream_message_id.py:38` |
| effective_cutoff moves forward after flush | `test_cache_flush.py:7` |
| flush endpoint denied to auditor | `test_role_allowlist.py:83` |
| `/chat/internal` removal regression guard | `test_chat_schema.py:18,27` |

---

## Integrity after removals: PASS

No live imports/calls to `/chat/internal`, `graph.py`, or `agency_directory` remain in backend, frontend, or e2e. Only residue:

- Two **stale comments** naming `graph.py`: `services/chat/dispatch.py:3`, `services/chat/turn.py:36`.
- Harmless `.pytest_cache` node-ids for the deleted test files (clear on next run).

---

## Recommended fixes (priority order)

- **P0**
  - Add `CREATE EXTENSION IF NOT EXISTS pg_trgm; ... fuzzystrmatch;` migration (#1).
  - Wrap `_vector_search` / `find_similar_question` in the same `try/except → None` guard as the other branches (#5).
  - Document `EMBEDDING_API_KEY` + all cache knobs in `.env.example` (#4).
- **P1**
  - Make `/stream` hits use a copy path like `_copy_cached_answer` instead of `_save_stream_conversation` (#2).
  - Restrict cache candidates to first-turn messages (order-by-created or `message_count`) (#3).
  - Assert/derive the index dimension from `EMBEDDING_DIMENSIONS` (#6).
- **P2**
  - Length-guard levenshtein (#7); narrow the `except` + real error logging (#9).
  - Add missing tests — unskipped Postgres coverage, and the poisoning/re-seed scenarios.
  - Clean the two stale `graph.py` comments.
