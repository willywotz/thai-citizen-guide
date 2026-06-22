# Backend Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the "make it work → make it right → make it fast" progression to `backend/app/`: fix correctness bugs (conversation status, LLM JSON validation, fire-and-forget failures, rate-limiter degrade, config override reporting, bare excepts), then decompose oversized modules, then remove hot-path N+1s and add caching/indexes — each refactor preceded by characterization tests.

**Architecture:** Routers stay thin HTTP/SSE adapters; business logic lives in `app/services/`. New `save_turn` is the single transactional conversation+message+log writer. `analytics` and `agencies` become packages. Rate limiter degrades to a shared in-process limiter on Redis failure. See `docs/superpowers/specs/2026-06-23-backend-refactor-design.md`.

**Tech Stack:** Python 3.12, FastAPI, Tortoise ORM, LangGraph, httpx, pytest-asyncio, Redis (redis.asyncio), FastMCP, OpenTelemetry.

All commands run from repo root unless noted. Tests run from `backend/`. Use the in-memory SQLite `db` fixture (`backend/tests/conftest.py`). Use `rtk` for git/test/grep per repo convention.

---

## File Map

**Created:**
- `backend/app/concurrency.py` — `spawn_logged`
- `backend/app/services/chat/turn.py` — `save_turn`
- `backend/app/services/agency_directory.py` — cached active-agency snapshot
- `backend/app/services/heatmap.py` — usage-heatmap aggregation
- `backend/app/services/analytics/__init__.py`, `dashboard.py`, `health.py`, `brief.py`
- `backend/app/routers/agencies/__init__.py`, `crud.py`, `lifecycle.py`, `golden.py`, `owners.py`, `spec.py`
- Tests: `backend/tests/test_concurrency.py`, `backend/tests/services/test_chat_turn.py`, `backend/tests/test_config_overrides_report.py`, `backend/tests/test_rate_limit_degrade.py`, `backend/tests/services/test_agency_directory.py`, `backend/tests/test_public_status_query_count.py`, `backend/tests/services/test_similarity_join.py`, `backend/tests/services/test_embedding_cache.py`, `backend/tests/test_conversations_history.py`, `backend/tests/test_connection_logs_filter.py`
- `backend/migrations/models/*_backend_refactor_indexes.py` (aerich-generated)

**Modified:**
- `backend/app/routers/chat.py` (602 → ~250)
- `backend/app/services/chat/graph.py` (validate JSON, injectable loader, cached agencies)
- `backend/app/services/rate_limit.py` (degrade-to-inprocess)
- `backend/app/config.py` (`apply_overrides` report + `DB_POOL_*`)
- `backend/app/routers/insight.py` (`except Exception`; heatmap → service)
- `backend/app/routers/conversations.py` (`date_from`/`date_to`/`page`/`page_size` params; full-count `total`)
- `backend/app/routers/connection_logs.py` (`status`/`connection_type` filters; `page_size` alias)
- `backend/app/routers/public_status.py` (single grouped query)
- `backend/app/services/similarity.py` (folded join)
- `backend/app/services/embedding.py` (shared client + cache)
- `backend/app/scheduler.py` (`spawn_logged`; per-item timeout)
- `backend/app/mcp/server.py` (per-request id defaulting)
- `backend/app/main.py` (import `agencies` package; wire pool config)

**Deleted:**
- `backend/app/routers/agencies.py` (replaced by package)

---

## Task 1: Create branch and add `spawn_logged` (foundation, TDD)

**Files:** `backend/app/concurrency.py`, `backend/tests/test_concurrency.py`

- [ ] **Step 1: Create branch**

```bash
rtk git checkout -b refactor/backend-work-right-fast
```

- [ ] **Step 2: Write failing test** — `backend/tests/test_concurrency.py`

```python
import asyncio
import logging

from app.concurrency import spawn_logged


async def test_spawn_logged_runs_coro():
    done = asyncio.Event()

    async def work():
        done.set()

    spawn_logged(work(), name="work")
    await asyncio.wait_for(done.wait(), timeout=1)


async def test_spawn_logged_logs_exception(caplog):
    async def boom():
        raise ValueError("kaboom")

    with caplog.at_level(logging.ERROR, logger="app.concurrency"):
        spawn_logged(boom(), name="boom")
        await asyncio.sleep(0.05)
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert any("boom" in r.getMessage() and "kaboom" in str(r.exc_info or r.getMessage())
               or "boom" in r.getMessage() for r in errors)
```

- [ ] **Step 3: Confirm RED**

```bash
cd backend && rtk pytest tests/test_concurrency.py -q
```

Expected: `ModuleNotFoundError: No module named 'app.concurrency'` (collection error = red).

- [ ] **Step 4: Implement** — `backend/app/concurrency.py`

```python
"""Fire-and-forget task helper that never silently drops exceptions."""
import asyncio
import logging

from opentelemetry import trace

logger = logging.getLogger(__name__)
_tracer = trace.get_tracer(__name__)
_pending: set[asyncio.Task] = set()


def spawn_logged(coro, *, name: str) -> asyncio.Task:
    """Schedule `coro` as a background task; log any exception it raises.

    Holds a strong reference until the task completes (asyncio only keeps weak
    references, so an un-retained task can be garbage-collected mid-flight).
    """
    task = asyncio.ensure_future(coro)
    task.set_name(name)
    _pending.add(task)

    def _done(t: asyncio.Task) -> None:
        _pending.discard(t)
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            logger.error("background task %s failed: %s", name, exc, exc_info=exc)
            trace.get_current_span().add_event(
                "background_task.failed", {"task": name, "error": type(exc).__name__}
            )

    task.add_done_callback(_done)
    return task
```

- [ ] **Step 5: Confirm GREEN**

```bash
cd backend && rtk pytest tests/test_concurrency.py -q
```

Expected: `2 passed`.

- [ ] **Step 6: Commit**

```bash
rtk git add -A && rtk git commit -m "feat(concurrency): add spawn_logged for observable fire-and-forget tasks"
```

---

## Task 2: Characterize chat save paths (characterization-first, no behavior change)

**Files:** `backend/tests/services/test_chat_turn.py`

Pin the CURRENT observable behavior of the three save paths before extracting/changing them. These must pass against unchanged `chat.py`.

- [ ] **Step 1: Write characterization tests**

```python
"""Characterization tests for chat save behavior BEFORE the save_turn refactor.

These pin current observable behavior. They must pass against unchanged chat.py.
SQLite-portable: no external HTTP, no Postgres-only SQL.
"""
import pytest

from app.models import Conversation, Message
from app.routers.chat import _copy_cached_answer, _save_stream_conversation
from fastapi import BackgroundTasks


@pytest.mark.usefixtures("db")
async def test_copy_cached_answer_creates_two_messages_and_links_parent():
    user_msg = await Message.create(conversation=await _conv(), role="user", content="q", category="cat")
    asst = await Message.create(conversation=await Conversation.get(id=user_msg.conversation_id),
                                role="assistant", content="a", sources=[{"x": 1}], parent_id=user_msg.id)

    new_asst = await _copy_cached_answer(
        query="q again", conversation_id=str(__import__("uuid").uuid4()),
        user=None, user_msg=user_msg, asst_msg=asst,
    )
    assert new_asst.role == "assistant"
    assert new_asst.content == "a"
    assert new_asst.sources == [{"x": 1}]
    conv = await Conversation.get(id=new_asst.conversation_id)
    assert conv.status == "success"          # CURRENT behavior — pinned
    assert conv.message_count == 2


@pytest.mark.usefixtures("db")
async def test_save_stream_conversation_success_status_current():
    cid = str(__import__("uuid").uuid4())
    assistant_id = await _save_stream_conversation(
        query="q", conversation_id=cid,
        answer_data={"answer": "hello", "sections": []},
        session_id=None, total_ms=10, latency_ms=5,
        user=None, background_tasks=BackgroundTasks(),
    )
    conv = await Conversation.get(id=cid)
    assert conv.status == "success"          # CURRENT behavior — pinned
    assert conv.message_count == 2
    assert await Message.filter(conversation_id=cid, role="assistant").count() == 1
    assert str(assistant_id)


async def _conv():
    return await Conversation.create(title="t", preview="p")
```

