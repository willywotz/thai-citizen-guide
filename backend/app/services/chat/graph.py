import asyncio
import json
import operator
import re
from dataclasses import dataclass, field
from typing import Annotated

from langgraph.graph import END, START, StateGraph

from app.models.agency import Agency
from app.services.chat.dispatch import dispatch_one
from app.services.chat.llm import build_router_prompt, call_llm
from app.services.circuit_breaker import record_dispatch_result


@dataclass
class AgentState:
    query: str = ""
    conversation_id: str = ""
    agencies: list[dict] = field(default_factory=list)
    routes: list[dict] = field(default_factory=list)
    results: Annotated[list[dict], operator.add] = field(default_factory=list)
    final_answer: str = ""


async def load_agencies(state: AgentState) -> dict:
    agencies = await Agency.filter(status="active").all().values()
    return {"agencies": agencies}


async def route_query(state: AgentState) -> dict:
    system_prompt = build_router_prompt(state.agencies)
    response = await call_llm([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": state.query},
    ])

    text = response.get("content", "").strip()

    if "<think>" in text:
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]

    parsed = json.loads(text)
    routes = parsed.get("routes", [])

    agency_map = {ag["id"]: ag for ag in state.agencies}
    for route in routes:
        ag = agency_map.get(route["agency_id"], {})
        route["endpoint_url"] = ag.get("endpoint_url", route.get("endpoint_url", ""))
        route["expected_payload"] = ag.get("expected_payload", route.get("expected_payload", {}))
        route["api_headers"] = ag.get("api_headers", route.get("api_headers", []))
        route["priority"] = ag.get("priority")
        route["dispatch_timeout_s"] = ag.get("dispatch_timeout_s")
        route["rate_limit_rpm"] = ag.get("rate_limit_rpm")

    # Sort by priority (lower number = higher priority); None last.
    routes.sort(key=lambda r: (r.get("priority") is None, r.get("priority") or 0))
    return {"routes": routes}


async def dispatch_to_agencies(state: AgentState) -> dict:
    tasks = [dispatch_one(route, state.conversation_id) for route in state.routes]
    results = await asyncio.gather(*tasks)
    for route, result in zip(state.routes, results):
        agency_id = route.get("agency_id")
        if agency_id is None or result.get("status") == "rate_limited":
            continue
        await record_dispatch_result(agency_id, success=(result.get("status") == "ok"))
    return {"results": list(results)}


async def synthesize(state: AgentState) -> dict:
    if not state.results:
        return {"final_answer": "ไม่พบหน่วยงานที่เกี่ยวข้องกับคำถามของคุณ"}

    results_text = "\n\n".join(
        f"### {r['agency']}\n{r['response']}" for r in state.results
    )

    response = await call_llm([
        {
            "role": "system",
            "content": """\
คุณคือ AI ผู้ช่วยภาครัฐไทย ทำหน้าที่สังเคราะห์ข้อมูลจากหลายหน่วยงานราชการให้เป็นคำตอบที่ชัดเจน ถูกต้อง และเข้าใจง่ายสำหรับประชาชน

กฎ:
- ตอบเป็นภาษาไทยเสมอ
- ใช้ Markdown formatting (หัวข้อ, bullet points, ตัวหนา) ให้อ่านง่าย
- อ้างอิงชื่อหน่วยงานที่เป็นแหล่งข้อมูลในคำตอบ
- หากข้อมูลจากหลายหน่วยงานเกี่ยวข้องกัน ให้เชื่อมโยงและสรุปให้เป็นคำตอบเดียวที่สอดคล้องกัน
- ห้ามเพิ่มข้อมูลที่ไม่มีในแหล่งข้อมูลที่ให้มา
- จบคำตอบด้วยข้อแนะนำเพิ่มเติมหากเหมาะสม
- หากมีลิงก์ในข้อมูลที่ได้มา ให้เขียนเป็นข้อความที่แสดงและลิงก์ในรูปแบบ Markdown link เช่น [ข้อความที่แสดง](ลิงก์)

กฎสำหรับวิเคราะห์หมวดหมู่คำถาม:
- วิเคราะห์คำถามของผู้ใช้และระบุหมวดหมู่ที่ตรงที่สุด 1 หมวด จากนี้: สอบถามข้อมูล | ตรวจสอบสถานะ | ขั้นตอนดำเนินการ | กฎหมาย/ระเบียบ
- **ต้องวาง tag นี้หลังคำตอบหลักเสมอ:**

<category>หมวดหมู่ที่วิเคราะห์ได้</category>

ตัวอย่าง: <category>ขั้นตอนดำเนินการ</category>""",
        },
        {
            "role": "user",
            "content": (
                f"คำถามจากประชาชน: {state.query}\n\n"
                f"ข้อมูลที่สืบค้นได้จากหน่วยงานราชการ:\n{results_text}\n\n"
                "กรุณาสังเคราะห์ข้อมูลข้างต้นเป็นคำตอบที่ครบถ้วนและเข้าใจง่ายสำหรับประชาชน"
            ),
        },
    ])

    return {"final_answer": response.get("content", "").strip()}


def should_dispatch(state: AgentState) -> str:
    return "dispatch" if state.routes else "synthesize"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("load_agencies", load_agencies)
    graph.add_node("route_query", route_query)
    graph.add_node("dispatch", dispatch_to_agencies)
    graph.add_node("synthesize", synthesize)

    graph.add_edge(START, "load_agencies")
    graph.add_edge("load_agencies", "route_query")
    graph.add_conditional_edges(
        "route_query",
        should_dispatch,
        {"dispatch": "dispatch", "synthesize": "synthesize"},
    )
    graph.add_edge("dispatch", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()
