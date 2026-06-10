import asyncio
import json
import operator
import re
import uuid
from dataclasses import dataclass, field
from typing import Annotated

import httpx
from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.models.agency import Agency
from app.services.chat.llm import build_router_prompt, call_llm


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

    return {"routes": routes}


async def dispatch_to_agencies(state: AgentState) -> dict:
    async def call_agency(route: dict) -> dict:
        conn = route["connection_type"]
        sub_q = route["sub_question"]
        name = route["agency_name"]

        try:
            if conn == "A2A":
                async with httpx.AsyncClient(timeout=settings.A2A_DISPATCH_TIMEOUT) as client:
                    resp = await client.post(
                        route["endpoint_url"],
                        json={
                            "session_id": str(uuid.uuid4()),
                            "query": f"ให้ระบุแหล่งที่มาของข้อมูลในคำตอบด้วยเสมอ\n\nคำถาม: {sub_q}",
                        },
                        headers={"Content-Type": "application/json"},
                    )
                    return {"agency": name, "response": resp.json(), "status": "ok"}

            if conn == "API":
                # TODO: implement real API agency dispatch
                raise NotImplementedError("API agency dispatch not yet implemented")

            if conn == "MCP":
                # TODO: implement real MCP agency dispatch
                raise NotImplementedError("MCP agency dispatch not yet implemented")

            return {"agency": name, "response": f"Unknown connection_type: {conn}", "status": "error"}

        except Exception as e:
            return {"agency": name, "response": str(e), "status": "error"}

    tasks = [call_agency(route) for route in state.routes]
    results = await asyncio.gather(*tasks)
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
