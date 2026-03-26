"""
Multi-Agent Router with LangGraph
==================================
Dynamic agency routing — ดึง agency list จาก MCP tool แล้ว route query
ไปยัง agency ที่เกี่ยวข้องผ่าน A2A / API / MCP adapters
"""

import dotenv
dotenv.load_dotenv()

import os
import asyncio
import re
import json
import uuid
import operator
from typing import Annotated, Any
from dataclasses import dataclass, field

import httpx
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END


# ─── State ────────────────────────────────────────────────────────────────────

@dataclass
class AgentState:
    query: str = ""
    agencies: list[dict] = field(default_factory=list)
    routes: list[dict] = field(default_factory=list)
    results: Annotated[list[dict], operator.add] = field(default_factory=list)
    final_answer: str = ""


# ─── Config ───────────────────────────────────────────────────────────────────

LLM = ChatOpenAI(
    model="/model",
    temperature=0,

    openai_api_key="sk-placeholder",
    openai_api_base="http://thaillm.or.th/api/pathumma/v1",
    default_headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "apikey": os.getenv("LLM_EXTRA_APIKEY", ""),
    },
)

# MCP / API endpoint สำหรับดึง agency list
AGENCY_LIST_URL = "http://localhost:8000/api/v1/agencies?status=active"  # ← ปรับ URL ตาม environment


# ─── Prompt Builder ───────────────────────────────────────────────────────────

def build_router_prompt(agencies: list[dict]) -> str:
    """สร้าง system prompt พร้อม available sources จาก agency list"""

    source_lines = []
    for ag in agencies:
        scope = ", ".join(ag.get("data_scope", []))
        source_lines.append(
            f'- {ag["name"]} (id: {ag["id"]}, type: {ag["connection_type"]}): '
            f'{ag["description"]} — ขอบเขตข้อมูล: {scope}'
        )

    sources_block = "\n".join(source_lines)

    return f"""\
คุณคือ Router Agent ที่วิเคราะห์คำถามผู้ใช้แล้วเลือกหน่วยงานที่เกี่ยวข้อง
สำหรับแต่ละหน่วยงาน ให้สร้าง sub-question ที่เหมาะกับขอบเขตข้อมูลของหน่วยงานนั้น

Available sources:
{sources_block}

ตอบเป็น JSON เท่านั้น ห้ามมี text อื่น:
{{
  "routes": [
    {{
      "agency_id": "<uuid>",
      "agency_name": "<ชื่อหน่วยงาน>",
      "connection_type": "<A2A|API|MCP>",
      "sub_question": "<คำถามที่ปรับให้เหมาะกับหน่วยงานนี้>"
    }}
  ]
}}

กฎ:
- เลือกเฉพาะหน่วยงานที่เกี่ยวข้องจริงๆ อย่าเลือกทุกอัน
- sub_question ต้องเจาะจงกับ data_scope ของหน่วยงานนั้น
- ถ้าไม่มีหน่วยงานไหนเกี่ยวข้อง ให้ตอบ {{"routes": []}}"""


# ─── Nodes ────────────────────────────────────────────────────────────────────

async def load_agencies(state: AgentState) -> dict:
    """Node 1: ดึง agency list จาก MCP tool / API"""

    # === Production: call MCP tool หรือ REST API ===
    async with httpx.AsyncClient() as client:
        resp = await client.get(AGENCY_LIST_URL)
        data = resp.json()
        return {"agencies": data["data"]}


async def route_query(state: AgentState) -> dict:
    """Node 2: LLM วิเคราะห์ query แล้วเลือก agencies + สร้าง sub-questions"""

    system_prompt = build_router_prompt(state.agencies)

    response = await LLM.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=state.query),
    ])

    # parse JSON จาก LLM response
    text = response.content.strip()

    # strip markdown fences ถ้ามี
    if '<think>' in text:
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]

    parsed = json.loads(text)
    routes = parsed.get("routes", [])

    # enrich route ด้วย endpoint info
    agency_map = {ag["id"]: ag for ag in state.agencies}
    for route in routes:
        ag = agency_map.get(route["agency_id"], {})
        route["endpoint_url"] = ag.get("endpoint_url", "")
        route["expected_payload"] = ag.get("expected_payload")

    return {"routes": routes}


