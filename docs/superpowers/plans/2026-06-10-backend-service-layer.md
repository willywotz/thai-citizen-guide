# Backend Service Layer Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate HTTP concerns from business logic across the FastAPI backend so routers are thin HTTP adapters and all business logic lives in `app/services/`.

**Architecture:** Routers own: route decorators, auth deps, request validation, HTTP error raising, and response formatting. Services own: LLM calls, external HTTP, analytics DB queries, and data transforms. No new features — improvements (dead code removal, logging) allowed.

**Tech Stack:** Python 3.12, FastAPI, Tortoise ORM, LangGraph, httpx, pytest-asyncio

---

## File Map

**Created:**
- `app/services/chat/__init__.py`
- `app/services/chat/llm.py` — `call_llm`, `build_router_prompt`, `classify_message_category`, `store_embedding`
- `app/services/chat/graph.py` — `AgentState`, LangGraph nodes, `build_graph`
- `app/services/agency.py` — `test_connection`, `_test_rest`, `_test_mcp`, `_test_a2a`, `parse_spec`
- `app/services/analytics.py` — `get_dashboard_stats`, `get_agency_health`, `get_executive_summary`
- `app/scheduler.py` — `agency_chat_item`, `agency_chat_test`, `start_scheduler`, `stop_scheduler`
- `tests/services/test_chat_llm.py`
- `tests/services/test_agency.py`

**Modified:**
- `app/routers/chat.py` (919 → ~200 lines)
- `app/routers/agencies.py` (666 → ~450 lines)
- `app/routers/dashboard.py` (107 → ~30 lines)
- `app/routers/insight.py` (257 → ~50 lines)
- `app/routers/executive_summary.py` (126 → ~30 lines)
- `app/main.py` (240 → ~165 lines)

**Deleted:**
- `app/models.py` (shadowed by `app/models/` package — dead code)

---

## Task 1: Create branch and delete models.py

**Files:**
- Delete: `app/models.py`

- [ ] **Step 1: Create branch**

```bash
rtk git checkout -b refactor/backend-service-layer
```

- [ ] **Step 2: Verify models.py is shadowed**

Python always resolves the `app/models/` package over `app/models.py` when both exist. Confirm by checking that `app/models/__init__.py` already re-exports `User`:

```bash
cat backend/app/models/__init__.py
```

Expected output includes: `from .user import *`

- [ ] **Step 3: Delete the duplicate**

```bash
rm backend/app/models.py
```

- [ ] **Step 4: Verify imports still resolve**

```bash
cd backend && python -c "from app.models import Agency, User, Conversation, Message, ConnectionLog, Setting; print('ok')"
```

Expected: `ok`

- [ ] **Step 5: Commit**

```bash
rtk git add -A && rtk git commit -m "refactor: remove app/models.py duplicate (shadowed by models/ package)"
```

---

## Task 2: Extract scheduler to app/scheduler.py

**Files:**
- Create: `backend/app/scheduler.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create `app/scheduler.py`**

Exact content (cut from `main.py` lines starting at `from apscheduler...`):

```python
import asyncio
import json
import random
import time

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.models import Agency, ConnectionLog
from app.utils import generate_uuid, now

scheduler = AsyncIOScheduler()
sem: asyncio.Semaphore | None = None


async def agency_chat_item(agency: Agency) -> None:
    try:
        async with sem:
            if agency.connection_type == "API":
                scope = agency.data_scope or ["ทั่วไป"]
                scope = scope[random.randint(0, len(scope) - 1)] if scope else "ทั่วไป"

                async with httpx.AsyncClient(timeout=settings.AGENCY_CHAT_TIMEOUT) as client:
                    headers = {"content-type": "application/json"}
                    for v in (agency.api_headers or []):
                        headers[v["name"].lower()] = v["value"]
                    payload = {}
                    for k, v in (agency.expected_payload or {}).items():
                        payload[k] = v
                        if v == "__query__":
                            payload[k] = "ปรึกษากฎหมาย" + scope
                        if v == "__user_id__":
                            payload[k] = str(generate_uuid())
                        if v == "__session_id__":
                            payload[k] = str(generate_uuid())
                        if v == "__conversation_id__":
                            payload[k] = str(generate_uuid())
                    start_ns = time.perf_counter_ns()
                    resp = await client.post(agency.endpoint_url, headers=headers, json=payload)
                    end_ns = time.perf_counter_ns()
                    latency = int((end_ns - start_ns) // 1_000_000)
                    await ConnectionLog.create(
                        id=str(generate_uuid()),
                        agency=agency,
                        action="test",
                        connection_type="API",
                        status="success" if resp.status_code == 200 else "error",
                        latency_ms=latency,
                        detail=f"Query: {payload.get('query', '')}\n\nAnswer: {resp.text}",
                        request_body=json.dumps(payload),
                        response_body=resp.text,
                    )
    except Exception as e:
        print(f"Error testing agency {agency.name}: {e}")


async def agency_chat_test() -> None:
    agencies = await Agency.all()
    await asyncio.gather(*[agency_chat_item(ag) for ag in agencies])


async def start_scheduler() -> None:
    global sem
    sem = asyncio.Semaphore(settings.AGENCY_CHAT_CONCURRENCY)
    asyncio.create_task(agency_chat_test())
    scheduler.add_job(agency_chat_test, IntervalTrigger(minutes=settings.HEALTH_CHECK_INTERVAL_MINUTES))
    scheduler.start()


async def stop_scheduler() -> None:
    scheduler.shutdown()
```

- [ ] **Step 2: Update `app/main.py` — remove scheduler block, import from scheduler**

Remove the scheduler block at the bottom of `main.py` (everything from `from apscheduler...` to end of `stop_scheduler`) and replace with:

```python
from app.scheduler import start_scheduler, stop_scheduler
```

The lifespan function already calls `start_scheduler()` and `stop_scheduler()` — those calls stay unchanged.

- [ ] **Step 3: Verify startup doesn't crash**

```bash
cd backend && python -c "from app.main import app; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
rtk git add backend/app/scheduler.py backend/app/main.py
rtk git commit -m "refactor: extract scheduler into app/scheduler.py"
```

---

## Task 3: Create services/chat/llm.py (TDD)

**Files:**
- Create: `backend/app/services/chat/__init__.py`
- Create: `backend/app/services/chat/llm.py`
- Create: `backend/tests/services/test_chat_llm.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/services/test_chat_llm.py`:

```python
from unittest.mock import AsyncMock, patch, MagicMock
import pytest


def test_build_router_prompt_includes_agency_names():
    from app.services.chat.llm import build_router_prompt

    agencies = [
        {
            "id": "abc-123",
            "name": "กรมสรรพากร",
            "description": "ด้านภาษี",
            "connection_type": "API",
            "endpoint_url": "http://example.com",
            "data_scope": ["ภาษี", "VAT"],
        }
    ]
    result = build_router_prompt(agencies)

    assert "กรมสรรพากร" in result
    assert "abc-123" in result
    assert "ภาษี, VAT" in result


def test_build_router_prompt_empty_agencies():
    from app.services.chat.llm import build_router_prompt

    result = build_router_prompt([])
    assert "routes" in result
    assert "Available sources:" in result


@pytest.mark.asyncio
async def test_call_llm_raises_on_missing_key(monkeypatch):
    monkeypatch.setenv("PARSE_SPEC_API_KEY", "")

    from app.services.chat.llm import call_llm

    with pytest.raises(ValueError, match="Missing LLM API key"):
        await call_llm([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_call_llm_returns_message_on_success(monkeypatch):
    monkeypatch.setenv("PARSE_SPEC_API_KEY", "test-key")
    monkeypatch.setenv("PARSE_SPEC_URL", "http://fake-llm/v1/chat")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "hello"}}]
    }

    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        from app.services.chat.llm import call_llm
        result = await call_llm([{"role": "user", "content": "hi"}])

    assert result == {"role": "assistant", "content": "hello"}
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd backend && python -m pytest tests/services/test_chat_llm.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'app.services.chat'`

- [ ] **Step 3: Create `app/services/chat/__init__.py`**

```bash
touch backend/app/services/chat/__init__.py
```

- [ ] **Step 4: Create `app/services/chat/llm.py`**

```python
import logging
import os

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def call_llm(messages: list[dict]) -> dict:
    llm_api_key = os.getenv("PARSE_SPEC_API_KEY", "")
    if not llm_api_key:
        raise ValueError("Missing LLM API key")

    async with httpx.AsyncClient(timeout=settings.LLM_CALL_TIMEOUT) as client:
        resp = await client.post(
            os.getenv("PARSE_SPEC_URL", ""),
            headers={
                "apikey": llm_api_key,
                "Content-Type": "application/json",
            },
            json={
                "model": os.getenv("PARSE_SPEC_LLM_MODEL", "gpt-4o-mini"),
                "messages": messages,
            },
        )
    if resp.status_code == 200:
        return resp.json().get("choices", [{}])[0].get("message", {})
    raise ValueError(f"LLM API error: {resp.status_code} {resp.text}")


