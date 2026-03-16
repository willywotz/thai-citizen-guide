"""
LangGraph nodes for the Thai citizen AI chat pipeline.
Each node is an async function that receives and returns ChatState.
"""
import asyncio
import time
from typing import Any
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.state import ChatState, AgencyResult, AgentStep
from app.config import settings

# ──────────────────────────────────────────────
# Agency keyword routing
# ──────────────────────────────────────────────

AGENCY_KEYWORDS: dict[str, list[str]] = {
    "fda": ["ยา", "อาหาร", "เครื่องสำอาง", "อย.", "พาราเซตามอล", "นำเข้า", "ผลิตภัณฑ์สุขภาพ"],
    "revenue": ["ภาษี", "ลดหย่อน", "สรรพากร", "vat", "ยื่นแบบ", "เงินได้"],
    "dopa": ["บัตรประชาชน", "ทะเบียนราษฎร์", "ทะเบียนบ้าน", "ปกครอง", "เปลี่ยนชื่อ", "แจ้งเกิด"],
    "land": ["ที่ดิน", "โฉนด", "ราคาประเมิน", "จดทะเบียน", "รังวัด", "โอนที่ดิน"],
}

AGENCY_NAME_MAP: dict[str, str] = {
    "fda": "สำนักงาน อย.",
    "revenue": "กรมสรรพากร",
    "dopa": "กรมการปกครอง",
    "land": "กรมที่ดิน",
}

AGENCY_ICON_MAP: dict[str, str] = {
    "fda": "🏥",
    "revenue": "💰",
    "dopa": "🏛️",
    "land": "🗺️",
}


def detect_agencies_from_query(query: str) -> list[str]:
    q = query.lower()
    matched = [
        agency_id
        for agency_id, keywords in AGENCY_KEYWORDS.items()
        if any(kw in q for kw in keywords)
    ]
    return matched or ["fda"]


# ──────────────────────────────────────────────
# Node 1: Detect agencies
# ──────────────────────────────────────────────

async def node_detect_agencies(state: ChatState) -> ChatState:
    query = state["query"]
    agencies = detect_agencies_from_query(query)

    steps = [
        AgentStep(icon="🔍", label="กำลังวิเคราะห์คำถาม...", status="done"),
        AgentStep(
            icon="📋",
            label=f"วางแผนการสืบค้น → เลือกหน่วยงาน: {', '.join(AGENCY_NAME_MAP[a] for a in agencies)}",
            status="done",
        ),
    ]

    return {
        **state,
        "target_agencies": agencies,
        "agent_steps": steps,
    }


# ──────────────────────────────────────────────
# Node 2: Fetch agency configs from DB
# ──────────────────────────────────────────────

async def node_fetch_agency_configs(state: ChatState, db: AsyncSession) -> ChatState:
    """Fetch agency response_schema and config from DB for schema guide building."""
    from app.models import Agency
    from sqlalchemy import select

    try:
        result = await db.execute(
            select(Agency).where(Agency.status == "active")
        )
        agencies = result.scalars().all()
        configs = [
            {
                "id": str(a.id),
                "short_name": a.short_name,
                "name": a.name,
                "logo": a.logo,
                "connection_type": a.connection_type,
                "response_schema": a.response_schema or [],
                "api_endpoints": a.api_endpoints or [],
            }
            for a in agencies
        ]
    except Exception:
        configs = []

    return {**state, "agency_configs": configs}


# ──────────────────────────────────────────────
# Node 3: Fetch agency data (parallel)
# ──────────────────────────────────────────────

async def _call_agency_handler(agency_id: str, query: str) -> AgencyResult:
    """
    Calls the local agency handler (in-process) instead of HTTP.
    Falls back gracefully on errors.
    """
    from app.services.agency_handlers import AGENCY_HANDLERS

    handler = AGENCY_HANDLERS.get(agency_id)
    if not handler:
        return AgencyResult(
            agency_id=agency_id,
            agency_name=AGENCY_NAME_MAP.get(agency_id, agency_id),
            agency_icon=AGENCY_ICON_MAP.get(agency_id, "🏢"),
            answer="ไม่พบข้อมูลจากหน่วยงานนี้",
            references=[],
            confidence=0.5,
            latency_ms=0,
        )

    start = time.monotonic()
    result = await handler(query)
    latency_ms = int((time.monotonic() - start) * 1000)

    return AgencyResult(
        agency_id=agency_id,
        agency_name=AGENCY_NAME_MAP.get(agency_id, agency_id),
        agency_icon=AGENCY_ICON_MAP.get(agency_id, "🏢"),
        answer=result["answer"],
        references=result.get("references", []),
        confidence=result.get("confidence", 0.8),
        latency_ms=latency_ms,
    )


async def node_fetch_agency_data(state: ChatState) -> ChatState:
    target = state["target_agencies"]
    query = state["query"]
    existing_steps = list(state.get("agent_steps", []))

    for agency_id in target:
        existing_steps.append(
            AgentStep(
                icon="🔗",
                label=f"กำลังสืบค้นจาก {AGENCY_NAME_MAP.get(agency_id, agency_id)} ...",
                status="done",
            )
        )

    # Run all agency calls in parallel
    results = await asyncio.gather(
        *[_call_agency_handler(agency_id, query) for agency_id in target],
        return_exceptions=False,
    )

    existing_steps.append(AgentStep(icon="✅", label="รวบรวมและประเมินผลลัพธ์", status="done"))

    return {
        **state,
        "agency_results": list(results),
        "agent_steps": existing_steps,
    }


