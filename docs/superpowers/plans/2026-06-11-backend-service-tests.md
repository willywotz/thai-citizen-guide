# Backend Service-Layer Test Coverage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add unit tests for the four untested `app/services/` modules (`chat/graph.py`, `similarity.py`, `embedding.py`, `analytics.py`) extracted by the preceding service-layer refactor.

**Architecture:** Pure unit tests with `pytest-asyncio` (`asyncio_mode = "auto"`). All external dependencies — `httpx.AsyncClient`, `call_llm`, Tortoise ORM model calls, raw `conn.execute_query_dict`, and `in_transaction` — are mocked with `unittest.mock`. No live database. These are **characterization tests**: they assert the *current* behavior of existing code, so each test should PASS on first run. A failure means a real bug was found — investigate and report it, do not silently change production code.

**Tech Stack:** Python 3.12, pytest, pytest-asyncio, unittest.mock. Run with the backend venv interpreter: `.venv/bin/python -m pytest` (the `rtk` hook cannot find `pytest` on PATH).

---

## Conventions (read once)

- All commands run from `backend/`.
- Test runner: `.venv/bin/python -m pytest <path> -v`
- Patch `httpx.AsyncClient` at its use site, e.g. `patch("app.services.embedding.httpx.AsyncClient")`.
- Patch settings values with `patch.object(settings, "NAME", value)`.
- `asyncio_mode = "auto"` is set, but keep the `@pytest.mark.asyncio` marker on async tests for consistency with existing files.
- Import the function-under-test *inside* each test function, matching the existing style in `tests/services/test_chat_llm.py`.
- Commit with `rtk git`.

---

## File Map

**Created:**
- `backend/tests/services/test_chat_graph.py` — tests for `services/chat/graph.py`
- `backend/tests/services/test_similarity.py` — tests for `services/similarity.py`
- `backend/tests/services/test_embedding.py` — tests for `services/embedding.py`
- `backend/tests/services/test_analytics.py` — tests for `services/analytics.py`

**Modified:** none (no production code changes).

---

## Task 1: Tests for `services/chat/graph.py`

**Files:**
- Create: `backend/tests/services/test_chat_graph.py`

- [ ] **Step 1: Write the test file**

Create `backend/tests/services/test_chat_graph.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_should_dispatch_with_routes():
    from app.services.chat.graph import AgentState, should_dispatch

    state = AgentState(routes=[{"agency_id": "a1"}])
    assert should_dispatch(state) == "dispatch"


def test_should_dispatch_without_routes():
    from app.services.chat.graph import AgentState, should_dispatch

    state = AgentState(routes=[])
    assert should_dispatch(state) == "synthesize"


def test_build_graph_compiles():
    from app.services.chat.graph import build_graph

    assert build_graph() is not None


@pytest.mark.asyncio
async def test_route_query_strips_think_and_fences_and_enriches():
    from app.services.chat.graph import AgentState, route_query

    state = AgentState(
        query="ภาษีรถ",
        agencies=[
            {
                "id": "a1",
                "name": "กรมขนส่ง",
                "description": "d",
                "connection_type": "API",
                "endpoint_url": "http://x",
                "expected_payload": {"q": "__query__"},
                "data_scope": [],
            }
        ],
    )
    llm_content = (
        '<think>reasoning</think>```json\n'
        '{"routes": [{"agency_id": "a1", "agency_name": "กรมขนส่ง", '
        '"connection_type": "API", "sub_question": "ค่าธรรมเนียม"}]}\n```'
    )

    with patch("app.services.chat.graph.call_llm", new=AsyncMock(return_value={"content": llm_content})):
        result = await route_query(state)

    routes = result["routes"]
    assert len(routes) == 1
    assert routes[0]["endpoint_url"] == "http://x"
    assert routes[0]["expected_payload"] == {"q": "__query__"}