def build_router_prompt(agencies: list[dict]) -> str:
    source_lines = []
    for ag in agencies:
        scope = ", ".join(ag.get("data_scope", []))
        source_lines.append(
            f'- {ag["name"]} (id: {ag["id"]}, type: {ag["connection_type"]}, '
            f'endpoint: {ag.get("endpoint_url", "")}): '
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


async def classify_message_category(message_id: str, query: str, answer: str) -> None:
    content = f"""\
คุณเป็นโมเดลภาษา LLM ที่เชี่ยวชาญด้านการวิเคราะห์ข้อความและการจัดหมวดหมู่คำถามในบริบทของการให้บริการข้อมูลภาครัฐไทย
โปรดวิเคราะห์คำถามของผู้ใช้และระบุหมวดหมู่ที่ตรงที่สุด 1 หมวด จากนี้: สอบถามข้อมูล | ตรวจสอบสถานะ | ขั้นตอนดำเนินการ | กฎหมาย/ระเบียบ
ตอบเป็นข้อความที่มีเพียงหมวดหมู่ที่วิเคราะห์ได้เท่านั้น เช่น:
ขั้นตอนดำเนินการ

ถ้าคำถามไม่ชัดเจนหรือไม่สามารถจัดหมวดหมู่ได้ ให้ตอบว่า "ไม่สามารถจัดหมวดหมู่ได้"

คำถาม: {query}

คำตอบ: {answer}
"""
    payload = {
        "model": settings.CLASSIFICATION_MODEL,
        "messages": [{"role": "user", "content": content}],
    }
    async with httpx.AsyncClient(timeout=settings.LLM_CALL_TIMEOUT) as client:
        resp = await client.post(
            settings.OPENROUTER_API_URL,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
            json=payload,
        )
    try:
        from app.models.conversation import Message
        category = resp.json()["choices"][0]["message"]["content"].strip()
        await Message.filter(id=message_id).update(category=category)
    except Exception as e:
        logger.error("Error classifying message category: %s", e)


async def store_embedding(message_id: str, query: str) -> None:
    from app.services.embedding import generate_embedding, encode_embedding
    from app.models.conversation import Message
    embedding = await generate_embedding(query)
    if embedding is not None:
        encoded = encode_embedding(embedding)
        await Message.filter(id=message_id).update(embedding=encoded)
```

- [ ] **Step 5: Run tests — confirm they pass**

```bash
cd backend && python -m pytest tests/services/test_chat_llm.py -v
```

Expected: all 4 tests pass

- [ ] **Step 6: Commit**

```bash
rtk git add backend/app/services/chat/ backend/tests/services/test_chat_llm.py
rtk git commit -m "refactor: extract chat LLM utilities into services/chat/llm.py"
```

---

## Task 4: Create services/chat/graph.py + slim chat router

**Files:**
- Create: `backend/app/services/chat/graph.py`
- Modify: `backend/app/routers/chat.py`

- [ ] **Step 1: Create `app/services/chat/graph.py`**

This is a pure move of the LangGraph code from `routers/chat.py`. No logic changes except: API/MCP dispatch stubs become explicit errors, and `print()` calls are removed.

```python
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
```

- [ ] **Step 2: Rewrite `app/routers/chat.py`**

Replace the entire file with the slimmed version. The HTTP route handlers stay; the LangGraph code, LLM helpers, `main()` dev script, dead `LLM = ChatOpenAI(...)` block, and mid-file duplicate imports are all removed. `_store_embedding` and `classify_message_category` are now imported from `services/chat/llm.py`. `build_graph` is imported from `services/chat/graph.py`.

The new file structure (full content):

```python
"""
AI Chat router.

Endpoints
---------
  POST /chat            → delegates to /chat/external
  POST /chat/internal   → LangGraph multi-agent pipeline
  POST /chat/external   → OneChat v3 (sync JSON)
  POST /chat/stream     → OneChat v4 (SSE proxy)
"""

import asyncio
import json
import logging
import re
import time
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from opentelemetry import trace
from opentelemetry.trace import StatusCode
from tortoise.exceptions import DoesNotExist

from app.auth.dependencies import get_current_user_optional
from app.config import settings
from app.models.agency import Agency
from app.models.connection_log import ConnectionLog
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat.graph import build_graph
from app.services.chat.llm import classify_message_category, store_embedding
from app.services.embedding import generate_embedding
from app.services.similarity import find_similar_question
from app.services.session import ensure_session_warmed
from app.utils import generate_uuid, now

router = APIRouter(prefix="/chat", tags=["Chat"])
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)


