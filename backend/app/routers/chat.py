"""
AI Chat router — port of the Supabase `ai-chat` edge function.

Flow
----
1. Detect target agencies from Thai keyword matching
2. Fetch agency response_schema configs from DB
3. Query each agency sub-handler in parallel (async)
4. Build a schema-guide prompt section
5. Synthesise a unified answer using the configured LLM (Gemini via AI Gateway)
6. Return structured response: answer, references, agentSteps, agencies, confidence

Endpoint
--------
  POST  /chat
"""

import asyncio
import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from opentelemetry import trace
from opentelemetry.trace import Status

from app.config import settings
from app.models.agency import Agency
from app.models.conversation import Conversation, Message
from app.models.connection_log import ConnectionLog
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.auth.dependencies import get_current_user_optional
from app.utils import generate_uuid

router = APIRouter(prefix="/chat", tags=["Chat"])
tracer = trace.get_tracer(__name__)

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
    conversation_id: str = ""

    agencies: list[dict] = field(default_factory=list)
    routes: list[dict] = field(default_factory=list)
    results: Annotated[list[dict], operator.add] = field(default_factory=list)
    final_answer: str = ""


# ─── Config ───────────────────────────────────────────────────────────────────

# LLM = ChatOpenAI(
#     model="/model",
#     temperature=0,

#     openai_api_key="sk-placeholder",
#     openai_api_base=os.getenv("PARSE_SPEC_URL", ""),
#     default_headers={
#         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
#         "apikey": os.getenv("PARSE_SPEC_API_KEY", ""),
#     },
# )

async def call_llm(messages: list[dict]) -> str:
    llm_api_key = os.getenv("PARSE_SPEC_API_KEY", "")
    if not llm_api_key:
        raise ValueError("Missing LLM API key")

    print(f"Calling LLM with messages: {messages}")

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            os.getenv("PARSE_SPEC_URL", ""),
            headers={
                "apikey": f"{llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": os.getenv("PARSE_SPEC_LLM_MODEL", "gpt-4o-mini"),
                "messages": messages,
            },
        )
    if resp.status_code == 200:
        resp_data = resp.json()
        print(f"LLM response: {resp_data}")
        return resp_data.get("choices", [{}])[0].get("message", {})
    else:
        raise ValueError(f"LLM API error: {resp.status_code} {resp.text}")


# ─── Prompt Builder ───────────────────────────────────────────────────────────