@pytest.mark.asyncio
async def test_dispatch_a2a_posts_and_returns_ok():
    from app.services.chat.graph import AgentState, dispatch_to_agencies

    state = AgentState(routes=[{
        "connection_type": "A2A", "sub_question": "q",
        "agency_name": "A", "endpoint_url": "http://x",
    }])
    mock_response = MagicMock()
    mock_response.json.return_value = {"answer": "ok"}

    with patch("app.services.chat.graph.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await dispatch_to_agencies(state)

    res = result["results"][0]
    assert res["status"] == "ok"
    assert res["response"] == {"answer": "ok"}
    assert res["agency"] == "A"


@pytest.mark.asyncio
async def test_dispatch_api_returns_not_implemented_error():
    # NOTE: characterizes current (stub) behavior — API dispatch is a TODO.
    # Sub-project #2 will replace this; this test is its regression safety net.
    from app.services.chat.graph import AgentState, dispatch_to_agencies

    state = AgentState(routes=[{
        "connection_type": "API", "sub_question": "q",
        "agency_name": "A", "endpoint_url": "http://x",
    }])
    result = await dispatch_to_agencies(state)
    res = result["results"][0]
    assert res["status"] == "error"
    assert "not yet implemented" in res["response"]


@pytest.mark.asyncio
async def test_dispatch_mcp_returns_not_implemented_error():
    # NOTE: characterizes current (stub) behavior — MCP dispatch is a TODO.
    from app.services.chat.graph import AgentState, dispatch_to_agencies

    state = AgentState(routes=[{
        "connection_type": "MCP", "sub_question": "q",
        "agency_name": "A", "endpoint_url": "http://x",
    }])
    result = await dispatch_to_agencies(state)
    res = result["results"][0]
    assert res["status"] == "error"
    assert "not yet implemented" in res["response"]


@pytest.mark.asyncio
async def test_dispatch_unknown_connection_type():
    from app.services.chat.graph import AgentState, dispatch_to_agencies

    state = AgentState(routes=[{
        "connection_type": "FOO", "sub_question": "q",
        "agency_name": "A", "endpoint_url": "http://x",
    }])
    result = await dispatch_to_agencies(state)
    res = result["results"][0]
    assert res["status"] == "error"
    assert "Unknown connection_type: FOO" in res["response"]


@pytest.mark.asyncio
async def test_synthesize_empty_results_returns_not_found():
    from app.services.chat.graph import AgentState, synthesize

    result = await synthesize(AgentState(results=[]))
    assert result["final_answer"] == "ไม่พบหน่วยงานที่เกี่ยวข้องกับคำถามของคุณ"


@pytest.mark.asyncio
async def test_synthesize_calls_llm_and_trims():
    from app.services.chat.graph import AgentState, synthesize

    state = AgentState(query="q", results=[{"agency": "A", "response": "info"}])
    with patch("app.services.chat.graph.call_llm", new=AsyncMock(return_value={"content": "  คำตอบ  "})):
        result = await synthesize(state)
    assert result["final_answer"] == "คำตอบ"
```

- [ ] **Step 2: Run the test file**

Run: `.venv/bin/python -m pytest tests/services/test_chat_graph.py -v`
Expected: all 10 tests PASS. (If any FAIL, a real bug or a wrong assumption was found — stop and report it, do not edit production code.)

- [ ] **Step 3: Commit**

```bash
rtk git add backend/tests/services/test_chat_graph.py
rtk git commit -m "test: add unit tests for services/chat/graph.py"
```

---

## Task 2: Tests for `services/similarity.py`

**Files:**
- Create: `backend/tests/services/test_similarity.py`

- [ ] **Step 1: Write the test file**

Create `backend/tests/services/test_similarity.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_find_similar_uses_vector_search_when_embedding_present():
    from app.services import similarity

    match_msg = MagicMock(id="m1", conversation_id="c1")
    assistant = MagicMock(id="a1")
    conv = MagicMock(id="c1", status="success")
    conn_log = MagicMock()

    with patch.object(similarity, "_vector_search", new=AsyncMock(return_value=match_msg)) as mvec, \
         patch.object(similarity, "_text_fallback_search", new=AsyncMock()) as mtext, \
         patch.object(similarity, "Message") as MockMessage, \
         patch.object(similarity, "Conversation") as MockConv, \
         patch.object(similarity, "ConnectionLog") as MockCL:
        MockMessage.get = AsyncMock(return_value=assistant)
        MockConv.get = AsyncMock(return_value=conv)
        MockCL.get = AsyncMock(return_value=conn_log)
        result = await similarity.find_similar_question("q", embedding=[0.1, 0.2])

    mvec.assert_awaited_once()
    mtext.assert_not_awaited()
    assert result == (match_msg, assistant, conn_log)


@pytest.mark.asyncio
async def test_find_similar_uses_text_fallback_when_no_embedding():
    from app.services import similarity

    with patch.object(similarity, "_vector_search", new=AsyncMock()) as mvec, \
         patch.object(similarity, "_text_fallback_search", new=AsyncMock(return_value=None)) as mtext:
        result = await similarity.find_similar_question("q", embedding=None)

    mtext.assert_awaited_once()
    mvec.assert_not_awaited()
    assert result is None


@pytest.mark.asyncio
async def test_find_similar_returns_none_when_no_assistant():
    from app.services import similarity

    match_msg = MagicMock(id="m1", conversation_id="c1")
    with patch.object(similarity, "_vector_search", new=AsyncMock(return_value=match_msg)), \
         patch.object(similarity, "Message") as MockMessage:
        MockMessage.get = AsyncMock(side_effect=Exception("not found"))
        result = await similarity.find_similar_question("q", embedding=[0.1])

    assert result is None


@pytest.mark.asyncio
async def test_find_similar_returns_none_when_conversation_not_success():
    from app.services import similarity

    match_msg = MagicMock(id="m1", conversation_id="c1")
    assistant = MagicMock(id="a1")
    conv = MagicMock(id="c1", status="error")
    with patch.object(similarity, "_vector_search", new=AsyncMock(return_value=match_msg)), \
         patch.object(similarity, "Message") as MockMessage, \
         patch.object(similarity, "Conversation") as MockConv:
        MockMessage.get = AsyncMock(return_value=assistant)
        MockConv.get = AsyncMock(return_value=conv)
        result = await similarity.find_similar_question("q", embedding=[0.1])

    assert result is None


@pytest.mark.asyncio
async def test_find_similar_returns_none_when_conn_log_missing():
    from app.services import similarity

    match_msg = MagicMock(id="m1", conversation_id="c1")
    assistant = MagicMock(id="a1")
    conv = MagicMock(id="c1", status="success")
    with patch.object(similarity, "_vector_search", new=AsyncMock(return_value=match_msg)), \
         patch.object(similarity, "Message") as MockMessage, \
         patch.object(similarity, "Conversation") as MockConv, \
         patch.object(similarity, "ConnectionLog") as MockCL:
        MockMessage.get = AsyncMock(return_value=assistant)
        MockConv.get = AsyncMock(return_value=conv)
        MockCL.get = AsyncMock(side_effect=Exception("not found"))
        result = await similarity.find_similar_question("q", embedding=[0.1])

    assert result is None


@pytest.mark.asyncio
async def test_text_fallback_similarity_only():
    from app.config import settings
    from app.services import similarity

    sentinel = MagicMock()
    with patch.object(settings, "SIMILARITY_FALLBACK", "similarity"), \
         patch.object(similarity, "_similarity_search", new=AsyncMock(return_value=sentinel)) as msim, \
         patch.object(similarity, "_levenshtein_search", new=AsyncMock()) as mlev:
        result = await similarity._text_fallback_search("q", 0.9, None)

    assert result is sentinel
    msim.assert_awaited_once()
    mlev.assert_not_awaited()


@pytest.mark.asyncio
async def test_text_fallback_both_falls_through_to_levenshtein():
    from app.config import settings
    from app.services import similarity

    sentinel = MagicMock()
    with patch.object(settings, "SIMILARITY_FALLBACK", "both"), \
         patch.object(similarity, "_similarity_search", new=AsyncMock(return_value=None)) as msim, \
         patch.object(similarity, "_levenshtein_search", new=AsyncMock(return_value=sentinel)) as mlev:
        result = await similarity._text_fallback_search("q", 0.9, None)

    assert result is sentinel
    msim.assert_awaited_once()
    mlev.assert_awaited_once()


@pytest.mark.asyncio
async def test_levenshtein_search_computes_max_distance():
    from app.services import similarity

    mock_conn = MagicMock()
    mock_conn.execute_query_dict = AsyncMock(return_value=[])
    query = "x" * 100  # max(1, int(100 * (1 - 0.95))) == 5

    with patch.object(similarity.Tortoise, "get_connection", return_value=mock_conn):
        result = await similarity._levenshtein_search(query, 0.95, None)

    assert result is None
    params = mock_conn.execute_query_dict.call_args[0][1]
    assert params[3] == 5


@pytest.mark.asyncio
async def test_levenshtein_search_returns_none_on_extension_error():
    from app.services import similarity

    mock_conn = MagicMock()
    mock_conn.execute_query_dict = AsyncMock(side_effect=Exception("function levenshtein does not exist"))

    with patch.object(similarity.Tortoise, "get_connection", return_value=mock_conn):
        result = await similarity._levenshtein_search("hello world", 0.95, None)

    assert result is None
```

- [ ] **Step 2: Run the test file**

Run: `.venv/bin/python -m pytest tests/services/test_similarity.py -v`
Expected: all 9 tests PASS. (If any FAIL, report the discrepancy — do not change production code.)

- [ ] **Step 3: Commit**

```bash
rtk git add backend/tests/services/test_similarity.py
rtk git commit -m "test: add unit tests for services/similarity.py"
```

---

## Task 3: Tests for `services/embedding.py`

**Files:**
- Create: `backend/tests/services/test_embedding.py`

- [ ] **Step 1: Write the test file**

Create `backend/tests/services/test_embedding.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


@pytest.mark.asyncio
async def test_generate_embedding_no_key_returns_none():
    from app.config import settings
    from app.services.embedding import generate_embedding

    with patch.object(settings, "EMBEDDING_API_KEY", ""):
        result = await generate_embedding("hello")
    assert result is None


@pytest.mark.asyncio
async def test_generate_embedding_success():
    from app.config import settings
    from app.services.embedding import generate_embedding

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    with patch.object(settings, "EMBEDDING_API_KEY", "key"), \
         patch("app.services.embedding.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await generate_embedding("hello")

    assert result == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_generate_embedding_non_200_retries_three_times():
    from app.config import settings
    from app.services.embedding import generate_embedding

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "err"

    with patch.object(settings, "EMBEDDING_API_KEY", "key"), \
         patch("app.services.embedding.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await generate_embedding("hello")

    assert result is None
    assert mock_client.post.await_count == 3


@pytest.mark.asyncio
async def test_generate_embedding_timeout_retries_three_times():
    from app.config import settings
    from app.services.embedding import generate_embedding

    with patch.object(settings, "EMBEDDING_API_KEY", "key"), \
         patch("app.services.embedding.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await generate_embedding("hello")

    assert result is None
    assert mock_client.post.await_count == 3


def test_encode_embedding_returns_json_string():
    from app.services.embedding import encode_embedding

    assert encode_embedding([1.0, 2.0]) == "[1.0, 2.0]"


def test_encode_decode_roundtrip():
    from app.services.embedding import decode_embedding, encode_embedding

    vec = [0.1, 0.2, 0.3]
    assert decode_embedding(encode_embedding(vec)) == vec
```

- [ ] **Step 2: Run the test file**

Run: `.venv/bin/python -m pytest tests/services/test_embedding.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 3: Commit**

```bash
rtk git add backend/tests/services/test_embedding.py
rtk git commit -m "test: add unit tests for services/embedding.py"
```

---

## Task 4: Tests for `services/analytics.py`

**Files:**
- Create: `backend/tests/services/test_analytics.py`

This module is heavy raw-SQL / ORM aggregation, so coverage is intentionally shallow:
shape assertions for `get_dashboard_stats`, smoke tests for the other two. Two helpers
mock the Tortoise queryset chain and the `in_transaction` async context manager.

- [ ] **Step 1: Write the test file**

Create `backend/tests/services/test_analytics.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _AsyncCM:
    """Stand-in for `async with in_transaction() as conn`."""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args):
        return False


def _make_query_mock(count_values=None, values_values=None):
    """Chainable Tortoise queryset mock.

    filter/annotate/group_by return self; count/values pop from the provided lists.
    """
    m = MagicMock()
    m.filter.return_value = m
    m.annotate.return_value = m
    m.group_by.return_value = m
    m.count = AsyncMock(side_effect=list(count_values or []))
    m.values = AsyncMock(side_effect=list(values_values or []))
    return m


@pytest.mark.asyncio
async def test_get_dashboard_stats_shape():
    from app.services import analytics

    conn = MagicMock()
    conn.execute_query = AsyncMock()
    conn.execute_query_dict = AsyncMock(return_value=[{"dow": 1, "questions": 4}])

    # Message: count x2 (total, today), values x3 (avg_time, rate, categories)
    msg = _make_query_mock(
        count_values=[5, 2],
        values_values=[
            [{"avg_time": 1500}],
            [{"rate": 80}],
            [{"category": "x", "cnt": 3}],
        ],
    )
    agency = MagicMock()
    agency.all.return_value = MagicMock(
        values=AsyncMock(return_value=[{"name": "A", "color": "#fff", "total_calls": 10}])
    )

    with patch.object(analytics, "in_transaction", return_value=_AsyncCM(conn)), \
         patch.object(analytics, "Message", msg), \
         patch.object(analytics, "Agency", agency):
        result = await analytics.get_dashboard_stats()

    assert set(result.keys()) == {"stats", "agencyUsage", "weeklyTrend", "categoryData"}
    assert len(result["weeklyTrend"]) == 7
    assert result["stats"]["totalQuestions"] == 5
    assert result["stats"]["todayQuestions"] == 2
    assert result["agencyUsage"] == [{"name": "A", "value": 10, "fill": "#fff"}]
    assert result["categoryData"] == [{"category": "x", "count": 3}]


@pytest.mark.asyncio
async def test_get_agency_health_empty_agencies():
    from app.schemas.insight import AgencyHealthData
    from app.services import analytics

    conn = MagicMock()
    conn.execute_query = AsyncMock()

    agency = MagicMock()
    agency.all.return_value = MagicMock(values=AsyncMock(return_value=[]))

    conn_log = MagicMock()
    conn_log.annotate.return_value = conn_log
    conn_log.filter.return_value = conn_log
    conn_log.group_by.return_value = conn_log
    conn_log.values = AsyncMock(return_value=[])

    with patch.object(analytics, "in_transaction", return_value=_AsyncCM(conn)), \
         patch.object(analytics, "Agency", agency), \
         patch.object(analytics, "ConnectionLog", conn_log):
        result = await analytics.get_agency_health()

    assert isinstance(result, AgencyHealthData)
    assert result.agencies == []
    assert result.historical == []


@pytest.mark.asyncio
async def test_get_executive_summary_smoke():
    from app.schemas.executive_summary import ExecutiveData
    from app.services import analytics

    conn = MagicMock()
    conn.execute_query = AsyncMock()

    msg = MagicMock()
    msg.filter.return_value = msg
    msg.annotate.return_value = msg
    msg.group_by.return_value = msg
    msg.count = AsyncMock(return_value=0)
    msg.values = AsyncMock(return_value=[])

    conv = MagicMock()
    conv.filter.return_value = conv
    conv.count = AsyncMock(return_value=0)

    with patch.object(analytics, "in_transaction", return_value=_AsyncCM(conn)), \
         patch.object(analytics, "Message", msg), \
         patch.object(analytics, "Conversation", conv), \
         patch.object(analytics, "_get_weekly_brief", new=AsyncMock(return_value="brief")):
        result = await analytics.get_executive_summary()

    assert isinstance(result, ExecutiveData)
    assert result.weeklyBrief == "brief"
```

- [ ] **Step 2: Run the test file**

Run: `.venv/bin/python -m pytest tests/services/test_analytics.py -v`
Expected: all 3 tests PASS. If the dashboard test fails on the chained-mock call order, re-read `get_dashboard_stats` and adjust the `count_values` / `values_values` ordering to match the actual sequence of `.count()` / `.values()` calls — this is a test-mock fix, not a production change.

- [ ] **Step 3: Commit**

```bash
rtk git add backend/tests/services/test_analytics.py
rtk git commit -m "test: add unit tests for services/analytics.py"
```

---

## Task 5: Full-suite verification

- [ ] **Step 1: Run the entire test suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all tests pass — the original 12 plus the new 28 (10 + 9 + 6 + 3) = **40 tests**.

- [ ] **Step 2: Confirm app still imports**

Run: `.venv/bin/python -c "from app.main import app; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Report any bugs surfaced**

If any characterization test could not be made to pass against current behavior, write up the discrepancy (file, function, expected vs actual) for the future bug-hunt sub-project. Do not fix production code in this plan.

- [ ] **Step 4: Invoke finishing skill**

Use `superpowers:finishing-a-development-branch` to decide how to integrate the branch.
```