# ─── Internal endpoint (LangGraph pipeline) ────────────────────────────────────

@router.post("/internal", summary="Send a query and get a synthesised AI response")
async def chat_internal(body: ChatRequest, user: User | None = Depends(get_current_user_optional)) -> ChatResponse:
    start = time.time()
    query = body.query.strip()

    if not query:
        return {"success": False, "error": "Missing query"}

    embedding = await generate_embedding(query)
    cached = await find_similar_question(query=query, embedding=embedding)
    if cached:
        user_msg, asst_msg = cached
        return {
            "success": True,
            "data": {
                "message_id": asst_msg.id,
                "answer": asst_msg.content,
                "references": asst_msg.sources if asst_msg.sources else [],
                "agentSteps": asst_msg.agent_steps if asst_msg.agent_steps else [],
                "agencies": [],
                "confidence": settings.SIMILARITY_THRESHOLD,
                "cached": True,
            },
            "conversation_id": str(user_msg.conversation_id),
            "responseTime": 0,
        }

    conversation_id = body.conversation_id or str(generate_uuid())
    result = await build_graph().ainvoke({"query": query, "conversation_id": conversation_id})
    response_time = int((time.time() - start) * 1000)
    answer = result.get("final_answer", "").strip()

    references = []
    if "<references>" in answer:
        parts = re.split(r"<references>(.*?)</references>", answer, flags=re.DOTALL)
        if len(parts) == 3:
            answer = parts[0].strip()
            try:
                references = json.loads(parts[1].strip())
            except json.JSONDecodeError:
                references = []

    category = None
    if "<category>" in answer:
        parts = re.split(r"<category>(.*?)</category>", answer, flags=re.DOTALL)
        if len(parts) == 3:
            category = parts[1].strip()

    if not body.conversation_id:
        conv = await Conversation.create(
            id=conversation_id,
            title=query[:settings.TITLE_MAX_LENGTH],
            preview=query[:settings.PREVIEW_MAX_LENGTH],
            agencies=[],
            status="success",
            message_count=len(answer),
            response_time=response_time,
            user_id=user.id if user else None,
        )
    else:
        conv = await Conversation.get(id=conversation_id)
        conv.message_count += len(answer)
        await conv.save()

    query_msg = await Message.create(
        conversation_id=conversation_id,
        role="user",
        content=query,
        agent_steps=[],
        sources=[],
        category=category,
    )

    asyncio.create_task(store_embedding(str(query_msg.id), query))

    response_msg = await Message.create(
        conversation_id=conversation_id,
        role="assistant",
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


# ─── External endpoint (OneChat v3) ────────────────────────────────────────────

@router.post("/external", summary="Send a query and get a synthesised AI response")
async def chat_external(body: ChatRequest, background_tasks: BackgroundTasks, user: User | None = Depends(get_current_user_optional)) -> ChatResponse:
    with tracer.start_as_current_span("chat_external_endpoint") as span:
        query = body.query.strip()
        conversation_id = body.conversation_id or str(generate_uuid())

        if body.conversation_id:
            try:
                conv = await Conversation.get(id=conversation_id)
            except DoesNotExist:
                raise HTTPException(status_code=404, detail="Conversation not found")

        if not query:
            span.set_status(StatusCode.ERROR, "Missing query")
            raise HTTPException(status_code=400, detail="Missing query")

        if not body.conversation_id:
            embedding = await generate_embedding(query)
            cached = await find_similar_question(query=query, embedding=embedding)
            if cached:
                user_msg, asst_msg = cached
                span.set_attribute("cache_hit", True)
                return {
                    "success": True,
                    "data": {
                        "message_id": asst_msg.id,
                        "answer": asst_msg.content,
                        "references": asst_msg.sources if asst_msg.sources else [],
                        "agentSteps": asst_msg.agent_steps if asst_msg.agent_steps else [],
                        "agencies": [],
                        "confidence": settings.SIMILARITY_THRESHOLD,
                        "cached": True,
                    },
                    "conversation_id": str(user_msg.conversation_id),
                    "responseTime": 0,
                }
        else:
            try:
                await ensure_session_warmed(conv, settings.ONECHAT_V3_URL, settings.MCP_ENDPOINT_URL)
            except Exception:
                logger.warning("Session warm-up failed for conversation %s", conversation_id)

        payload = {"query": query, "mcp_endpoint_url": settings.MCP_ENDPOINT_URL, "session_id": conversation_id}

        async with httpx.AsyncClient(timeout=settings.EXTERNAL_CHAT_TIMEOUT) as client:
            start_time_ns = time.perf_counter_ns()
            resp = await client.post(settings.ONECHAT_V3_URL, headers={"Content-Type": "application/json"}, json=payload)
            end_time_ns = time.perf_counter_ns()

        if resp.status_code != 200:
            span.set_status(StatusCode.ERROR, f"External chat request failed with status {resp.status_code}")
            raise HTTPException(status_code=502, detail="Failed to get response from external chat service")

        response_time = int((end_time_ns - start_time_ns) // 1_000_000)
        raw_data = resp.json()
        span.set_attributes({"external_response": resp.text})

        await ConnectionLog.create(
            id=str(generate_uuid()),
            action="query",
            connection_type="external_chat",
            status="success",
            latency_ms=response_time,
            detail=f"Query: {query}\n\nAnswer: {raw_data}",
            request_body=json.dumps(payload),
            response_body=json.dumps(raw_data),
        )

        data = raw_data.get("data", {})
        answer = data.get("answer", "").strip()
        errors = data.get("errors", [])

        agency_ids = []
        if "data" in raw_data and "sections" in raw_data["data"]:
            for sec in raw_data["data"]["sections"]:
                if "agencies" in sec:
                    agency_ids.extend([ag["id"] for ag in sec["agencies"]])

        if not body.conversation_id:
            conv = await Conversation.create(
                id=conversation_id,
                title=query[:settings.TITLE_MAX_LENGTH],
                preview=query[:settings.PREVIEW_MAX_LENGTH],
                agencies=[],
                status="success",
                message_count=len(answer),
                response_time=response_time,
                user_id=user.id if user else None,
                external_session_id=data.get("session_id"),
            )
        else:
            conv.message_count += len(answer)
            conv.updated_at = now()
            await conv.save()

        query_msg = await Message.create(conversation_id=conversation_id, role="user", content=query)
        response_msg = await Message.create(
            parent_id=query_msg.id,
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            response_time=response_time,
            errors=errors,
            agency_ids=agency_ids,
        )

        background_tasks.add_task(classify_message_category, query_msg.id, query, answer)
        background_tasks.add_task(store_embedding, str(query_msg.id), query)

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


# ─── Stream endpoint (OneChat v4 SSE) ─────────────────────────────────────────

@router.post("/stream", summary="Send a query and receive SSE streaming response (v4)")
async def chat_stream(body: ChatRequest, request: Request, background_tasks: BackgroundTasks, user: User | None = Depends(get_current_user_optional)):
    """Proxy to OneChat v4 SSE endpoint, re-emit events to client, save conversation after answer."""
    query = body.query.strip()
    conversation_id = body.conversation_id or str(generate_uuid())

    with tracer.start_as_current_span("chat_stream_endpoint") as span:
        span.set_attribute("conversation_id", conversation_id)

        if not query:
            span.set_status(StatusCode.ERROR, "Missing query")
            raise HTTPException(status_code=400, detail="Missing query")

        span.set_attribute("query", query)

        if not body.conversation_id:
            embedding = await generate_embedding(query)
            cached = await find_similar_question(query=query, embedding=embedding)
            if cached:
                user_msg, asst_msg, conn_log = cached

                async def cached_stream():
                    await asyncio.sleep(0.01)
                    span.set_attribute("cache_hit", True)
                    await _save_stream_conversation(
                        query=query,
                        conversation_id=conversation_id,
                        answer_data=json.loads(conn_log.response_body),
                        session_id=None,
                        total_ms=0,
                        latency_ms=0,
                        user=user,
                        background_tasks=background_tasks,
                    )
                    yield _sse_event("answer", {"answer": asst_msg.content})
                    yield _sse_event("done", {"session_id": conversation_id, "total_ms": 0})

                return StreamingResponse(cached_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
        else:
            try:
                conv = await Conversation.get(id=conversation_id)
            except DoesNotExist:
                span.set_status(StatusCode.ERROR, "Conversation not found for session warm-up")
                raise HTTPException(status_code=404, detail="Conversation not found")
            try:
                await ensure_session_warmed(conv, settings.ONECHAT_V3_URL, settings.MCP_ENDPOINT_URL)
            except Exception:
                logger.warning("Session warm-up failed for conversation %s", conversation_id)
                span.set_status(StatusCode.WARNING, "Session warm-up failed")

        payload = {"query": query, "mcp_endpoint_url": settings.MCP_ENDPOINT_URL, "session_id": conversation_id}

        async def event_generator():
            answer_data = None
            session_id = None
            total_ms = None
            start_ns = time.perf_counter_ns()
            log_latency_ms = 0

            try:
                async with httpx.AsyncClient(timeout=settings.V4_STREAM_TIMEOUT) as client:
                    async with client.stream("POST", settings.ONECHAT_V4_URL, headers={"Content-Type": "application/json"}, json=payload) as resp:
                        if resp.status_code != 200:
                            error_msg = f"OneChat v4 returned {resp.status_code}"
                            try:
                                error_body = await resp.aread()
                                error_msg = f"OneChat v4 returned {resp.status_code}: {error_body.decode()[:200]}"
                            except Exception:
                                pass
                            span.set_status(StatusCode.ERROR, error_msg)
                            yield _sse_event("error", {"message": error_msg, "code": resp.status_code})
                            yield _sse_event("done", {"session_id": conversation_id, "total_ms": 0})
                            return

                        log_latency_ms = int((time.perf_counter_ns() - start_ns) // 1_000_000)
                        buffer = ""
                        async for chunk in resp.aiter_text():
                            buffer += chunk
                            while "\n\n" in buffer:
                                event_block, buffer = buffer.split("\n\n", 1)
                                parsed = _parse_sse_block(event_block)
                                if not parsed:
                                    continue
                                event_name, event_data = parsed
                                if event_name == "answer":
                                    answer_data = event_data
                                elif event_name == "done":
                                    session_id = event_data.get("session_id")
                                    total_ms = event_data.get("total_ms")
                                with tracer.start_as_current_span("event") as event_span:
                                    event_span.set_attribute("stream_event", event_name)
                                    event_span.set_attribute("event_data", json.dumps(event_data)[:500])
                                if event_name == "done":
                                    yield _sse_event(event_name, {**event_data, "session_id": conversation_id})
                                else:
                                    yield _sse_event(event_name, event_data)

            except httpx.ReadTimeout:
                span.set_status(StatusCode.ERROR, "OneChat v4 stream read timeout")
                yield _sse_event("error", {"message": "OneChat v4 connection timed out", "code": 504})
                yield _sse_event("done", {"session_id": conversation_id, "total_ms": 0})
                return
            except Exception as e:
                span.set_status(StatusCode.ERROR, f"Exception during OneChat v4 streaming: {e}")
                yield _sse_event("error", {"message": str(e), "code": 500})
                yield _sse_event("done", {"session_id": conversation_id, "total_ms": 0})
                return

            if answer_data:
                await _save_stream_conversation(
                    query=query,
                    conversation_id=conversation_id,
                    answer_data=answer_data,
                    session_id=session_id,
                    total_ms=total_ms,
                    latency_ms=log_latency_ms,
                    user=user,
                    background_tasks=background_tasks,
                )

        return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ─── Default route (delegates to /external) ───────────────────────────────────

@router.post("", summary="Send a query and get a synthesised AI response")
async def chat(body: ChatRequest, background_tasks: BackgroundTasks, user: User | None = Depends(get_current_user_optional)) -> ChatResponse:
    with tracer.start_as_current_span("chat_endpoint"):
        return await chat_external(body, background_tasks, user)


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def _sse_event(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _parse_sse_block(block: str) -> tuple[str, Any] | None:
    event_name = "message"
    data_line = None
    for line in block.strip().split("\n"):
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_line = line[5:].strip()
    if not data_line:
        return None
    try:
        return event_name, json.loads(data_line)
    except json.JSONDecodeError:
        return None


async def _save_stream_conversation(
    *,
    query: str,
    conversation_id: str,
    answer_data: dict,
    session_id: str | None,
    total_ms: int | None,
    latency_ms: int,
    user: User | None,
    background_tasks: BackgroundTasks,
) -> None:
    answer = answer_data.get("answer", "").strip()
    errors = answer_data.get("errors", [])
    sections = answer_data.get("sections", [])

    agency_ids = []
    for sec in sections:
        if "agencies" in sec:
            agency_ids.extend([ag["id"] for ag in sec["agencies"]])

    response_time = total_ms if total_ms else latency_ms

    try:
        conv = await Conversation.get(id=conversation_id)
        conv.message_count += len(answer)
        conv.updated_at = now()
        await conv.save()
    except Exception:
        await Conversation.create(
            id=conversation_id,
            title=query[:50],
            preview=query[:100],
            agencies=[],
            status="success",
            message_count=len(answer),
            response_time=response_time,
            user_id=user.id if user else None,
            external_session_id=session_id,
        )

    query_msg = await Message.create(conversation_id=conversation_id, role="user", content=query)
    assistant_msg = await Message.create(
        parent_id=query_msg.id,
        conversation_id=conversation_id,
        role="assistant",
        content=answer,
        response_time=response_time,
        errors=errors,
        agency_ids=agency_ids,
    )

    await ConnectionLog.create(
        id=str(generate_uuid()),
        action="query",
        connection_type="external_chat_v4",
        status="success",
        latency_ms=latency_ms,
        detail=f"v4 stream query: {query[:100]}",
        request_body=json.dumps({"query": query, "session_id": conversation_id}),
        response_body=json.dumps(answer_data, ensure_ascii=False),
        message_id=query_msg.id,
        assistant_message_id=assistant_msg.id,
    )

    background_tasks.add_task(classify_message_category, query_msg.id, query, answer)
    background_tasks.add_task(store_embedding, str(query_msg.id), query)
```

- [ ] **Step 3: Verify import graph is clean**

```bash
cd backend && python -c "from app.routers.chat import router; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Run existing tests**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
rtk git add backend/app/services/chat/graph.py backend/app/routers/chat.py
rtk git commit -m "refactor: extract LangGraph into services/chat/graph.py, slim chat router to 200 lines"
```

---

## Task 5: Create services/agency.py + slim agencies router

**Files:**
- Create: `backend/app/services/agency.py`
- Modify: `backend/app/routers/agencies.py`
- Create: `backend/tests/services/test_agency.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/services/test_agency.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.mark.asyncio
async def test_test_rest_returns_error_on_timeout():
    from app.services.agency import _test_rest

    agency = MagicMock()
    agency.endpoint_url = "http://unreachable-host:9999/"

    import httpx
    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.head.side_effect = httpx.TimeoutException("timeout")
        mock_client.get.side_effect = httpx.TimeoutException("timeout")
        MockClient.return_value.__aenter__.return_value = mock_client

        result = await _test_rest(agency)

    assert result["success"] is False
    assert "timeout" in result["error"].lower() or "timeout" in result["latency"].lower() or result["latency"] != "0ms"


@pytest.mark.asyncio
async def test_test_rest_missing_url():
    from app.services.agency import _test_rest

    agency = MagicMock()
    agency.endpoint_url = ""

    result = await _test_rest(agency)

    assert result["success"] is False
    assert "required" in result["error"].lower()


@pytest.mark.asyncio
async def test_test_connection_dispatches_by_type():
    from app.services.agency import test_connection

    agency = MagicMock()
    agency.endpoint_url = ""

    with patch("app.services.agency._test_rest", new_callable=AsyncMock) as mock_rest:
        mock_rest.return_value = {"success": True, "protocol": "REST API", "version": "v1", "steps": [], "latency": "5ms"}
        result = await test_connection("API", agency)

    mock_rest.assert_awaited_once_with(agency)
    assert result["protocol"] == "REST API"
```

- [ ] **Step 2: Confirm tests fail**

```bash
cd backend && python -m pytest tests/services/test_agency.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'app.services.agency'`

- [ ] **Step 3: Create `app/services/agency.py`**

Move `_test_rest`, `_test_mcp`, `_test_a2a`, `_run_connection_test`, and `parse_api_spec` logic from `routers/agencies.py`. Rename `_run_connection_test` → `test_connection` and extract the spec parse body into `parse_spec(spec_text: str) -> dict`.

```python
import json as _json
import time
import uuid
from typing import Any

import httpx

from app.config import settings
from app.models.agency import Agency


async def test_connection(connection_type: str, agency: Agency) -> dict[str, Any]:
    if connection_type == "API":
        return await _test_rest(agency)
    if connection_type == "MCP":
        return await _test_mcp(agency)
    if connection_type == "A2A":
        return await _test_a2a(agency)
    return {
        "success": False,
        "protocol": "UNKNOWN",
        "version": "-",
        "steps": [],
        "latency": "0ms",
        "error": "Unsupported connection type",
    }


async def parse_spec(spec_text: str) -> dict[str, Any]:
    payload = {
        "model": settings.PARSE_SPEC_LLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are an API specification parser. Extract structured information from OpenAPI/Swagger specs including response schemas.",
            },
            {
                "role": "user",
                "content": f"Parse this API specification and extract the details including response field schemas:\n\n{spec_text[:settings.SPEC_TEXT_MAX_CHARS]}",
            },
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "extract_api_spec",
                    "description": "Extract structured API specification details including response schemas",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "auth_method": {"type": "string", "enum": ["api_key", "oauth2", "basic_auth", "none"]},
                            "auth_header": {"type": "string"},
                            "base_path": {"type": "string"},
                            "rate_limit_rpm": {"type": "integer"},
                            "request_format": {"type": "string", "enum": ["json", "xml"]},
                            "endpoints": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]},
                                        "path": {"type": "string"},
                                        "description": {"type": "string"},
                                    },
                                    "required": ["method", "path", "description"],
                                    "additionalProperties": False,
                                },
                            },
                            "response_schema": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "field": {"type": "string"},
                                        "type": {"type": "string"},
                                        "description": {"type": "string"},
                                        "example": {"type": "string"},
                                    },
                                    "required": ["field", "type", "description"],
                                    "additionalProperties": False,
                                },
                            },
                        },
                        "required": ["auth_method", "auth_header", "base_path", "request_format", "endpoints", "response_schema"],
                        "additionalProperties": False,
                    },
                },
            }
        ],
        "tool_choice": {"type": "function", "function": {"name": "extract_api_spec"}},
    }

    async with httpx.AsyncClient(timeout=settings.PARSE_SPEC_TIMEOUT) as client:
        resp = await client.post(
            settings.PARSE_SPEC_URL,
            headers={"Content-Type": "application/json", "apikey": settings.PARSE_SPEC_API_KEY},
            json=payload,
        )

    if not resp.is_success:
        try:
            data = resp.json()
        except Exception:
            data = {}
        raise ValueError(data.get("message", f"HTTP {resp.status_code}"))

    data = resp.json()
    tool_call = (data.get("choices") or [{}])[0].get("message", {}).get("tool_calls", [{}])[0]
    args_raw = tool_call.get("function", {}).get("arguments")

    if not args_raw:
        raise ValueError("Failed to parse specification")

    return _json.loads(args_raw)