async def dispatch_to_agencies(state: AgentState) -> dict:
    """Node 3: ส่ง sub-question ไปแต่ละ agency ตาม connection_type"""

    async def call_agency(route: dict) -> dict:
        """Dispatch ตาม connection_type"""
        conn = route["connection_type"]
        sub_q = route["sub_question"]
        name = route["agency_name"]

        try:
            # ─── A2A Protocol ───
            if conn == "A2A":
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        route["endpoint_url"],
                        json={
                            # "jsonrpc": "2.0",
                            # "method": "message/send",
                            # "params": {"message": {"text": sub_q}},
                            "session_id": str(uuid.uuid4()),
                            "query": sub_q,
                        },
                        headers={"Content-Type": "application/json"},
                    )
                    return {"agency": name, "response": resp.json(), "status": "ok"}
                # return {"agency": name, "response": f"[A2A mock] ตอบจาก {name}: {sub_q}", "status": "ok"}

            # ─── REST API ───
            elif conn == "API":
                payload = route.get("expected_payload") or {}
                # แทนที่ placeholder
                if "query" in payload:
                    payload = {**payload, "query": sub_q}
                # async with httpx.AsyncClient(timeout=30) as client:
                #     resp = await client.post(route["endpoint_url"], json=payload)
                #     return {"agency": name, "response": resp.json(), "status": "ok"}
                return {"agency": name, "response": f"[API mock] ตอบจาก {name}: {sub_q}", "status": "ok"}

            # ─── MCP Protocol ───
            elif conn == "MCP":
                # MCP call via SDK
                # result = await mcp_client.call_tool(route["endpoint_url"], {"query": sub_q})
                # return {"agency": name, "response": result, "status": "ok"}
                return {"agency": name, "response": f"[MCP mock] ตอบจาก {name}: {sub_q}", "status": "ok"}

            else:
                return {"agency": name, "response": f"Unknown connection_type: {conn}", "status": "error"}

        except Exception as e:
            return {"agency": name, "response": str(e), "status": "error"}

    # fire all agencies concurrently
    tasks = [call_agency(route) for route in state.routes]
    results = await asyncio.gather(*tasks)

    return {"results": list(results)}


async def synthesize(state: AgentState) -> dict:
    """Node 4: รวมผลลัพธ์จากทุก agency เป็นคำตอบเดียว"""

    if not state.results:
        return {"final_answer": "ไม่พบหน่วยงานที่เกี่ยวข้องกับคำถามของคุณ"}

    results_text = "\n\n".join(
        f"### {r['agency']}\n{r['response']}" for r in state.results
    )

    response = await LLM.ainvoke([
        SystemMessage(content="""\
คุณคือ Synthesizer Agent สรุปข้อมูลจากหลายหน่วยงานราชการเป็นคำตอบเดียวที่ครบถ้วน
- ตอบเป็นภาษาไทย
- อ้างอิงว่าข้อมูลมาจากหน่วยงานไหน
- ถ้ามี error ให้แจ้งผู้ใช้ว่าหน่วยงานไหนไม่สามารถตอบได้"""),
        HumanMessage(content=f"คำถามเดิม: {state.query}\n\nผลลัพธ์จากหน่วยงาน:\n{results_text}"),
    ])

    return {"final_answer": response.content}


# ─── Conditional Edge ─────────────────────────────────────────────────────────

def should_dispatch(state: AgentState) -> str:
    """ถ้าไม่มี route เลย ข้ามไป synthesize เลย"""
    return "dispatch" if state.routes else "synthesize"


# ─── Graph ────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # nodes
    graph.add_node("load_agencies", load_agencies)
    graph.add_node("route_query", route_query)
    graph.add_node("dispatch", dispatch_to_agencies)
    graph.add_node("synthesize", synthesize)

    # edges
    graph.add_edge(START, "load_agencies")
    graph.add_edge("load_agencies", "route_query")
    graph.add_conditional_edges("route_query", should_dispatch, {
        "dispatch": "dispatch",
        "synthesize": "synthesize",
    })
    graph.add_edge("dispatch", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    app = build_graph()

    queries = [
        # "อยากเปลี่ยนชื่อในบัตรประชาชน ต้องเสียภาษีอะไรเพิ่มไหม",
        # "ยาพาราเซตามอลตัวไหนผ่าน อย. บ้าง",
        # "อยากซื้อที่ดิน ต้องตรวจสอบโฉนดยังไง แล้วเสียภาษีอะไรบ้าง",
        "ขั้นตอนการทำบัตรประชาชนใหม่",
    ]

    for q in queries:
        print(f"\n{'='*70}")
        print(f"Q: {q}")
        print(f"{'='*70}")

        result = await app.ainvoke({"query": q})

        print(f"\n📌 Routes:")
        for r in result["routes"]:
            print(f"  → {r['agency_name']} ({r['connection_type']})")
            print(f"    sub-question: {r['sub_question']}")

        print(f"\n📋 Results:")
        for r in result["results"]:
            print(f"  [{r['status']}] {r['agency']}: {r['response']}")

        print(f"\n✅ Final Answer:\n{result['final_answer']}")


if __name__ == "__main__":
    asyncio.run(main())