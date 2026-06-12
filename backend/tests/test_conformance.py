import pytest

from app.models import Agency
from app.services import conformance


@pytest.mark.asyncio
async def test_report_aggregates_checks(db, monkeypatch):
    ag = await Agency.create(name="A", status="draft", connection_type="API",
                             endpoint_url="http://x", expected_payload={"query": "__query__"})

    async def fake_ask(agency, question):
        return {"ok": True, "latency_ms": 120, "answer": "คำตอบภาษาไทย"}

    monkeypatch.setattr(conformance, "_ask", fake_ask)
    report = await conformance.run_conformance(ag)

    assert report["passed"] is True
    assert {c["name"] for c in report["checks"]} == {
        "responds", "thai_text", "non_empty", "concurrency_3", "garbage_input",
    }


@pytest.mark.asyncio
async def test_failing_check_fails_report(db, monkeypatch):
    ag = await Agency.create(name="B", status="draft", connection_type="API", endpoint_url="http://x")

    async def fake_ask(agency, question):
        return {"ok": False, "latency_ms": 0, "answer": "", "error": "ConnectError"}

    monkeypatch.setattr(conformance, "_ask", fake_ask)
    report = await conformance.run_conformance(ag)
    assert report["passed"] is False