async def _test_rest(agency: Agency) -> dict[str, Any]:
    url = agency.endpoint_url.strip()
    if not url:
        return {"success": False, "protocol": "REST API", "version": "-", "steps": [], "latency": "0ms", "error": "Endpoint URL is required"}

    steps: list[dict] = []
    total_start = time.monotonic()
    headers = {"User-Agent": f"{settings.USER_AGENT_PREFIX} ConnectionTest"}

    s1 = time.monotonic()
    response = None
    fetch_error: str | None = None

    async with httpx.AsyncClient(timeout=settings.CONNECTION_TEST_TIMEOUT) as client:
        try:
            response = await client.head(url, headers=headers)
        except Exception:
            try:
                response = await client.get(url, headers=headers)
            except httpx.TimeoutException:
                fetch_error = f"Connection timeout ({settings.CONNECTION_TEST_TIMEOUT}s)"
            except Exception as exc:
                fetch_error = str(exc)

    s1_ms = int((time.monotonic() - s1) * 1000)
    steps.append({"step": 1, "label": "TCP Connection", "status": "error" if fetch_error else "done", "time": s1_ms})

    if fetch_error:
        total_ms = int((time.monotonic() - total_start) * 1000)
        steps.append({"step": 2, "label": "HTTP Response", "status": "error", "time": 0})
        return {"success": False, "protocol": "REST API", "version": "-", "steps": steps, "latency": f"{total_ms}ms", "error": fetch_error}

    status_code = response.status_code
    steps.append({"step": 2, "label": f"HTTP {status_code} {response.reason_phrase}", "status": "done" if status_code < 500 else "error", "time": s1_ms})

    content_type = response.headers.get("content-type", "unknown").split(";")[0]
    server = response.headers.get("server", "unknown")
    steps.append({"step": 3, "label": f"Content-Type: {content_type}", "status": "done", "time": 0})

    total_ms = int((time.monotonic() - total_start) * 1000)
    is_success = 200 <= status_code < 500
    steps.append({"step": 4, "label": "API Reachable" if is_success else "API Error", "status": "done" if is_success else "error", "time": 0})

    return {
        "success": is_success,
        "protocol": "REST API",
        "version": "v1",
        "steps": steps,
        "latency": f"{total_ms}ms",
        "statusCode": status_code,
        "statusText": response.reason_phrase,
        "server": server,
        "contentType": content_type,
    }


