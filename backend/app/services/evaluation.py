"""Scheduled answer-quality evaluation: dispatch golden questions, LLM-judge the answers."""
import json
import logging

from app.config import settings
from app.models import Agency, EvalResult
from app.models.evaluation import GoldenQuestion
from app.services.conformance import _ask
from app.services.llm_client import openrouter_chat

logger = logging.getLogger(__name__)

_JUDGE_PROMPT = """\
คุณเป็นผู้ตรวจคุณภาพคำตอบบริการภาครัฐ ให้คะแนนคำตอบ 0.0–1.0
คำถาม: {question}
หัวข้อที่คำตอบควรครอบคลุม: {topics}
คำตอบที่ได้: {answer}

ตอบเป็น JSON เท่านั้น: {{"score": <float>, "reason": "<สั้นๆ>"}}"""


async def run_evaluation() -> int:
    ran = 0
    questions = await GoldenQuestion.all().prefetch_related("agency")
    for gq in questions:
        if gq.agency.status != "active":
            continue
        try:
            res = await _ask(gq.agency, gq.question)
            answer = res["answer"] if res["ok"] else ""
            score, reason = await _judge(gq.question, gq.expected_topics, answer)
            await EvalResult.create(golden_question=gq, score=score, answer=answer, judge_reason=reason)
            ran += 1
        except Exception:
            logger.exception("eval failed for question %s", gq.id)
    return ran


async def _judge(question: str, topics: list, answer: str) -> tuple[float, str]:
    if not answer.strip():
        return 0.0, "no answer from agency"
    prompt = _JUDGE_PROMPT.format(question=question, topics=", ".join(topics), answer=answer[:4000])
    resp = await openrouter_chat(
        {"model": settings.CLASSIFICATION_MODEL, "messages": [{"role": "user", "content": prompt}]},
        purpose="judge",
    )
    content = resp.json()["choices"][0]["message"]["content"]
    data = json.loads(content)
    return float(data["score"]), str(data.get("reason", ""))
