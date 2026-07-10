"""Popular Questions (คำถามยอดนิยม): curated + auto-generated FAQ list.

Auto-generation churn policy: rows created by ``regenerate`` are tagged
``source="auto"``; editing one (see ``app/routers/popular_questions.py``) flips
it to ``source="manual"`` so it survives future churn. A hidden row acts as a
tombstone — its ``text_key`` blocks the same question from being regenerated.
"""
import json
import logging
import re
from datetime import timedelta

from app.config import settings
from app.models.agency import Agency
from app.models.conversation import Message
from app.models.popular_question import PopularQuestion, PopularQuestionSource
from app.utils import now

logger = logging.getLogger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")
_TRAILING_PUNCT_RE = re.compile(r"[\s.,!?;:？！。，、]+$")
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)

_LLM_MAX_QUESTIONS = 8
_LLM_QUESTION_SAMPLE = 200

# 2 natural citizen questions per seeded agency (must match seeded agency names
# in app/routers/seed.py's DEFAULT_AGENCIES).
_SEED_QUESTIONS = [
    ("กรมการปกครอง", "ทำบัตรประชาชนใหม่ ต้องใช้เอกสารอะไรบ้าง"),
    ("กรมการปกครอง", "ย้ายทะเบียนบ้านออนไลน์ทำอย่างไร"),
    ("กรมที่ดิน", "ตรวจสอบราคาประเมินที่ดินทำอย่างไร"),
    ("กรมที่ดิน", "ขอคัดสำเนาโฉนดที่ดินต้องทำอย่างไร"),
    ("สำนักงานคณะกรรมการอาหารและยา", "ตรวจสอบเลขทะเบียน อย. ของผลิตภัณฑ์ได้ที่ไหน"),
    ("สำนักงานคณะกรรมการอาหารและยา", "ยาพาราเซตามอลต้องขึ้นทะเบียน อย. หรือไม่"),
]

_LLM_PROMPT = """\
คุณเป็นผู้ช่วยวิเคราะห์คำถามยอดนิยมของประชาชนที่ถามเข้าระบบพอร์ทัลบริการภาครัฐ
จากรายการคำถามของผู้ใช้ด้านล่าง ให้เลือกและเรียบเรียงคำถามที่พบบ่อยที่สุดไม่เกิน {k} ข้อ
เป็นคำถามภาษาไทยที่กระชับและชัดเจน พร้อมระบุชื่อหน่วยงานที่เกี่ยวข้องเต็มรูปแบบ (ถ้าไม่ทราบให้เว้นว่าง)

รายการคำถาม:
{questions}

ตอบเป็น JSON เท่านั้น ไม่มีข้อความอื่นปน ในรูปแบบ:
{{"questions": [{{"text": "<คำถาม>", "agency": "<ชื่อหน่วยงาน หรือค่าว่าง>", "score": <ตัวเลข 0.0-1.0>}}]}}
"""


def normalize_text_key(text: str) -> str:
    """Dedupe key: trim, collapse internal whitespace, strip trailing punctuation, casefold."""
    collapsed = _WHITESPACE_RE.sub(" ", text.strip())
    stripped = _TRAILING_PUNCT_RE.sub("", collapsed)
    return stripped.casefold()


async def published_questions() -> list[dict]:
    """Rows to show publicly: not hidden, pinned first, capped at the display count."""
    rows = await PopularQuestion.filter(hidden=False).prefetch_related("agency")
    rows.sort(key=lambda r: (
        0 if r.pinned else 1,
        r.sort_order,
        0 if r.score is not None else 1,
        -(r.score or 0.0),
        -r.created_at.timestamp(),
    ))
    out: list[dict] = []
    for r in rows[: settings.POPULAR_QUESTIONS_DISPLAY_COUNT]:
        agency = r.agency if r.agency_id else None
        out.append({
            "id": str(r.id),
            "text": r.text,
            "agency": {"id": str(agency.id), "name": agency.name, "logo": agency.logo} if agency else None,
        })
    return out