async def _test_mcp(agency: Agency) -> dict[str, Any]:
    steps: list[dict] = []
    total_start = time.monotonic()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": f"{settings.USER_AGENT_PREFIX} MCPProbe",
    }

    if not agency.endpoint_url:
        return {"success": False, "protocol": "MCP", "version": "-", "steps": [], "latency": "0ms", "error": "Endpoint URL is required"}

    url = agency.endpoint_url.strip()

    try:
        async with httpx.AsyncClient(timeout=settings.CONNECTION_TEST_TIMEOUT) as client:
            init_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": settings.MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": settings.USER_AGENT_PREFIX.split("/")[0], "version": settings.MCP_CLIENT_VERSION},
                },
            }
            s1 = time.monotonic()
            s1_ms = int((time.monotonic() - s1) * 1000)
            steps.append({"step": 1, "label": "TCP Connection", "status": "done", "time": s1_ms})

            s2 = time.monotonic()
            resp = await client.post(url, json=init_payload, headers=headers)
            s2_ms = int((time.monotonic() - s2) * 1000)

            if resp.status_code >= 500:
                steps.append({"step": 2, "label": f"MCP Handshake — HTTP {resp.status_code}", "status": "error", "time": s2_ms})
                total_ms = int((time.monotonic() - total_start) * 1000)
                return {"success": False, "protocol": "MCP", "version": "-", "steps": steps, "latency": f"{total_ms}ms", "error": f"Server error: HTTP {resp.status_code}"}

            steps.append({"step": 2, "label": "MCP Handshake", "status": "done", "time": s2_ms})

            s3 = time.monotonic()
            try:
                body = resp.json()
            except Exception:
                body = {}

            result = body.get("result", {})
            server_info = result.get("serverInfo", {})
            raw_caps = result.get("capabilities", {})
            protocol_version = result.get("protocolVersion", "unknown")

            capabilities: list[str] = []
            for group, val in raw_caps.items():
                if isinstance(val, dict):
                    for method in val:
                        capabilities.append(f"{group}/{method}")
                else:
                    capabilities.append(group)
            if not capabilities:
                capabilities = list(raw_caps.keys()) or ["(none advertised)"]

            s3_ms = int((time.monotonic() - s3) * 1000)
            steps.append({"step": 3, "label": f"Capability Exchange — {len(capabilities)} cap(s)", "status": "done", "time": s3_ms})
            steps.append({"step": 4, "label": "Session Established", "status": "done", "time": 0})

    except httpx.TimeoutException:
        total_ms = int((time.monotonic() - total_start) * 1000)
        if not steps:
            steps.append({"step": 1, "label": "TCP Connection", "status": "error", "time": total_ms})
        steps.append({"step": 2, "label": "MCP Handshake", "status": "error", "time": 0})
        return {"success": False, "protocol": "MCP", "version": "-", "steps": steps, "latency": f"{total_ms}ms", "error": f"Connection timeout ({settings.CONNECTION_TEST_TIMEOUT}s)"}
    except Exception as exc:
        total_ms = int((time.monotonic() - total_start) * 1000)
        if not steps:
            steps.append({"step": 1, "label": "TCP Connection", "status": "error", "time": total_ms})
        return {"success": False, "protocol": "MCP", "version": "-", "steps": steps, "latency": f"{total_ms}ms", "error": str(exc)}

    total_ms = int((time.monotonic() - total_start) * 1000)
    return {
        "success": True,
        "protocol": "MCP",
        "version": protocol_version,
        "steps": steps,
        "latency": f"{total_ms}ms",
        "capabilities": capabilities,
        "serverInfo": server_info,
    }