- [ ] **Step 2: Confirm GREEN against unchanged code**

```bash
cd backend && rtk pytest tests/services/test_chat_turn.py -q
```

Expected: `2 passed`. (If red, fix the test to match reality before proceeding — do not change `chat.py` yet.)

- [ ] **Step 3: Commit**

```bash
rtk git add -A && rtk git commit -m "test(chat): characterize current save-path status and message-count behavior"
```

---

## Task 3: Extract `save_turn` and derive conversation status (WORK — BC #1, #3)

**Files:** `backend/app/services/chat/turn.py`, `backend/app/routers/chat.py`, `backend/tests/services/test_chat_turn.py`

- [ ] **Step 1: RED test for the new `failed` status** — append to `test_chat_turn.py`

```python
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
```

- [ ] **Step 2: Confirm RED**

```bash
cd backend && rtk pytest tests/services/test_chat_turn.py -q
```

Expected: import error / failures for the two new tests.

- [ ] **Step 3: Implement** — `backend/app/services/chat/turn.py`

```python
"""Single transactional writer for a chat turn (conversation + 2 messages)."""
from dataclasses import dataclass

from tortoise.exceptions import DoesNotExist
from tortoise.transactions import in_transaction

from app.config import settings
from app.models.conversation import Conversation, Message
from app.utils import now


@dataclass
class SavedTurn:
    user_message_id: str
    assistant_message_id: str
    conversation_id: str


async def save_turn(
    *,
    query: str,
    conversation_id: str,
    answer: str,
    references: list,
    category: str | None,
    agency_ids: list[str],
    response_time: int,
    user,
    succeeded: bool,
    external_session_id: str | None = None,
    errors: list | None = None,
) -> SavedTurn:
    """Create/extend a conversation and write the user+assistant messages atomically.

    `succeeded=False` records the conversation as status="failed" so it never
    seeds the similarity cache (find_similar_question filters status="success").
    """
    status = "success" if succeeded else "failed"
    async with in_transaction():
        try:
            conv = await Conversation.get(id=conversation_id)
            conv.message_count += 2
            conv.updated_at = now()
            if not succeeded:
                conv.status = "failed"
            await conv.save()
        except DoesNotExist:
            conv = await Conversation.create(
                id=conversation_id,
                title=query[: settings.TITLE_MAX_LENGTH],
                preview=query[: settings.PREVIEW_MAX_LENGTH],
                agencies=[],
                status=status,
                message_count=2,
                response_time=response_time,
                user_id=user.id if user else None,
                external_session_id=external_session_id,
            )
        user_msg = await Message.create(
            conversation_id=conversation_id, role="user", content=query, category=category,
        )
        asst_msg = await Message.create(
            parent_id=user_msg.id,
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            sources=references,
            response_time=response_time,
            agency_ids=agency_ids,
            errors=errors or [],
        )
    return SavedTurn(str(user_msg.id), str(asst_msg.id), conversation_id)
```

- [ ] **Step 4: Rewire `/chat/internal` in `chat.py`** to compute `succeeded` and call `save_turn` + `spawn_logged`.

Replace the inline save block (current chat.py lines ~120-155) with:

```python
routes = result.get("routes", [])
results = result.get("results", [])
succeeded = bool(routes) and any(r.get("status") == "ok" for r in results)

saved = await save_turn(
    query=query, conversation_id=conversation_id, answer=answer,
    references=references, category=category,
    agency_ids=[str(ag["agency_id"]) for ag in routes],
    response_time=response_time, user=user, succeeded=succeeded,
)
spawn_logged(store_embedding(saved.user_message_id, query), name="store_embedding")
```

Add imports near the top of `chat.py`:

```python
from app.concurrency import spawn_logged
from app.services.chat.turn import save_turn
```

Remove the now-unused `asyncio.create_task(store_embedding(...))` line.

> Note: `build_graph().ainvoke(...)` returns `routes` and `results` in the final state (graph.py `AgentState`), so they are available here. Keep `extract_tag` handling for `references`/`category` unchanged.

- [ ] **Step 5: Confirm GREEN** (new + characterization tests)

```bash
cd backend && rtk pytest tests/services/test_chat_turn.py tests/routers/test_chat_cache.py tests/routers/test_chat_stream_message_id.py -q
```

Expected: all pass. The earlier characterization tests for `_save_stream_conversation`/`_copy_cached_answer` still pass (those paths unchanged in this task).

- [ ] **Step 6: Format, lint, commit**

```bash
cd backend && gofmt_skip=1; python -m black app/services/chat/turn.py app/routers/chat.py 2>/dev/null || true
cd backend && rtk pytest tests/ -q -k "chat" 
rtk git add -A && rtk git commit -m "refactor(chat): extract transactional save_turn; mark failed turns (BC #1, #3)"
```

---

## Task 4: Validate router LLM JSON (WORK — BC #2)

**Files:** `backend/app/services/chat/graph.py`, `backend/tests/services/test_chat_graph.py`

- [ ] **Step 1: RED test** — append to `test_chat_graph.py`

```python
async def test_route_query_invalid_json_yields_no_routes(monkeypatch):
    import app.services.chat.graph as g
    from app.services.chat.graph import AgentState, route_query

    async def fake_llm(_messages):
        return {"content": "not json at all"}

    monkeypatch.setattr(g, "call_llm", fake_llm)
    out = await route_query(AgentState(query="q", agencies=[]))
    assert out == {"routes": []}


async def test_route_query_missing_routes_key(monkeypatch):
    import app.services.chat.graph as g
    from app.services.chat.graph import AgentState, route_query

    async def fake_llm(_messages):
        return {"content": '{"foo": 1}'}

    monkeypatch.setattr(g, "call_llm", fake_llm)
    out = await route_query(AgentState(query="q", agencies=[]))
    assert out == {"routes": []}
```

- [ ] **Step 2: Confirm RED** (current code raises `json.JSONDecodeError`)

```bash
cd backend && rtk pytest tests/services/test_chat_graph.py -q -k invalid_json
```

Expected: failure (uncaught `JSONDecodeError`).

- [ ] **Step 3: Implement** — replace the parse block in `route_query` (graph.py ~lines 38-47)

```python
    text = response.get("content", "").strip()

    if "<think>" in text:
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]

    routes = _parse_routes(text)
    if not routes:
        return {"routes": []}
```

Add a module-level helper to `graph.py`:

```python
def _parse_routes(text: str) -> list[dict]:
    """Parse the router LLM output. Returns [] on any malformed output."""
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        logger.warning("router LLM returned non-JSON output; treating as no routes")
        return []
    routes = parsed.get("routes") if isinstance(parsed, dict) else None
    if not isinstance(routes, list):
        return []
    return [r for r in routes if isinstance(r, dict) and r.get("agency_id")]
```

Add at top of `graph.py` if absent:

```python
import logging
logger = logging.getLogger(__name__)
```

- [ ] **Step 4: Confirm GREEN**

```bash
cd backend && rtk pytest tests/services/test_chat_graph.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
rtk git add -A && rtk git commit -m "fix(chat): validate router LLM JSON, no-route fallback instead of 500 (BC #2)"
```

---

## Task 5: Rate limiter degrades to in-process (WORK — BC #4)

**Files:** `backend/app/services/rate_limit.py`, `backend/tests/test_rate_limit_degrade.py`

- [ ] **Step 1: RED test** — `backend/tests/test_rate_limit_degrade.py`

```python
import app.services.rate_limit as rl
from app.services.rate_limit import RedisSlidingWindowLimiter
from tests.test_fail_open_observability import FakeClient, FakeScript  # reuse fakes


import pytest


@pytest.fixture(autouse=True)
def _reset_health():
    rl._redis_health.failing = False
    rl._redis_health.fail_open_total = 0
    rl._redis_health._since = 0
    yield


async def test_degrades_to_inprocess_and_enforces_limit():
    # Redis always fails -> limiter must fall back to a shared in-process limiter
    # and still enforce the per-worker budget (NOT fail open).
    lim = RedisSlidingWindowLimiter(FakeClient(FakeScript(fail_n=10_000)))
    allowed = []
    for _ in range(5):
        allowed.append((await lim.check("user:1", limit=2)).allowed)
    assert allowed[:2] == [True, True]
    assert allowed[2] is False  # third request blocked by in-process fallback
```

- [ ] **Step 2: Confirm RED** (current code fails open → all True)

```bash
cd backend && rtk pytest tests/test_rate_limit_degrade.py -q
```

Expected: assertion failure on `allowed[2] is False`.

- [ ] **Step 3: Implement** — in `rate_limit.py`

Add a shared fallback limiter (module level, after `_redis_health`):

```python
# Shared per-worker fallback used when Redis is unreachable. One instance so the
# budget is consistent across all three Redis limiters during an outage.
_fallback_limiter = InProcessLimiter()
```

Replace the `except (RedisError, OSError)` block in `RedisSlidingWindowLimiter.check`:

```python
        except (RedisError, OSError) as exc:  # connection/timeout — degrade
            span = trace.get_current_span()
            span.add_event(
                "rate_limit.fail_open", {"key": key, "error": type(exc).__name__}
            )
            span.add_event("rate_limit.degraded_to_inprocess", {"key": key})
            if _redis_health.record_failure():
                logger.warning(
                    "rate limiter: Redis unavailable, degrading to in-process "
                    "limiter (per-worker budget still enforced)",
                    exc_info=exc,
                )
            return await _fallback_limiter.check(key, limit=limit, window_s=window_s)
```

- [ ] **Step 4: Confirm GREEN, and that existing fail-open observability still holds**

```bash
cd backend && rtk pytest tests/test_rate_limit_degrade.py tests/test_fail_open_observability.py -q
```

Expected: degrade test passes. `test_fail_open_observability` may need its name/assertions reconciled — the span event `rate_limit.fail_open` and the single healthy→failing WARNING are preserved, so those assertions still pass. If `test_fail_open_returns_allowed_and_logs_once` asserts `RateLimitResult(True, 0)` for an unlimited check (`limit=5`, only 3 calls), the in-process fallback still returns allowed for the first 5 → still `True`; keep it green.

- [ ] **Step 5: Commit**

```bash
rtk git add -A && rtk git commit -m "fix(rate-limit): degrade to in-process limiter on Redis failure instead of fail-open (BC #4)"
```

---

## Task 6: `apply_overrides` reports unknown/invalid keys + bare excepts (WORK — BC #5, #6)

**Files:** `backend/app/config.py`, `backend/app/routers/insight.py`, `backend/tests/test_config_overrides_report.py`

- [ ] **Step 1: RED test** — `backend/tests/test_config_overrides_report.py`

```python
import logging

from app.config import Settings


def test_apply_overrides_reports_unknown_and_invalid(caplog):
    s = Settings()
    with caplog.at_level(logging.WARNING, logger="app.config"):
        report = s.apply_overrides({
            "USER_RATE_LIMIT_RPM": "42",   # valid
            "NOPE_KEY": "x",               # unknown
            "JWT_EXPIRE_MINUTES": "abc",   # invalid int
        })
    assert s.USER_RATE_LIMIT_RPM == 42
    assert report.applied == ["USER_RATE_LIMIT_RPM"]
    assert report.unknown == ["NOPE_KEY"]
    assert report.invalid == ["JWT_EXPIRE_MINUTES"]
    assert any("NOPE_KEY" in r.getMessage() for r in caplog.records)
```

- [ ] **Step 2: Confirm RED**

```bash
cd backend && rtk pytest tests/test_config_overrides_report.py -q
```

Expected: failure (`apply_overrides` returns `None`).

- [ ] **Step 3: Implement** — in `config.py`

Add near the top:

```python
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class OverrideReport:
    applied: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    invalid: list[str] = field(default_factory=list)
```

Replace `apply_overrides`:

```python
    def apply_overrides(self, overrides: dict[str, str]) -> "OverrideReport":
        report = OverrideReport()
        for key, raw_value in overrides.items():
            field_info = self.model_fields.get(key)
            if field_info is None:
                report.unknown.append(key)
                logger.warning("ignoring unknown settings override key: %s", key)
                continue
            try:
                parsed = _deserialize(raw_value, field_info.annotation)
                object.__setattr__(self, key, parsed)
                report.applied.append(key)
            except Exception:
                report.invalid.append(key)
                logger.warning("failed to parse override %s=%r; keeping default", key, raw_value)
        return report
```

Keep `load_settings_from_db` calling it (return value optional; it may log the report).

- [ ] **Step 4: Replace bare excepts in `insight.py`** (lines 199, 214)

```python
        except Exception:
            logger.debug("peak-day/hour aggregation failed", exc_info=True)
```
and
```python
        except Exception:
            logger.debug("agency-peak aggregation failed", exc_info=True)
```

Add at top of `insight.py`:

```python
import logging
logger = logging.getLogger(__name__)
```

- [ ] **Step 5: Confirm GREEN + no bare excepts remain**

```bash
cd backend && rtk pytest tests/test_config_overrides_report.py tests/test_config_guard.py -q
rtk grep -rn "except:" app/
```

Expected: tests pass; grep returns no matches.

- [ ] **Step 6: Commit**

```bash
rtk git add -A && rtk git commit -m "fix(config,insight): report override failures; replace bare excepts (BC #5, #6)"
```

---

## Task 7: Scheduler — observable background tasks + per-item timeout (WORK — BC #3)

**Files:** `backend/app/scheduler.py`, `backend/tests/test_scheduler_health.py`

- [ ] **Step 1: Characterize current `agency_chat_item` skip/log behavior**

```bash
cd backend && rtk pytest tests/test_scheduler_health.py -q
```

Expected: passes (baseline). If it imports `agency_chat_item`/`agency_chat_test`, the signatures below preserve them.

- [ ] **Step 2: Replace `create_task` in `start_scheduler`** with `spawn_logged`

```python
from app.concurrency import spawn_logged
# ...
    spawn_logged(agency_chat_test(), name="agency_chat_test:startup")
    spawn_logged(regenerate_brief_job(), name="regenerate_brief_job:startup")
```

- [ ] **Step 3: Add a hard timeout around each agency item**

