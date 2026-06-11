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