async def _test_a2a(agency: Agency) -> dict[str, Any]:
    steps: list[dict] = []
    total_start = time.monotonic()

    if not agency.endpoint_url:
        return {"success": False, "protocol": "A2A", "version": "-", "steps": [], "latency": "0ms", "error": "Endpoint URL is required"}

    rpc_headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": f"{settings.USER_AGENT_PREFIX} A2AProbe"}

    try:
        async with httpx.AsyncClient(timeout=settings.CONNECTION_TEST_TIMEOUT, follow_redirects=True) as client:
            s1 = time.monotonic()
            await client.get(agency.endpoint_url)
            steps.append({"step": 1, "label": "TCP Connection", "status": "done", "time": int((time.monotonic() - s1) * 1000)})

            chat_payload = {"session_id": uuid.uuid4().hex, "query": "ทดสอบการเชื่อมต่อ"}
            s2 = time.monotonic()
            try:
                await client.post(agency.endpoint_url, json=chat_payload, headers=rpc_headers)
                s2_ms = int((time.monotonic() - s2) * 1000)
                steps.append({"step": 2, "label": "Chat Query", "status": "done", "time": s2_ms})
            except Exception as chat_exc:
                s2_ms = int((time.monotonic() - s2) * 1000)
                steps.append({"step": 2, "label": f"Chat failed — {chat_exc}", "status": "error", "time": s2_ms})

    except httpx.TimeoutException:
        total_ms = int((time.monotonic() - total_start) * 1000)
        if not steps:
            steps.append({"step": 1, "label": "TCP Connection", "status": "error", "time": total_ms})
        if len(steps) < 4:
            steps.append({"step": len(steps) + 1, "label": "Timeout", "status": "error", "time": 0})
        return {"success": False, "protocol": "A2A", "version": "-", "steps": steps, "latency": f"{total_ms}ms", "error": f"Connection timeout ({settings.CONNECTION_TEST_TIMEOUT}s)"}
    except Exception as exc:
        total_ms = int((time.monotonic() - total_start) * 1000)
        if not steps:
            steps.append({"step": 1, "label": "TCP Connection", "status": "error", "time": total_ms})
        return {"success": False, "protocol": "A2A", "version": "-", "steps": steps, "latency": f"{total_ms}ms", "error": str(exc)}

    total_ms = int((time.monotonic() - total_start) * 1000)
    return {"success": True, "protocol": "A2A", "version": "-", "steps": steps, "latency": f"{total_ms}ms"}