# ──────────────────────────────────────────────
# Node 4: Synthesize answer via LLM
# ──────────────────────────────────────────────

def _build_schema_guide(agency_configs: list[dict], target_agencies: list[str]) -> str:
    sections: list[str] = []
    for agency_id in target_agencies:
        config = None
        for c in agency_configs:
            sn = c["short_name"].replace(".", "").lower()
            if (
                (agency_id == "fda" and ("อย" in sn or "อาหาร" in c["name"]))
                or (agency_id == "revenue" and "สรรพากร" in sn)
                or (agency_id == "dopa" and "ปกครอง" in sn)
                or (agency_id == "land" and "ที่ดิน" in sn)
            ):
                config = c
                break

        schema = config.get("response_schema") if config else []
        if not schema:
            continue

        fields = "\n".join(
            f"  - **{f['field']}** ({f['type']}): {f['description']}"
            + (f" — ตัวอย่าง: {f['example']}" if f.get("example") else "")
            for f in schema
        )
        sections.append(
            f"#### {config['name']} ({config['short_name']})\nResponse fields ที่สำคัญ:\n{fields}"
        )

    if not sections:
        return ""
    return (
        "\n\n## Schema Reference สำหรับ Parse ข้อมูล\n"
        "ใช้ข้อมูล schema ด้านล่างเพื่อระบุและจัดรูปแบบข้อมูลในคำตอบให้ถูกต้อง:\n\n"
        + "\n\n".join(sections)
    )


async def node_synthesize_answer(state: ChatState) -> ChatState:
    results: list[AgencyResult] = state["agency_results"]
    query = state["query"]
    agency_configs = state.get("agency_configs", [])
    target_agencies = state["target_agencies"]
    existing_steps = list(state.get("agent_steps", []))

    fallback_answer = "\n\n---\n\n".join(r.answer for r in results)

    if not settings.AI_GATEWAY_KEY or not results:
        existing_steps.append(AgentStep(icon="📝", label="สังเคราะห์คำตอบเสร็จสิ้น", status="done"))
        references = [
            {"agency": r.agency_name, "title": ref["title"], "url": ref["url"]}
            for r in results
            for ref in r.references
        ]
        confidence = sum(r.confidence for r in results) / len(results) if results else 0.8
        return {
            **state,
            "synthesized_answer": fallback_answer,
            "agent_steps": existing_steps,
            "references": references,
            "confidence": confidence,
        }

    existing_steps.append(
        AgentStep(icon="🤖", label="AI กำลังสังเคราะห์คำตอบ (พร้อม Schema Guide)...", status="done")
    )

    agency_context = "\n\n".join(
        f"### ข้อมูลจาก {r.agency_name}\n{r.answer}" for r in results
    )
    schema_guide = _build_schema_guide(agency_configs, target_agencies)

    system_prompt = (
        "คุณคือ AI ผู้ช่วยภาครัฐไทย ทำหน้าที่สังเคราะห์ข้อมูลจากหลายหน่วยงานราชการ"
        "ให้เป็นคำตอบที่ชัดเจน ถูกต้อง และเข้าใจง่ายสำหรับประชาชน\n\n"
        "กฎ:\n"
        "- ตอบเป็นภาษาไทยเสมอ\n"
        "- ใช้ Markdown formatting (หัวข้อ, bullet points, ตัวหนา) ให้อ่านง่าย\n"
        "- อ้างอิงชื่อหน่วยงานที่เป็นแหล่งข้อมูลในคำตอบ\n"
        "- หากข้อมูลจากหลายหน่วยงานเกี่ยวข้องกัน ให้เชื่อมโยงและสรุปให้เป็นคำตอบเดียว\n"
        "- ห้ามเพิ่มข้อมูลที่ไม่มีในแหล่งข้อมูลที่ให้มา\n"
        "- จบคำตอบด้วยข้อแนะนำเพิ่มเติมหากเหมาะสม"
        + schema_guide
    )

    user_prompt = (
        f'คำถามจากประชาชน: "{query}"\n\n'
        f"ข้อมูลที่สืบค้นได้จากหน่วยงานราชการ:\n\n{agency_context}\n\n"
        "กรุณาสังเคราะห์ข้อมูลข้างต้นเป็นคำตอบที่ครบถ้วนและเข้าใจง่ายสำหรับประชาชน"
    )

    synthesized = fallback_answer
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.AI_GATEWAY_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.AI_GATEWAY_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.AI_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
        if resp.status_code == 200:
            data = resp.json()
            synthesized = data["choices"][0]["message"]["content"] or fallback_answer
    except Exception:
        pass

    existing_steps.append(AgentStep(icon="📝", label="สังเคราะห์คำตอบเสร็จสิ้น", status="done"))

    references = [
        {"agency": r.agency_name, "title": ref["title"], "url": ref["url"]}
        for r in results
        for ref in r.references
    ]
    confidence = sum(r.confidence for r in results) / len(results) if results else 0.8

    return {
        **state,
        "synthesized_answer": synthesized,
        "agent_steps": existing_steps,
        "references": references,
        "confidence": confidence,
    }