Wrap the body of `agency_chat_item` so a hung MCP/A2A client cannot pin a semaphore slot. Replace `async with sem:` body entry with:

```python
    async with sem:
        try:
            await asyncio.wait_for(_run_agency_item(agency), timeout=settings.AGENCY_CHAT_TIMEOUT + 5)
        except asyncio.TimeoutError:
            logger.error("agency %s health item timed out", agency.name)
```

Extract the existing tracing+dispatch body into `async def _run_agency_item(agency: Agency) -> None:` (mechanical move; behavior identical except now time-bounded).

- [ ] **Step 4: Confirm GREEN**

```bash
cd backend && rtk pytest tests/test_scheduler_health.py tests/test_concurrency.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
rtk git add -A && rtk git commit -m "fix(scheduler): spawn_logged background jobs; bound each health item (BC #3)"
```

---

## Task 8: Characterize then split `analytics.py` into a package (RIGHT)

**Files:** new `backend/app/services/analytics/{__init__,dashboard,health,brief}.py`, delete-then-shim `backend/app/services/analytics.py`, `backend/tests/services/test_analytics.py`

- [ ] **Step 1: Confirm existing analytics tests are green (characterization baseline)**

```bash
cd backend && rtk pytest tests/services/test_analytics.py -q
```

Expected: pass. Note the imported symbols (`get_dashboard_stats`, `get_agency_health`, `get_executive_summary`, `regenerate_weekly_brief`).

- [ ] **Step 2: Create the package** by moving functions verbatim:
  - `dashboard.py` ← `get_dashboard_stats`
  - `health.py` ← `get_agency_health`
  - `brief.py` ← `regenerate_weekly_brief`, `_latest_brief`, `_compute_executive_metrics`, `_build_brief_prompt`, `get_executive_summary`, `_generate_brief_content`, `_BRIEF_*`

- [ ] **Step 3: `__init__.py` re-exports** so callers (`scheduler.py`, `insight.py`, `routers/dashboard.py`, `routers/executive_summary.py`) keep importing `from app.services.analytics import ...`

```python
from app.services.analytics.brief import (
    get_executive_summary,
    regenerate_weekly_brief,
)
from app.services.analytics.dashboard import get_dashboard_stats
from app.services.analytics.health import get_agency_health

__all__ = [
    "get_dashboard_stats",
    "get_agency_health",
    "get_executive_summary",
    "regenerate_weekly_brief",
]
```

- [ ] **Step 4: Delete the old module file** (the package dir shadows it; remove to avoid ambiguity)

```bash
rm backend/app/services/analytics.py
```

- [ ] **Step 5: Confirm imports + tests**

```bash
cd backend && python -c "from app.services.analytics import get_dashboard_stats, get_agency_health, get_executive_summary, regenerate_weekly_brief; print('ok')"
cd backend && rtk pytest tests/services/test_analytics.py -q
```

Expected: `ok`; tests pass unchanged.

- [ ] **Step 6: Commit**

```bash
rtk git add -A && rtk git commit -m "refactor(analytics): split into dashboard/health/brief package with compat re-exports"
```

---

## Task 9: Split `agencies.py` router into a package (RIGHT)

**Files:** new `backend/app/routers/agencies/{__init__,crud,lifecycle,golden,owners,spec}.py`, delete `backend/app/routers/agencies.py`, modify `backend/app/main.py` (no path change), `backend/tests/test_agencies_router.py`

- [ ] **Step 1: Confirm baseline**

```bash
cd backend && rtk pytest tests/test_agencies_router.py tests/test_agency_owners.py tests/test_agency_status_endpoint.py tests/test_parse_spec_auth.py -q
```

Expected: pass.

- [ ] **Step 2: Create sub-routers**, each `router = APIRouter()` (NO prefix; the package aggregates with the `/agencies` prefix). Distribute the existing handlers verbatim:
  - `spec.py`: `mcp_discover` (`/mcp/discover`), `parse_api_spec` (`/parse-spec`) + `ParseSpecRequest`
  - `owners.py`: `add_agency_owner`, `list_my_agencies` (`/mine`) + `AddOwnerRequest`
  - `lifecycle.py`: `update_agency_status`, `run_agency_conformance`, `test_connection_endpoint` + its response models, `agency_health_history`
  - `golden.py`: golden-question + eval-result handlers and their models, `_get_agency_or_404`
  - `crud.py`: `list_agencies`, `get_agency`, `create_agency`, `replace_agency`, `update_agency`, `delete_agency`, `increment_calls`, `_with_health`

- [ ] **Step 3: `__init__.py` — aggregate preserving registration order**

Order matters: literal/`/mine`/`/mcp/discover` routes must register BEFORE `/{agency_id}`.

```python
from fastapi import APIRouter

from app.routers.agencies import crud, golden, lifecycle, owners, spec

router = APIRouter(prefix="/agencies", tags=["Agencies"])
router.include_router(spec.router)       # /mcp/discover, /parse-spec
router.include_router(owners.router)     # /mine, /{id}/owners
router.include_router(lifecycle.router)  # /{id}/status, /{id}/test, /{id}/health/history, /{id}/conformance
router.include_router(golden.router)     # /{id}/golden-questions, /{id}/eval-results
router.include_router(crud.router)       # /, /{id}  (LAST: catch-all path param)
```

- [ ] **Step 4: Delete the old module; `main.py` import is unchanged** (`from app.routers import agencies` now resolves to the package).

```bash
rm backend/app/routers/agencies.py
```

- [ ] **Step 5: Verify routes unchanged**

```bash
cd backend && python -c "
from app.main import app
paths = sorted({r.path for r in app.routes if '/agencies' in getattr(r, 'path', '')})
print('\n'.join(paths))
"
cd backend && rtk pytest tests/test_agencies_router.py tests/test_agency_owners.py tests/test_agency_status_endpoint.py tests/test_mcp_discover_endpoint.py tests/test_parse_spec_auth.py -q
```

Expected: the same `/api/v1/agencies/...` paths as before; tests pass.

- [ ] **Step 6: Commit**

```bash
rtk git add -A && rtk git commit -m "refactor(agencies): split 549-line router into crud/lifecycle/golden/owners/spec package (paths unchanged)"
```

---

## Task 10: Thin chat.py — fold `/external` and `/stream` saves into `save_turn` (RIGHT)

**Files:** `backend/app/routers/chat.py`, `backend/tests/services/test_chat_turn.py`, `backend/tests/routers/test_chat_*`

- [ ] **Step 1: RED — extend characterization to assert failed status on empty answer**

```python
@pytest.mark.usefixtures("db")
async def test_stream_empty_answer_marks_failed():
    from app.routers.chat import _save_stream_conversation
    from fastapi import BackgroundTasks
    cid = str(__import__("uuid").uuid4())
    await _save_stream_conversation(
        query="q", conversation_id=cid, answer_data={"answer": "", "sections": []},
        session_id=None, total_ms=0, latency_ms=0, user=None, background_tasks=BackgroundTasks(),
    )
    conv = await Conversation.get(id=cid)
    assert conv.status == "failed"   # NEW behavior
```

- [ ] **Step 2: Confirm RED**

```bash
cd backend && rtk pytest tests/services/test_chat_turn.py -q -k empty_answer
```

Expected: fail (currently `success`).

- [ ] **Step 3: Refactor `_save_stream_conversation` and the `/external` save block** to call `save_turn` with `succeeded=bool(answer.strip())` and `background_tasks.add_task(...)` wrapped so failures log. Keep the `ConnectionLog.create(...)` call (it must reference `saved.user_message_id`/`saved.assistant_message_id`). Replace the conn-log status to mirror outcome:

```python
    saved = await save_turn(
        query=query, conversation_id=conversation_id, answer=answer,
        references=answer_data.get("references", []), category=None,
        agency_ids=agency_ids, response_time=response_time, user=user,
        succeeded=bool(answer), external_session_id=session_id, errors=errors,
    )
    await ConnectionLog.create(
        id=str(generate_uuid()), action="query", connection_type="external_chat_v4",
        status="success" if answer else "error", latency_ms=latency_ms,
        detail=sanitize_body(f"v4 stream query: {query[:100]}"),
        request_body=sanitize_body(json.dumps({"query": query, "session_id": conversation_id})),
        response_body=sanitize_body(json.dumps(answer_data, ensure_ascii=False)),
        message_id=saved.user_message_id, assistant_message_id=saved.assistant_message_id,
    )
    background_tasks.add_task(classify_message_category, saved.user_message_id, query, answer)
    background_tasks.add_task(store_embedding, saved.user_message_id, query)
    return saved.assistant_message_id
```

Apply the analogous change to the `/external` (`chat_external`) save block. Delete the now-dead `_save_stream_conversation` internal Conversation create/update branches that `save_turn` now owns.

- [ ] **Step 4: Confirm GREEN**

```bash
cd backend && rtk pytest tests/services/test_chat_turn.py tests/routers/ -q
```

Expected: all pass; `chat.py` now ~250 lines (`wc -l app/routers/chat.py`).

- [ ] **Step 5: Commit**

```bash
rtk git add -A && rtk git commit -m "refactor(chat): route /external and /stream saves through save_turn; failed-status on empty answer"
```

---

## Task 11: public_status N+1 → single grouped query (FAST)

**Files:** `backend/app/routers/public_status.py`, `backend/tests/test_public_status_query_count.py`

- [ ] **Step 1: Characterize values + RED on query count**

```python
"""Query-count characterization for public_status N+1 fix."""
import pytest

from app.models import Agency, ConnectionLog
from app.routers.public_status import public_status


@pytest.mark.usefixtures("db")
async def test_uptime_values_preserved():
    ag = await Agency.create(name="A", status="active")
    for ok in (True, True, True, False):
        await ConnectionLog.create(agency=ag, connection_type="API",
                                   status="success" if ok else "error", action="test")
    rows = await public_status()
    assert rows == [{"name": "A", "status": "active", "uptime_24h_pct": 75.0}]


@pytest.mark.usefixtures("db")
async def test_query_count_is_constant_not_per_agency(monkeypatch):
    for i in range(5):
        ag = await Agency.create(name=f"A{i}", status="active")
        await ConnectionLog.create(agency=ag, connection_type="API", status="success", action="test")

    from tortoise import Tortoise
    conn = Tortoise.get_connection("default")
    calls = {"n": 0}
    orig = conn.execute_query_dict

    async def counting(*a, **k):
        calls["n"] += 1
        return await orig(*a, **k)

    monkeypatch.setattr(conn, "execute_query_dict", counting)
    await public_status()
    assert calls["n"] <= 2   # NOT 2*N
```

- [ ] **Step 2: Confirm RED** (current code does 2 counts per agency, but via ORM `.count()`, not `execute_query_dict`; rewrite uses raw grouped SQL so the counter is meaningful)

```bash
cd backend && rtk pytest tests/test_public_status_query_count.py -q
```

- [ ] **Step 3: Implement** — single grouped query (Postgres `FILTER`; SQLite supports `FILTER` since 3.30, and CI SQLite is newer — guard with a portable `SUM(CASE WHEN ...)`)

```python
"""Public, unauthenticated agency status — name, status, 24h uptime. No internals."""
from datetime import timedelta

from fastapi import APIRouter
from tortoise import Tortoise

from app.models import Agency
from app.utils import now

router = APIRouter(prefix="/public", tags=["Public"])


async def public_status() -> list[dict]:
    cutoff = now() - timedelta(hours=24)
    conn = Tortoise.get_connection("default")
    rows = await conn.execute_query_dict(
        """
        SELECT agency_id,
               COUNT(*) AS total,
               SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS ok
        FROM connection_log
        WHERE created_at >= $1
        GROUP BY agency_id
        """,
        [cutoff],
    )
    counts = {str(r["agency_id"]): (r["total"], r["ok"]) for r in rows}
    out: list[dict] = []
    for ag in await Agency.exclude(status="draft").order_by("name"):
        total, ok = counts.get(str(ag.id), (0, 0))
        uptime = round(ok / total * 100, 1) if total else None
        out.append({"name": ag.name, "status": ag.status.value, "uptime_24h_pct": uptime})
    return out


@router.get("/status", summary="Public agency status")
async def get_public_status() -> list[dict]:
    return await public_status()
```

> Verify the actual table name with `rtk grep -n "table =" app/models/connection_log.py` and substitute it in the SQL.

- [ ] **Step 4: Confirm GREEN**

```bash
cd backend && rtk pytest tests/test_public_status.py tests/test_public_status_query_count.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
rtk git add -A && rtk git commit -m "perf(public-status): replace per-agency N+1 counts with one grouped query"
```

---

## Task 12: similarity 3-query tail → single join (FAST)

**Files:** `backend/app/services/similarity.py`, `backend/tests/services/test_similarity_join.py`

- [ ] **Step 1: Characterize current match identity** (reuse/extend `tests/services/test_similarity.py` patterns) — assert that for a known cached question the returned `(user_msg, assistant_msg, conn_log)` ids are unchanged after the refactor, and that a non-success conversation still yields `None`.

```python
@pytest.mark.usefixtures("db")
async def test_match_resolution_unchanged_after_join(...):
    # build: user msg, assistant child, success conversation, conn_log
    # assert find_similar_question(text-fallback path) returns the same ids
    ...
```

- [ ] **Step 2: Confirm baseline GREEN**

```bash
cd backend && rtk pytest tests/services/test_similarity.py -q
```

- [ ] **Step 3: Implement** — keep `_vector_search`/`_text_fallback_search` returning the matched user `Message`, but replace the three sequential follow-up `Message.get`/`Conversation.get`/`ConnectionLog.get` calls in `find_similar_question` with one ORM query that prefetches: fetch the assistant child and its conn_log filtered to a success conversation. Use a single query joining `messages` (assistant where `parent_id = match.id`) to `connection_log` (`assistant_message_id`) and `conversations` (`status='success'`), returning `None` if no row. Preserve the existing log lines' intent (debug-level).

- [ ] **Step 4: Confirm GREEN**

```bash
cd backend && rtk pytest tests/services/test_similarity.py tests/services/test_similarity_join.py tests/routers/test_chat_cache.py -q
```

Expected: identical match results, fewer round trips.

- [ ] **Step 5: Commit**

```bash
rtk git add -A && rtk git commit -m "perf(similarity): fold post-match lookups into a single join"
```

---

## Task 13: Cached agency directory + router-prompt prefilter (FAST)

**Files:** `backend/app/services/agency_directory.py`, `backend/app/services/chat/graph.py`, cache-invalidation hooks in `routers/agencies/crud.py` + `lifecycle.py`, `backend/tests/services/test_agency_directory.py`

- [ ] **Step 1: RED test** — `backend/tests/services/test_agency_directory.py`