```

- [ ] **Step 4: Update `app/routers/agencies.py`**

Remove `_run_connection_test`, `_test_rest`, `_test_mcp`, `_test_a2a`, and the spec-parse LLM body. Add these imports at the top:

```python
from app.services.agency import test_connection, parse_spec
```

Replace the `test_connection` route handler body:

```python
@router.get("/{agency_id}/test", response_model=TestConnectionResponse, summary="Test agency connection and record a connection log")
async def test_connection_endpoint(agency_id: uuid.UUID, _: User = Depends(require_admin)) -> TestConnectionResponse:
    try:
        agency = await Agency.get(id=agency_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")

    raw = await test_connection(agency.connection_type, agency)

    agent_card_raw = raw.get("agentCard")
    response = TestConnectionResponse(
        success=raw["success"],
        protocol=raw["protocol"],
        version=raw["version"],
        steps=[TestStep(**s) for s in raw.get("steps", [])],
        latency=raw["latency"],
        error=raw.get("error"),
        status_code=raw.get("statusCode"),
        status_text=raw.get("statusText"),
        server=raw.get("server"),
        content_type=raw.get("contentType"),
        capabilities=raw.get("capabilities"),
        server_info=raw.get("serverInfo"),
        agent_card=AgentCardInfo(**agent_card_raw) if agent_card_raw else None,
    )

    latency_ms = int(response.latency.replace("ms", ""))
    await ConnectionLog.create(
        agency=agency,
        action="test",
        connection_type=agency.connection_type,
        status="success" if response.success else "error",
        latency_ms=latency_ms,
        detail=response.error or (f"HTTP {response.status_code}" if response.status_code else response.protocol),
    )

    return response
```

Replace the `parse_api_spec` route handler body (remove everything after the guard clause, delete the dead unreachable block at the bottom of the file entirely):

```python
@router.post("/parse-spec", summary="Parse an OpenAPI spec via LLM and extract structured metadata")
async def parse_api_spec(body: ParseSpecRequest):
    if not body.spec_text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="spec_text is required")

    try:
        parsed = await parse_spec(body.spec_text)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"gateway error: {exc}")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return {"success": True, "data": parsed}
```

Also delete the dead code block (lines after `return {"success": True, "data": parsed}` through end of file — the unreachable `lovable_api_key` block).

- [ ] **Step 5: Run tests — confirm they pass**

```bash
cd backend && python -m pytest tests/services/test_agency.py -v
```

Expected: all 3 tests pass

- [ ] **Step 6: Verify router import**

```bash
cd backend && python -c "from app.routers.agencies import router; print('ok')"
```

Expected: `ok`

- [ ] **Step 7: Commit**

```bash
rtk git add backend/app/services/agency.py backend/app/routers/agencies.py backend/tests/services/test_agency.py
rtk git commit -m "refactor: extract agency test/parse logic into services/agency.py"
```

---

## Task 6: Create services/analytics.py + slim analytics routers

**Files:**
- Create: `backend/app/services/analytics.py`
- Modify: `backend/app/routers/dashboard.py`
- Modify: `backend/app/routers/insight.py`
- Modify: `backend/app/routers/executive_summary.py`

- [ ] **Step 1: Create `app/services/analytics.py`**

Move the entire DB query bodies from each analytics router into typed async functions. The routers call these functions and return the result directly.

`get_dashboard_stats` is fully specified below. For `get_agency_health` and `get_executive_summary`, copy the full body of the corresponding route handler verbatim from `routers/insight.py` and `routers/executive_summary.py` — including all imports used (add them at top of analytics.py) and the exact Pydantic model construction in the return statement. Use the same return type as the original handler annotation (`AgencyHealthData` and `ExecutiveData` respectively).

```python
from datetime import timedelta

