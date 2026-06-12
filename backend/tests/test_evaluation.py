import json

import pytest

from app.models import Agency, EvalResult
from app.models.evaluation import GoldenQuestion
from app.services import evaluation


@pytest.mark.asyncio
async def test_eval_run_scores_each_question(db, monkeypatch):
    ag = await Agency.create(name="A", status="active", connection_type="API", endpoint_url="http://x")
    gq = await GoldenQuestion.create(agency=ag, question="ทำบัตรประชาชนที่ไหน",
                                     expected_topics=["สถานที่", "เอกสาร"])

    async def fake_ask(agency, question):
        return {"ok": True, "latency_ms": 10, "answer": "ไปที่สำนักงานเขต ใช้บัตรเดิม"}

    class _Resp:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": json.dumps({"score": 0.8, "reason": "covers both"})}}],
                    "usage": {}}

    async def fake_judge(payload, **kw):
        return _Resp()

    monkeypatch.setattr(evaluation, "_ask", fake_ask)
    monkeypatch.setattr(evaluation, "openrouter_chat", fake_judge)

    await evaluation.run_evaluation()

    result = await EvalResult.filter(golden_question_id=gq.id).first()
    assert result.score == 0.8 and "สำนักงานเขต" in result.answer


@pytest.mark.asyncio
async def test_eval_skips_inactive_agencies(db, monkeypatch):
    ag = await Agency.create(name="Inactive", status="draft", connection_type="API", endpoint_url="http://x")
    await GoldenQuestion.create(agency=ag, question="test question", expected_topics=[])

    called = []

    async def fake_ask(agency, question):
        called.append(question)
        return {"ok": True, "latency_ms": 10, "answer": "answer"}

    monkeypatch.setattr(evaluation, "_ask", fake_ask)

    ran = await evaluation.run_evaluation()
    assert ran == 0
    assert called == []


@pytest.mark.asyncio
async def test_golden_question_create_and_list(db):
    ag = await Agency.create(name="GovAgency", status="active", connection_type="API", endpoint_url="http://x")
    gq1 = await GoldenQuestion.create(agency=ag, question="Q1", expected_topics=["topic1"])
    gq2 = await GoldenQuestion.create(agency=ag, question="Q2", expected_topics=["topic2"])

    questions = await GoldenQuestion.filter(agency=ag)
    assert len(questions) == 2
    ids = {q.id for q in questions}
    assert gq1.id in ids and gq2.id in ids


@pytest.mark.asyncio
async def test_golden_question_scoped_to_agency(db):
    ag1 = await Agency.create(name="Agency1", status="active", connection_type="API", endpoint_url="http://x")
    ag2 = await Agency.create(name="Agency2", status="active", connection_type="API", endpoint_url="http://y")
    await GoldenQuestion.create(agency=ag1, question="Q for ag1", expected_topics=[])
    await GoldenQuestion.create(agency=ag2, question="Q for ag2", expected_topics=[])

    ag1_questions = await GoldenQuestion.filter(agency=ag1)
    assert len(ag1_questions) == 1
    assert ag1_questions[0].question == "Q for ag1"
