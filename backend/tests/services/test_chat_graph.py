from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import asyncio


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
    assert routes[0]["sub_question"] == "ค่าธรรมเนียม"
    assert routes[0]["agency_name"] == "กรมขนส่ง"
    assert routes[0]["api_headers"] == []


@pytest.mark.asyncio
async def test_route_query_enriches_api_headers_from_agency():
    from app.services.chat.graph import AgentState, route_query

    state = AgentState(
        query="ภาษี",
        agencies=[
            {
                "id": "a1",
                "name": "กรมสรรพากร",
                "description": "d",
                "connection_type": "API",
                "endpoint_url": "http://x",
                "expected_payload": {},
                "api_headers": [{"name": "X-Key", "value": "secret"}],
                "data_scope": [],
            }
        ],
    )
    llm_content = (
        '{"routes": [{"agency_id": "a1", "agency_name": "กรมสรรพากร", '
        '"connection_type": "API", "sub_question": "ภาษีมูลค่าเพิ่ม"}]}'
    )

    with patch("app.services.chat.graph.call_llm", new=AsyncMock(return_value={"content": llm_content})):
        result = await route_query(state)

    routes = result["routes"]
    assert routes[0]["api_headers"] == [{"name": "X-Key", "value": "secret"}]


@pytest.mark.asyncio
async def test_dispatch_to_agencies_calls_dispatch_one_per_route():
    from app.services.chat.graph import AgentState, dispatch_to_agencies

    routes = [
        {"connection_type": "A2A", "sub_question": "q1", "agency_name": "A", "endpoint_url": "http://a"},
        {"connection_type": "API", "sub_question": "q2", "agency_name": "B", "endpoint_url": "http://b"},
    ]
    state = AgentState(routes=routes, conversation_id="conv-test")

    call_log = []

    async def fake_dispatch_one(route, conversation_id):
        call_log.append((route["agency_name"], conversation_id))
        return {"agency": route["agency_name"], "response": "ok", "status": "ok"}

    with patch("app.services.chat.graph.dispatch_one", side_effect=fake_dispatch_one):
        result = await dispatch_to_agencies(state)

    assert len(result["results"]) == 2
    assert {r["agency"] for r in result["results"]} == {"A", "B"}
    assert call_log == [("A", "conv-test"), ("B", "conv-test")]


@pytest.mark.asyncio
async def test_dispatch_api_real_path_returns_ok():
    from app.services.chat.graph import AgentState, dispatch_to_agencies

    state = AgentState(
        routes=[{
            "connection_type": "API", "sub_question": "q",
            "agency_name": "A", "endpoint_url": "http://x",
            "api_headers": None, "expected_payload": {},
        }],
        conversation_id="c1",
    )

    with patch("app.services.chat.graph.dispatch_one", new=AsyncMock(
        return_value={"agency": "A", "response": {"data": "result"}, "status": "ok"}
    )):
        result = await dispatch_to_agencies(state)

    assert result["results"][0]["status"] == "ok"
    assert result["results"][0]["response"] == {"data": "result"}


@pytest.mark.asyncio
async def test_dispatch_mcp_real_path_returns_ok():
    from app.services.chat.graph import AgentState, dispatch_to_agencies

    state = AgentState(
        routes=[{
            "connection_type": "MCP", "sub_question": "q",
            "agency_name": "A", "endpoint_url": "http://x",
        }],
        conversation_id="c1",
    )

    with patch("app.services.chat.graph.dispatch_one", new=AsyncMock(
        return_value={"agency": "A", "response": "mcp text", "status": "ok"}
    )):
        result = await dispatch_to_agencies(state)

    assert result["results"][0]["status"] == "ok"
    assert result["results"][0]["response"] == "mcp text"


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


@pytest.mark.asyncio
async def test_route_query_invalid_json_yields_no_routes(monkeypatch):
    import app.services.chat.graph as g
    from app.services.chat.graph import AgentState, route_query

    async def fake_llm(_messages):
        return {"content": "not json at all"}

    monkeypatch.setattr(g, "call_llm", fake_llm)
    out = await route_query(AgentState(query="q", agencies=[]))
    assert out == {"routes": []}


@pytest.mark.asyncio
async def test_route_query_missing_routes_key(monkeypatch):
    import app.services.chat.graph as g
    from app.services.chat.graph import AgentState, route_query

    async def fake_llm(_messages):
        return {"content": '{"foo": 1}'}

    monkeypatch.setattr(g, "call_llm", fake_llm)
    out = await route_query(AgentState(query="q", agencies=[]))
    assert out == {"routes": []}