def build_router_prompt(agencies: list[dict]) -> str:
    """สร้าง system prompt พร้อม available sources จาก agency list"""

    source_lines = []
    for ag in agencies:
        scope = ", ".join(ag.get("data_scope", []))
        source_lines.append(
            f'- {ag["name"]} (id: {ag["id"]}, type: {ag["connection_type"]}, endpoint: {ag.get("endpoint_url", "")}): '
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
      "endpoint_url": "<endpoint_url>",
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
    # async with httpx.AsyncClient() as client:
    #     resp = await client.get(AGENCY_LIST_URL)
    #     data = resp.json()
    #     return {"agencies": data["data"]}

    agencies = await Agency.filter(status="active").all().values()
    return {"agencies": agencies}


async def route_query(state: AgentState) -> dict:
    """Node 2: LLM วิเคราะห์ query แล้วเลือก agencies + สร้าง sub-questions"""

    system_prompt = build_router_prompt(state.agencies)

    response = await call_llm([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": state.query},
    ])

    # parse JSON จาก LLM response
    text = response.get("content", "").strip()

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
        route["endpoint_url"] = ag.get("endpoint_url", route.get("endpoint_url", ""))
        route["expected_payload"] = ag.get("expected_payload", route.get("expected_payload", {}))

    return {"routes": routes}


async def dispatch_to_agencies(state: AgentState) -> dict:
    """Node 3: ส่ง sub-question ไปแต่ละ agency ตาม connection_type"""

    async def call_agency(route: dict) -> dict:
        """Dispatch ตาม connection_type"""
        conn = route["connection_type"]
        sub_q = route['sub_question']
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
                            "query": f"ให้ระบุแหล่งที่มาของข้อมูลในคำตอบด้วยเสมอ\n\nคำถาม: {sub_q}",
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

    response = await call_llm([
        {"role": "system", "content": """\
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

ตัวอย่าง: <category>ขั้นตอนดำเนินการ</category>"""},
        {"role": "user", "content": f"""\
คำถามจากประชาชน: {state.query}\n\n
ข้อมูลที่สืบค้นได้จากหน่วยงานราชการ:\n{results_text}\n\n
กรุณาสังเคราะห์ข้อมูลข้างต้นเป็นคำตอบที่ครบถ้วนและเข้าใจง่ายสำหรับประชาชน"""},
    ])

    return {"final_answer": response.get("content", "").strip()}


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

@router.post("/internal", summary="Send a query and get a synthesised AI response")
async def chat_internal(body: ChatRequest, user: User | None = Depends(get_current_user_optional)) -> ChatResponse:
    start = time.time()
    query = body.query.strip()

    if not query:
        return {"success": False, "error": "Missing query"}

    conversation_id = body.conversation_id or str(generate_uuid())
    
    app = build_graph()
    
    result = await app.ainvoke({"query": query, "conversation_id": conversation_id})

    response_time = int((time.time() - start) * 1000)
    
    answer = result.get("final_answer", "").strip()

    references = []

    if '<references>' in answer:
        # แยกส่วน answer กับ references
        parts = re.split(r'<references>(.*?)</references>', answer, flags=re.DOTALL)
        if len(parts) == 3:
            answer = parts[0].strip()
            try:
                references = json.loads(parts[1].strip())
            except json.JSONDecodeError:
                references = []
        else:
            references = []

    category = None

    if '<category>' in answer:
        parts = re.split(r'<category>(.*?)</category>', answer, flags=re.DOTALL)
        print(f"Answer parts after category split: {parts}")
        if len(parts) == 3:
            category = parts[1].strip()

    if not body.conversation_id:
        conv = await Conversation.create(
            id=conversation_id,
            title=query[:50],
            preview=query[:100],
            agencies=[],
            status='success',
            message_count=len(answer),
            response_time=response_time,
            user_id=user.id if user else None,
        )
    else:
        conv = await Conversation.get(id=conversation_id)
        conv.message_count += len(answer)
        await conv.save()

    await Message.create(
        conversation_id=conversation_id,
        role='user',
        content=query,
        agent_steps=[],
        sources=[],
        category=category,
    )
    
    response_msg = await Message.create(
        conversation_id=conversation_id,
        role='assistant',
        content=answer,
        agent_steps=[],
        sources=references,
        response_time=response_time,
        agency_ids=[str(ag["agency_id"]) for ag in result.get("routes", [])],
    )

    return {
        "success": True,
        "data": {
            "message_id": response_msg.id,
            "answer": answer,
            "references": references,
            "agentSteps": [],
            "agencies": [],
            "confidence": 0.0,
        },
        "conversation_id": conversation_id,
        "responseTime": response_time,
    }

@router.post("/external", summary="Send a query and get a synthesised AI response")
async def chat_external(body: ChatRequest, user: User | None = Depends(get_current_user_optional)) -> ChatResponse:
    with tracer.start_as_current_span("chat_external_endpoint") as span:
        start = time.time()
        
        query = body.query.strip()
        conversation_id = body.conversation_id or str(generate_uuid())
        
        if body.conversation_id:
            conv = await Conversation.get(id=conversation_id)

        if not query:
            span.set_status(Status.ERROR, "Missing query")
            span.set_attributes({"error": "missing query"})
            return {"success": False, "error": "missing query"}

        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                "http://185.84.160.55:8000/v3/chat",
                json={"query": query, "mcp_endpoint_url": "http://185.84.161.145/mcp/", "session_id": conversation_id},
                headers={"Content-Type": "application/json"},
            )

        if resp.status_code != 200:
            span.set_status(Status.ERROR, f"External chat request failed with status {resp.status_code}")
            span.set_attributes({"error": resp.text})
            return {"success": False, "error": resp.text}
            
        response_time = int((time.time() - start) * 1000)

        raw_data = resp.json()
        span.set_attributes({"external_response": raw_data})
        # print(f"External chat response: {raw_data}")

        data = raw_data.get("data", {})

        answer = data.get("answer", "").strip()
        errors = data.get("errors", [])

        if not body.conversation_id:
            conv = await Conversation.create(
                id=conversation_id,
                title=query[:50],
                preview=query[:100],
                agencies=[],
                status='success',
                message_count=len(answer),
                response_time=response_time,
                user_id=user.id if user else None,
                external_session_id=data.get("session_id", None),
            )
        else:
            conv.message_count += len(answer)
            await conv.save()

        await Message.create(
            conversation_id=conversation_id,
            role='user',
            content=query,
        )
        
        response_msg = await Message.create(
            conversation_id=conversation_id,
            role='assistant',
            content=answer,
            response_time=response_time,
            errors=errors,
        )

        return {
            "success": True,
            "data": {
                "message_id": response_msg.id,
                "answer": answer,
                "references": data.get("references", []),
                "agentSteps": data.get("agentSteps", []),
                "agencies": data.get("agencies", []),
                "confidence": data.get("confidence", 0.0),
            },
            "conversation_id": conversation_id,
            "responseTime": response_time,
        }

@router.post("", summary="Send a query and get a synthesised AI response")
async def chat(body: ChatRequest, user: User | None = Depends(get_current_user_optional)) -> ChatResponse:
    with tracer.start_as_current_span("chat_endpoint"):
        return await chat_external(body, user)