```python
import pytest

from app.models import Agency
from app.services import agency_directory


@pytest.mark.usefixtures("db")
async def test_snapshot_caches_and_invalidates():
    await Agency.create(name="A", status="active")
    agency_directory.invalidate()
    first = await agency_directory.snapshot()
    assert len(first) == 1
    await Agency.create(name="B", status="active")
    cached = await agency_directory.snapshot()
    assert len(cached) == 1          # still cached
    agency_directory.invalidate()
    fresh = await agency_directory.snapshot()
    assert len(fresh) == 2
```

- [ ] **Step 2: Confirm RED**

```bash
cd backend && rtk pytest tests/services/test_agency_directory.py -q
```

- [ ] **Step 3: Implement** — `backend/app/services/agency_directory.py`

```python
"""In-process cached snapshot of active agencies for the chat router prompt.

Invalidated on any agency create/update/delete/status-change (same hooks that
flush the similarity cache). Falls back to a fresh query when the cache is cold
or its TTL has elapsed.
"""
import time

from app.models.agency import Agency

_CACHE_TTL_S = 60.0
_cache: list[dict] | None = None
_loaded_at = 0.0


def invalidate() -> None:
    global _cache, _loaded_at
    _cache = None
    _loaded_at = 0.0


async def snapshot() -> list[dict]:
    global _cache, _loaded_at
    if _cache is not None and (time.monotonic() - _loaded_at) < _CACHE_TTL_S:
        return _cache
    _cache = await Agency.filter(status="active").all().values()
    _loaded_at = time.monotonic()
    return _cache


def prefilter(agencies: list[dict], query: str, *, max_n: int = 25) -> list[dict]:
    """Cheap keyword pre-filter on data_scope before prompt construction.

    Keeps agencies whose name/scope shares a token with the query; if that
    yields fewer than 3 (or nothing matches), fall back to the full list so the
    LLM still makes the final call. Caps the prompt at max_n agencies.
    """
    tokens = {t for t in query.lower().split() if len(t) >= 2}
    if not tokens:
        return agencies[:max_n]
    scored = []
    for ag in agencies:
        hay = (ag.get("name", "") + " " + " ".join(ag.get("data_scope") or [])).lower()
        if any(t in hay for t in tokens):
            scored.append(ag)
    if len(scored) < 3:
        return agencies[:max_n]
    return scored[:max_n]
```

- [ ] **Step 4: Wire into `graph.py`** — make `load_agencies` use the cache and let `build_graph` accept an injectable loader:

```python
from app.services import agency_directory


async def load_agencies(state: AgentState) -> dict:
    agencies = await agency_directory.snapshot()
    return {"agencies": agency_directory.prefilter(agencies, state.query)}
```

Add `agency_loader` param to `build_graph` for test injection (default `load_agencies`). Update `route_query` callers untouched.

- [ ] **Step 5: Add invalidation hooks** in `crud.py` (`create_agency`, `replace_agency`, `update_agency`, `delete_agency`) and `lifecycle.py` (`update_agency_status`) — call `agency_directory.invalidate()` right where `flush_similarity_cache()` is (or after `save`).

- [ ] **Step 6: Confirm GREEN**

```bash
cd backend && rtk pytest tests/services/test_agency_directory.py tests/services/test_chat_graph.py tests/services/test_router_integration.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
rtk git add -A && rtk git commit -m "perf(chat): cache active-agency snapshot and prefilter router prompt"
```

---

## Task 14: Embedding client reuse + TTL cache (FAST)

**Files:** `backend/app/services/embedding.py`, `backend/tests/services/test_embedding_cache.py`, `backend/tests/services/test_embedding.py`

- [ ] **Step 1: Confirm baseline**

```bash
cd backend && rtk pytest tests/services/test_embedding.py -q
```

- [ ] **Step 2: RED test for cache** — `backend/tests/services/test_embedding_cache.py`

```python
import app.services.embedding as emb


async def test_identical_text_hits_cache(monkeypatch):
    emb._cache_clear()
    calls = {"n": 0}

    class FakeResp:
        status_code = 200
        def json(self):
            return {"data": [{"embedding": [0.1] * 384}]}

    class FakeClient:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): ...
        async def post(self, *a, **k):
            calls["n"] += 1
            return FakeResp()

    monkeypatch.setattr(emb.settings, "EMBEDDING_API_KEY", "x")
    monkeypatch.setattr(emb.httpx, "AsyncClient", FakeClient)
    a = await emb.generate_embedding("same text")
    b = await emb.generate_embedding("same text")
    assert a == b
    assert calls["n"] == 1  # second call served from cache
```

- [ ] **Step 3: Confirm RED**

```bash
cd backend && rtk pytest tests/services/test_embedding_cache.py -q
```

- [ ] **Step 4: Implement** — add a small TTL dict cache keyed on `(model, dims, text)` and a `_cache_clear()` test hook to `embedding.py`; keep the 3-attempt retry and `None`-on-failure contract intact. (A module-level shared `httpx.AsyncClient` is optional; the cache is the primary win and keeps the existing test fakes working. Document the trade-off in a comment.)

- [ ] **Step 5: Confirm GREEN**

```bash
cd backend && rtk pytest tests/services/test_embedding.py tests/services/test_embedding_cache.py -q
```

- [ ] **Step 6: Commit**

```bash
rtk git add -A && rtk git commit -m "perf(embedding): TTL-cache identical in-window queries"
```

---

## Task 15: Server-side filter/paginate on list endpoints (FAST — unblocks frontend refactor)

**Files:** `backend/app/routers/conversations.py`, `backend/app/routers/connection_logs.py`, `backend/tests/test_conversations_history.py`, `backend/tests/test_connection_logs_filter.py`

Adds additive query params that push filtering/pagination into the Tortoise ORM (no fetch-all-then-filter). Unblocks `2026-06-23-frontend-refactor` FAST tier (`HistoryPage` server-side filter/paginate + connection-log filters). Characterization-first: pin current unfiltered behavior, confirm green against unchanged code, then add params.