async def regenerate() -> int:
    """Regenerate ``source="auto"`` rows from recent successful chat turns.

    Cold-start guarantee: below ``POPULAR_QUESTIONS_MIN_TURNS`` recent
    successful turns, this is a no-op so the seed rows stay visible.
    """
    cutoff = now() - timedelta(days=settings.POPULAR_QUESTIONS_WINDOW_DAYS)
    turn_count = await Message.filter(
        role="user", created_at__gte=cutoff, conversation__status="success",
    ).count()
    if turn_count < settings.POPULAR_QUESTIONS_MIN_TURNS:
        logger.info(
            "popular questions: only %d successful turns in the last %d days, skipping regen",
            turn_count, settings.POPULAR_QUESTIONS_WINDOW_DAYS,
        )
        return 0

    questions = await Message.filter(
        role="user", created_at__gte=cutoff, conversation__status="success",
    ).order_by("-created_at").limit(_LLM_QUESTION_SAMPLE).values_list("content", flat=True)

    candidates = await _ask_llm(list(questions))
    if not candidates:
        return 0

    # Churn: drop stale auto-generated rows that were never pinned or hidden.
    await PopularQuestion.filter(source=PopularQuestionSource.auto, pinned=False, hidden=False).delete()

    created = 0
    for cand in candidates[:_LLM_MAX_QUESTIONS]:
        text = str(cand.get("text") or "").strip()
        if not text:
            continue
        key = normalize_text_key(text)
        if await PopularQuestion.filter(text_key=key).exists():
            continue  # any existing row (incl. a hidden tombstone) blocks recreation

        agency = None
        agency_name = str(cand.get("agency") or "").strip()
        if agency_name:
            agency = await Agency.filter(name__iexact=agency_name).first()

        score = cand.get("score")
        try:
            score = float(score) if score is not None else None
        except (TypeError, ValueError):
            score = None

        await PopularQuestion.create(
            text=text, text_key=key, agency=agency, source=PopularQuestionSource.auto, score=score,
        )
        created += 1
    return created


def _extract_json_payload(text: str) -> str:
    """Strip a Markdown code fence, or any leading/trailing prose, around a JSON payload.

    Real chat models often wrap JSON in ```json fences or add a sentence
    before/after it; this recovers the payload so ``json.loads`` still works.
    """
    fenced = _FENCE_RE.search(text)
    if fenced:
        return fenced.group(1).strip()
    start = next((i for i, ch in enumerate(text) if ch in "{["), None)
    if start is None:
        return text.strip()
    end = max(text.rfind("}"), text.rfind("]"))
    if end < start:
        return text.strip()
    return text[start:end + 1]


async def _ask_llm(questions: list[str]) -> list[dict]:
    from app.services.llm import LlmError, chat
    prompt = _LLM_PROMPT.format(k=_LLM_MAX_QUESTIONS, questions="\n".join(f"- {q}" for q in questions))
    try:
        res = await chat(purpose="popular_questions", messages=[{"role": "user", "content": prompt}])
        data = json.loads(_extract_json_payload(res.content))
        candidates = data.get("questions", [])
        return candidates if isinstance(candidates, list) else []
    except (LlmError, json.JSONDecodeError, ValueError, TypeError, AttributeError) as e:
        logger.error("popular questions LLM call failed: %s", e)
        return []


async def seed_popular_questions() -> int:
    """Idempotent seed of natural citizen questions, 2 per seeded agency."""
    created = 0
    for agency_name, text in _SEED_QUESTIONS:
        agency = await Agency.filter(name=agency_name).first()
        _, was_created = await PopularQuestion.get_or_create(
            text_key=normalize_text_key(text),
            defaults={"text": text, "agency": agency, "source": PopularQuestionSource.seed},
        )
        created += int(was_created)
    return created
