"""
AI Chatbot Portal — FastAPI Backend
=====================================
Stack:  FastAPI · Tortoise ORM · FastMCP
DB:     PostgreSQL

Entry-point:
    uvicorn app.main:app --reload

MCP server:
  - SSE transport  →  GET /sse   (opens stream, server emits session endpoint URL)
                      POST /messages/  (send JSON-RPC commands, ref session_id query param)
  - Streamable-HTTP →  /mcp/  (legacy mount, kept for backward compat)
REST API is served under /api/v1
"""

import asyncio
import json
import logging
import random
import time

import httpx

class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("/health") == -1

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.database import init_db, close_db
from app.mcp.server import mcp
from app.routers import agencies, conversations, messages, dashboard, feedback, auth, seed, chat, connection_logs, api_key, executive_summary, insight
from app.routers.seed import _run_seed_admin, _run_seed_agencies
from app.models import Agency, ConnectionLog
from app.utils import generate_uuid, now

mcp_app = mcp.http_app(path="/")

# ---------------------------------------------------------------------------
# SSE transport — GET /sse + POST /messages/
# (follows OneChat MCP SSE spec: server generates session_id, no pre-auth needed)
# ---------------------------------------------------------------------------

_sse_transport = SseServerTransport("/messages/")


async def _sse_handler(request: Request) -> Response:
    """Open an SSE stream; server auto-generates session_id and emits endpoint URL."""
    async with _sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp._mcp_server.run(
            streams[0],
            streams[1],
            mcp._mcp_server.create_initialization_options(),
        )
    return Response()

# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _run_seed_admin()
    await _run_seed_agencies()
    await start_scheduler()

    async with mcp_app.lifespan(app):
        yield

    await stop_scheduler()
    await close_db()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Central AI Chatbot Portal API.\n\n"
        "**MCP SSE** (OneChat-compatible): `GET /sse` → open stream, `POST /messages/` → send commands.\n\n"
        "**MCP Streamable-HTTP** (legacy): available at `/mcp`.\n\n"
        "**REST API** endpoints are under `/api/v1`."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# REST routers
# ---------------------------------------------------------------------------

app.include_router(auth.router, prefix="/api/v1")
# app.include_router(seed.router, prefix="/api/v1")
app.include_router(agencies.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")
app.include_router(connection_logs.router, prefix="/api/v1")
app.include_router(api_key.router, prefix="/api/v1")
app.include_router(executive_summary.router, prefix="/api/v1")
app.include_router(insight.router, prefix="/api/v1")

# ---------------------------------------------------------------------------
# MCP server — streamable-HTTP sub-app (backward compat)
# ---------------------------------------------------------------------------

app.mount("/mcp", mcp_app)

# ---------------------------------------------------------------------------
# MCP SSE transport — root-level routes (OneChat spec)
# GET  /sse           → open SSE stream; server emits endpoint URL with session_id
# POST /messages/     → send MCP JSON-RPC message, ?session_id=<id> required
# ---------------------------------------------------------------------------

app.add_route("/sse", _sse_handler, methods=["GET"])
app.mount("/messages", _sse_transport.handle_post_message)

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return "ok\n"

# ---------------------------------------------------------------------------
# Opentelemetry auto-instrumentation
# ---------------------------------------------------------------------------
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

resource = Resource.create(attributes={
    SERVICE_NAME: "backend"
})

tracerProvider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="otel-collector:4317", insecure=True))
tracerProvider.add_span_processor(processor)
trace.set_tracer_provider(tracerProvider)

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
FastAPIInstrumentor.instrument_app(app, excluded_urls="^/health$")

# ---------------------------------------------------------------------------
# Background scheduler
# ---------------------------------------------------------------------------

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
scheduler = AsyncIOScheduler()
sem = asyncio.Semaphore(5)

async def agency_chat_item(agency: Agency):
    async with sem:
        if agency.connection_type == "API":
            scope = agency.data_scope or ["ทั่วไป"]
            scope = scope[random.randint(0, len(scope)-1)] if len(scope) > 0 else "ทั่วไป"

            async with httpx.AsyncClient(timeout=180) as client:
                headers = {"content-type": "application/json"}
                for v in (agency.api_headers or []):
                    headers[v["name"].lower()] = v["value"]
                payload = {}
                for k, v in agency.expected_payload.items():
                    payload[k] = v
                    if v == "__query__": payload[k] = "ปรึกษากฎหมาย" + scope
                    if v == "__user_id__": payload[k] = str(generate_uuid())
                    if v == "__session_id__": payload[k] = str(generate_uuid())
                    if v == "__conversation_id__": payload[k] = str(generate_uuid())
                start_ns = time.perf_counter_ns()
                resp = await client.post(agency.endpoint_url, headers=headers, json=payload)
                end_ns = time.perf_counter_ns()
                latency = int((end_ns - start_ns) // 1_000_000)  # ms
                print(f"Sent test message to agency {agency.name} with latency {latency} ms")
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

async def agency_chat_test():
    agencies = await Agency.all()
    await asyncio.gather(*[agency_chat_item(ag) for ag in agencies])

async def start_scheduler():
    asyncio.create_task(agency_chat_test())
    scheduler.add_job(agency_chat_test, IntervalTrigger(minutes=15))
    scheduler.start()

async def stop_scheduler():
    scheduler.shutdown()