> **Param contract (from spec API/Migration Notes):**
> - `GET /conversations`: add `date_from`, `date_to` (`YYYY-MM-DD`, inclusive, on `created_at`), `page` (default 1), `page_size` (omit → no limit, today's behavior). Response shape unchanged; `total` now = full filtered count.
> - `GET /connection-logs`: add `status` (`success`|`error`), `connection_type` (`MCP`|`API`|`A2A`); accept `page_size` as alias for existing `limit`. `agency_id`/`page`/`limit` already exist.
> All params optional and backward-compatible — omitting them reproduces current behavior.

- [ ] **Step 1: Characterize current behavior** — `backend/tests/test_conversations_history.py` and `backend/tests/test_connection_logs_filter.py`. These pin today's observable behavior and MUST pass against unchanged routers.

```python
# backend/tests/test_conversations_history.py
"""Characterization + new-param tests for GET /conversations history listing.

SQLite-portable (db fixture). Auth is mocked via dependency_overrides.
"""
import uuid
from datetime import timedelta

import pytest

from app.auth.dependencies import get_current_user
from app.main import app
from app.models.conversation import Conversation
from app.models.user import User
from app.utils import now
from httpx import ASGITransport, AsyncClient


def _admin():
    u = User(id=uuid.uuid4(), email="a@x.io", role="admin", is_admin=True)
    return u


async def _client():
    app.dependency_overrides[get_current_user] = _admin
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


@pytest.mark.usefixtures("db")
async def test_history_returns_full_list_when_no_params():
    for i in range(3):
        await Conversation.create(title=f"t{i}", preview="p", status="success", message_count=2)
    async with await _client() as c:
        r = await c.get("/api/v1/conversations")
    app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3                 # CURRENT behavior — pinned
    assert len(body["data"]) == 3


@pytest.mark.usefixtures("db")
async def test_history_search_filter_unchanged():
    await Conversation.create(title="visa renewal", preview="p", status="success", message_count=2)
    await Conversation.create(title="tax return", preview="p", status="success", message_count=2)
    async with await _client() as c:
        r = await c.get("/api/v1/conversations", params={"search": "visa"})
    app.dependency_overrides.clear()
    assert [d["title"] for d in r.json()["data"]] == ["visa renewal"]
```

```python
# backend/tests/test_connection_logs_filter.py
"""Characterization + new-filter tests for GET /connection-logs."""
import uuid

import pytest

from app.auth.dependencies import get_current_user
from app.main import app
from app.models import Agency, ConnectionLog
from app.models.user import User
from httpx import ASGITransport, AsyncClient


def _admin():
    return User(id=uuid.uuid4(), email="a@x.io", role="admin", is_admin=True)


async def _client():
    app.dependency_overrides[get_current_user] = _admin
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


@pytest.mark.usefixtures("db")
async def test_connection_logs_paginate_unchanged():
    ag = await Agency.create(name="A", status="active")
    for _ in range(5):
        await ConnectionLog.create(agency=ag, connection_type="API", status="success", action="test")
    async with await _client() as c:
        r = await c.get("/api/v1/connection-logs", params={"page": 1, "limit": 2})
    app.dependency_overrides.clear()
    body = r.json()
    assert len(body["items"]) == 2            # CURRENT behavior — pinned
    assert body["total_items"] == 5
```

- [ ] **Step 2: Confirm GREEN against unchanged routers**

```bash
cd backend && rtk pytest tests/test_conversations_history.py tests/test_connection_logs_filter.py -q
```

Expected: `3 passed`. (If red, reconcile the tests with reality before editing routers — e.g. the actual `/api/v1` prefix and auth fixture; check `main.py` for the API prefix and `conftest.py` for how other router tests mock `get_current_user`.)

- [ ] **Step 3: RED — add new-param tests** (append to the two files)

```python
# append to test_conversations_history.py
@pytest.mark.usefixtures("db")
async def test_history_paginates_and_reports_full_total():
    for i in range(5):
        await Conversation.create(title=f"t{i}", preview="p", status="success", message_count=2)
    async with await _client() as c:
        r = await c.get("/api/v1/conversations", params={"page": 1, "page_size": 2})
    app.dependency_overrides.clear()
    body = r.json()
    assert len(body["data"]) == 2
    assert body["total"] == 5                 # full filtered count, not page length


@pytest.mark.usefixtures("db")
async def test_history_date_range_filters_in_query():
    old = await Conversation.create(title="old", preview="p", status="success", message_count=2)
    await Conversation.all().filter(id=old.id).update(created_at=now() - timedelta(days=10))
    await Conversation.create(title="new", preview="p", status="success", message_count=2)
    cutoff = (now() - timedelta(days=2)).strftime("%Y-%m-%d")
    async with await _client() as c:
        r = await c.get("/api/v1/conversations", params={"date_from": cutoff})
    app.dependency_overrides.clear()
    assert [d["title"] for d in r.json()["data"]] == ["new"]
```

```python
# append to test_connection_logs_filter.py
@pytest.mark.usefixtures("db")
async def test_status_and_type_filters_apply_to_items_and_stats():
    ag = await Agency.create(name="A", status="active")
    await ConnectionLog.create(agency=ag, connection_type="API", status="success", action="test")
    await ConnectionLog.create(agency=ag, connection_type="API", status="error", action="test")
    await ConnectionLog.create(agency=ag, connection_type="MCP", status="success", action="test")
    async with await _client() as c:
        r = await c.get("/api/v1/connection-logs",
                        params={"status": "success", "connection_type": "API"})
    app.dependency_overrides.clear()
    body = r.json()
    assert len(body["items"]) == 1
    assert body["total_items"] == 1
    assert body["successful_connections"] == 1  # stats reflect the filter too
    assert body["failed_connections"] == 0


@pytest.mark.usefixtures("db")
async def test_page_size_alias_for_limit():
    ag = await Agency.create(name="A", status="active")
    for _ in range(4):
        await ConnectionLog.create(agency=ag, connection_type="API", status="success", action="test")
    async with await _client() as c:
        r = await c.get("/api/v1/connection-logs", params={"page_size": 2})
    app.dependency_overrides.clear()
    assert len(r.json()["items"]) == 2
```

- [ ] **Step 4: Confirm RED**

```bash
cd backend && rtk pytest tests/test_conversations_history.py tests/test_connection_logs_filter.py -q
```

Expected: the four new tests fail (params ignored: full list returned / `total` = page length / filters not applied / `page_size` unknown query rejected or ignored).

- [ ] **Step 5: Implement conversations params** — `backend/app/routers/conversations.py`. Replace the `list_conversations` signature and the query-build/return block (current lines ~80-122). Filtering is pushed into the ORM `qs`; pagination uses `offset`/`limit`; `total` is `await qs.count()` before slicing.

```python
from datetime import datetime, timedelta


@router.get("", summary="List conversations (history)")
async def list_conversations(
    search: str = Query("", description="Search in title or preview"),
    filter_agency: str = Query("", alias="filterAgency", description="Filter by agency name"),
    date_from: str | None = Query(None, description="Inclusive start date YYYY-MM-DD"),
    date_to: str | None = Query(None, description="Inclusive end date YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1, le=200, description="Omit for full list (legacy)"),
    user: User = Depends(get_current_user),
) -> HistoryResponse:
    start = time.time()

    qs = Conversation.all()
    if not (user.is_admin or user.role == "auditor"):
        qs = qs.filter(user_id=user.id)
    if search:
        qs = qs.filter(title__icontains=search)
    if filter_agency:
        qs = qs.filter(agencies__contains=filter_agency)
    if date_from:
        try:
            qs = qs.filter(created_at__gte=datetime.strptime(date_from, "%Y-%m-%d"))
        except ValueError:
            raise HTTPException(status_code=400, detail="date_from must be YYYY-MM-DD")
    if date_to:
        try:
            end = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            qs = qs.filter(created_at__lt=end)
        except ValueError:
            raise HTTPException(status_code=400, detail="date_to must be YYYY-MM-DD")

    total = await qs.count()

    page_qs = qs.order_by("-created_at")
    if page_size is not None:
        page_qs = page_qs.offset((page - 1) * page_size).limit(page_size)
    convs = await page_qs

    items = [
        HistoryItem(
            id=str(c.id),
            title=c.title,
            preview=c.preview or "",
            date=c.created_at.strftime("%Y-%m-%d"),
            agencies=[],
            status=c.status,
            message_count=c.message_count or 0,
            response_time=c.response_time or "",
        )
        for c in convs
    ]

    return HistoryResponse(
        success=True,
        data=items,
        total=total,
        response_time=int((time.time() - start) * 1000),
    )
```

> Note: when `page_size` is omitted, `page_qs` has no offset/limit, so the full ordered list is returned exactly as today; `total` equals `len(items)` in that case, matching the old `total=len(items)`.

- [ ] **Step 6: Implement connection-logs filters** — `backend/app/routers/connection_logs.py`. Add `status`, `connection_type`, and a `page_size` alias to the `list_connection_logs` signature, and apply the two new filters to `qs` *before* the stats counts so totals stay consistent.

```python
async def list_connection_logs(
    search: str | None = Query(None, description="Search in detail"),
    agency_id: str | None = Query(None, description="Filter by agency ID"),
    status_filter: str | None = Query(None, alias="status", description="success | error"),
    connection_type: str | None = Query(None, description="MCP | API | A2A"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100, alias="page_size"),
    user: User = Depends(get_current_user),
) -> ListConnectionLogResponse:
```

Then after the existing `agency_id` block (current line ~78), add:

```python
    if status_filter:
        qs = qs.filter(status=status_filter)
    if connection_type:
        qs = qs.filter(connection_type=connection_type)
```

> `limit` keeps its name internally (offset/limit math, `page_size=limit` in the response) — only its query alias becomes `page_size`. FastAPI accepts the param under the alias; existing callers passing `limit` keep working only if a non-aliased param is also desired, so verify current callers: `rtk grep -rn "connection-logs" frontend/src backend/tests` to confirm whether any client still sends `limit`. If so, keep `limit` as the canonical name and add `page_size` via a separate optional param that overrides it:
> ```python
>     limit: int = Query(20, ge=1, le=100),
>     page_size: int | None = Query(None, ge=1, le=100),
>     # ...
>     effective_limit = page_size if page_size is not None else limit
> ```
> Use whichever matches the grep result; the test in Step 3 only requires `page_size` to work.

- [ ] **Step 7: Confirm GREEN**

```bash
cd backend && rtk pytest tests/test_conversations_history.py tests/test_connection_logs_filter.py -q
```

Expected: all pass (characterization + new params).

- [ ] **Step 8: Format, lint, commit**

```bash
cd backend && python -m black app/routers/conversations.py app/routers/connection_logs.py 2>/dev/null || true
rtk git add -A && rtk git commit -m "perf(history,connection-logs): server-side date/status/type filters + pagination (additive; unblocks frontend refactor)"
```

---

## Task 16: DB indexes + pool sizing migration (FAST)

**Files:** `backend/app/config.py`, `backend/migrations/models/*`, aerich

- [ ] **Step 1: Add pool config** to `config.py`

```python
    # ── Database pool ────────────────────────────────────────────────────────
    DB_POOL_MIN: int = 1
    DB_POOL_MAX: int = 10
```

and thread into `TORTOISE_ORM`'s connection (use the dict form with `credentials`/`minsize`/`maxsize` as supported by the asyncpg client). Verify the app still boots:

```bash
cd backend && python -c "from app.config import TORTOISE_ORM; print(TORTOISE_ORM['connections'])"
```

- [ ] **Step 2: Generate the index migration**

```bash
cd backend && rtk proxy aerich migrate --name backend_refactor_indexes
```

Edit the generated migration to add (forward) / drop (downgrade):

```sql
CREATE INDEX IF NOT EXISTS idx_connlog_agency_created ON connection_log (agency_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_role_created ON messages (role, created_at);
```

- [ ] **Step 3: Verify migration applies on a throwaway DB** (or in the Postgres CI job)

```bash
cd backend && rtk proxy aerich upgrade && echo OK
```

Expected: `OK`. (Skip locally if no Postgres; rely on CI.)

- [ ] **Step 4: Commit**

```bash
rtk git add -A && rtk git commit -m "perf(db): configurable pool sizing + indexes for status/analytics/heatmap queries"
```

---

## Task 17: analytics.get_agency_health grouped query + MCP id defaulting (RIGHT/FAST cleanup)

**Files:** `backend/app/services/analytics/health.py`, `backend/app/mcp/server.py`, `backend/tests/services/test_analytics.py`, `backend/tests/test_mcp_role_access.py`

- [ ] **Step 1: Characterize `get_agency_health` output** for a 2-agency fixture (uptime, latency, errorRate) so the grouped rewrite is provably value-preserving. Confirm green against current code first.

```bash
cd backend && rtk pytest tests/services/test_analytics.py -q -k health
```

- [ ] **Step 2: Rewrite the per-agency loop** as grouped aggregates keyed by `agency_id` (one query per window: current-latency window, 7d latency, 7d error rate, day count), then assemble `AgencyHealth` rows in Python from the lookup dicts. Postgres-only SQL is fine here (this module is the Postgres path; `agency_health.py` remains the SQLite-portable one).

- [ ] **Step 3: Fix MCP id defaulting** in `mcp/server.py:_fetch_agencies` — resolve `user_id` and `conversation_id` ONCE before the payload loop so every `__user_id__`/`__conversation_id__` placeholder in one response uses the same value:

```python
    resolved_user_id = str(await ctx.get_state("user_id") or generate_uuid())
    resolved_conversation_id = str(await ctx.get_state("conversation_id") or generate_uuid())
    # ...inside the expected_payload loop, replace with resolved_* (no per-key generate_uuid)
```

- [ ] **Step 4: Confirm GREEN**

```bash
cd backend && rtk pytest tests/services/test_analytics.py tests/test_mcp_role_access.py tests/test_mcp_streamable_calls.py -q
```

- [ ] **Step 5: Commit**

```bash
rtk git add -A && rtk git commit -m "perf(analytics): grouped agency-health query; fix(mcp): per-request id defaulting"
```

---

## Task 18: Full-suite verification + PR into dev

**Files:** none (verification only)

- [ ] **Step 1: Run the whole backend suite**

```bash
cd backend && rtk pytest -q
```

Expected: all green. Investigate any failure with superpowers:systematic-debugging before proceeding.

- [ ] **Step 2: Lint/format**

```bash
cd backend && python -m black app/ tests/ && python -m ruff check app/ tests/ 2>/dev/null || true
```

- [ ] **Step 3: Confirm no regressions in measured sizes / no bare excepts**

```bash
cd backend && wc -l app/routers/chat.py app/routers/agencies/__init__.py app/services/analytics/__init__.py
rtk grep -rn "except:" app/
rtk grep -rn "asyncio.create_task" app/   # should only appear inside spawn_logged, if at all
```

Expected: `chat.py` ~250; no bare excepts; no raw `create_task`.

- [ ] **Step 4: Verify behavior-change docs are reflected** — confirm the spec's Behavior Changes #1–#7 each have a corresponding test (grep test names).

```bash
cd backend && rtk grep -rln "failed\|degrade\|override\|invalid_json\|spawn_logged" tests/
```

- [ ] **Step 5: Push and open PR into `dev`** (never into `main` directly)

```bash
rtk git push -u origin refactor/backend-work-right-fast
rtk gh pr create --base dev --title "refactor(backend): work → right → fast (correctness, decomposition, perf)" \
  --body "$(cat <<'EOF'
## What
Applies make-it-work → right → fast to backend/app:
- WORK: transactional save_turn + failed-status, router JSON validation, spawn_logged fire-and-forget, rate-limit degrade-to-inprocess, apply_overrides reporting, bare-except removal, bounded health items.
- RIGHT: split agencies.py and analytics.py into packages; thin chat.py; injectable graph loader; MCP id defaulting.
- FAST: public_status grouped query, similarity single join, cached/prefiltered router prompt, embedding cache, DB indexes + pool sizing, grouped agency-health.

## Behavior changes
See docs/superpowers/specs/2026-06-23-backend-refactor-design.md → Behavior Changes. Conversation status may now be "failed" (visible via GET /conversations); no /api path/shape changes.

## Testing
Characterization-first per module; full `pytest` green. Postgres-only paths exercised in CI.
EOF
)"
```

- [ ] **Step 6: Confirm CI green**

```bash
rtk gh pr checks
```

Expected: all checks pass; address failures before requesting review (superpowers:requesting-code-review).