from tortoise.expressions import RawSQL
from tortoise.functions import Count
from tortoise.transactions import in_transaction

from app.config import settings
from app.utils import now


async def get_dashboard_stats() -> dict:
    async with in_transaction() as conn:
        await conn.execute_query(f"SET TIME ZONE '{settings.TIMEZONE}';")

        from app.models.conversation import Message
        from app.models.agency import Agency

        stats = {
            "totalQuestions": 0,
            "totalQuestionsTrend": 0.0,
            "todayQuestions": 0,
            "todayQuestionsTrend": 0.0,
            "avgResponseTime": 0.0,
            "avgResponseTimeTrend": 0.0,
            "satisfactionRate": 0.0,
            "satisfactionRateTrend": 0.0,
        }

        stats["totalQuestions"] = await Message.filter(role="user").count()

        today_start = now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now().replace(hour=23, minute=59, second=59, microsecond=999999)
        stats["todayQuestions"] = await Message.filter(role="user", created_at__range=(today_start, today_end)).count()

        avg_response_time = await Message.annotate(avg_time=RawSQL("AVG(response_time) / 1000")).values("avg_time")
        avg_response_time = avg_response_time[0]["avg_time"] if avg_response_time else 0
        stats["avgResponseTime"] = float(round(avg_response_time or 0, 2))

        rate = await Message.annotate(rate=RawSQL("avg(case when rating = 'up' then 1 else 0 end) * 100")).filter(rating__isnull=False).values("rate")
        rate = rate[0]["rate"] if rate else 0
        stats["satisfactionRate"] = float(round(rate or 0, 2))

        agency_usage = [
            {"name": a["name"], "value": a["total_calls"], "fill": a["color"]}
            for a in await Agency.all().values("name", "color", "total_calls")
        ]

        day_names = ["อาทิตย์", "จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์"]
        raw_weekly = await conn.execute_query_dict(
            """
            SELECT EXTRACT(DOW FROM created_at)::int AS dow, COUNT(*) AS questions
            FROM messages
            WHERE role = 'user' and created_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY dow
            """
        )
        dow_map = {row["dow"]: row["questions"] for row in raw_weekly}
        weekly_trend = [{"day": day_names[i], "questions": dow_map.get(i, 0)} for i in range(len(day_names))]

        categories = (
            await Message.filter(category__isnull=False)
            .annotate(cnt=Count("id"))
            .group_by("category")
            .values("category", "cnt")
        )
        category_data = sorted(
            [{"category": row["category"], "count": row["cnt"]} for row in categories],
            key=lambda x: x["count"],
            reverse=True,
        )

        return {
            "stats": stats,
            "agencyUsage": agency_usage,
            "weeklyTrend": weekly_trend,
            "categoryData": category_data,
        }
```

For `get_agency_health` and `get_executive_summary`: open `routers/insight.py` and `routers/executive_summary.py`, copy the full `async with in_transaction()` block (and return statement) from each route handler verbatim into correspondingly-named functions in `analytics.py`. Preserve the original return type annotation: `async def get_agency_health() -> AgencyHealthData` and `async def get_executive_summary() -> ExecutiveData` (import these from `app.schemas.insight` and `app.schemas.executive_summary` respectively).

- [ ] **Step 2: Update `app/routers/dashboard.py`**

Replace the entire route handler body with a call to the service:

```python
import time

from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.services.analytics import get_dashboard_stats

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", summary="Get dashboard statistics and charts data")
async def dashboard_stats(user: User = Depends(get_current_user)) -> dict:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="ไม่สามารถเข้าถึงข้อมูลนี้ได้")

    start = time.time()
    data = await get_dashboard_stats()
    return {"success": True, "data": data, "responseTime": int((time.time() - start) * 1000)}
```

- [ ] **Step 3: Update `app/routers/insight.py`**

Import from analytics service and replace each route handler's DB query block with a service call. Handlers that were already stubs (returning zeros) can stay as-is or call through:

```python
from fastapi import APIRouter
from app.services.analytics import get_agency_health
from app.schemas.insight import AnalyticsInsightsData, AgencyHealthData
from app.utils import now

router = APIRouter(tags=["insight"])


@router.get("/analytics-insights")
async def get_insight_analytics_insights() -> AnalyticsInsightsData:
    return AnalyticsInsightsData(
        totalWeekQuestions=0,
        topicClusters=[],
        sentimentDist={"positive": 0, "neutral": 0, "negative": 0},
        noAnswerByAgency=[],
        dailyVolume=[],
        trendingTopics=[],
        decliningTopics=[],
        aiInsights="",
        recommendations=[],
        generatedAt=now(),
    )


@router.get("/agency-health")
async def get_insight_agency_health() -> AgencyHealthData:
    return await get_agency_health()
```

- [ ] **Step 4: Update `app/routers/executive_summary.py`**

```python
from fastapi import APIRouter
from app.schemas.executive_summary import ExecutiveData
from app.services.analytics import get_executive_summary

router = APIRouter(tags=["executive"])


@router.get("/executive-summary")
async def executive_summary_endpoint() -> ExecutiveData:
    return await get_executive_summary()
```

- [ ] **Step 5: Verify all router imports**

```bash
cd backend && python -c "
from app.routers.dashboard import router as d
from app.routers.insight import router as i
from app.routers.executive_summary import router as e
print('ok')
"
```

Expected: `ok`

- [ ] **Step 6: Run all tests**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
rtk git add backend/app/services/analytics.py backend/app/routers/dashboard.py backend/app/routers/insight.py backend/app/routers/executive_summary.py
rtk git commit -m "refactor: extract analytics queries into services/analytics.py, slim analytics routers"
```

---

## Task 7: Invoke finishing skill

- [ ] **Step 1: Run final verification**

```bash
cd backend && python -c "from app.main import app; print('ok')"
cd backend && python -m pytest tests/ -v
```

Expected: both succeed

- [ ] **Step 2: Invoke finishing skill**

Use `superpowers:finishing-a-development-branch` to decide how to integrate the branch.
