"""
Thai Citizen Guide — MCP Server

Exposes government agency information and query capabilities to any
MCP-compatible LLM client (Claude Desktop, Continue, Cursor, etc.).

Features
--------
* get_agencies / get_agency / ask_agency tools
* tcg://agencies/live  — always-fresh agency list resource
* tcg://agencies/changes — rolling log of recent DB changes
* Real-time push: PostgreSQL LISTEN/NOTIFY → MCP notifications/resources/updated
  Clients that subscribe to either resource URI are notified automatically when
  any agency row is inserted, updated, or deleted.

Transport (MCP_TRANSPORT env var):
  stdio  — default, local tool use (Claude Desktop)
  sse    — HTTP SSE, suitable for Docker / remote

Run locally:
  cd backend && python mcp_server.py

Run in Docker (see docker-compose.yaml, service: mcp):
  MCP_TRANSPORT=sse MCP_PORT=8090 python mcp_server.py

Claude Desktop config  (~/.claude/claude_desktop_config.json):
  {
    "mcpServers": {
      "thai-citizen-guide": {
        "command": "python",
        "args": ["/path/to/backend/mcp_server.py"],
        "env": { "DATABASE_URL": "postgresql+asyncpg://user:pass@host:5432/db" }
      }
    }
  }

Docker SSE config:
  { "mcpServers": { "thai-citizen-guide": { "url": "http://localhost:8090/sse" } } }
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import weakref
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
from mcp.server.fastmcp import Context, FastMCP
from pydantic import AnyUrl
from sqlalchemy import func, or_, select

from app.config import settings
from app.database import AsyncSessionLocal
from app.graph.graph import run_chat_pipeline
from app.models import Agency

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [MCP] %(levelname)s %(message)s")

NOTIFY_CHANNEL = "agency_changes"
POLL_INTERVAL = int(os.getenv("MCP_POLL_INTERVAL", "30"))   # seconds between DB polls (fallback)
CHANGE_LOG_SIZE = 100                                        # max events kept in memory


# ---------------------------------------------------------------------------
# Shared state (module-level so the lifespan task and handlers share it)
# ---------------------------------------------------------------------------

# Rolling log of agency change events, newest first
_change_log: deque[dict] = deque(maxlen=CHANGE_LOG_SIZE)

# Weak references to MCP ServerSession objects that have interacted with this
# server — used to push notifications/resources/updated when data changes.
# WeakSet means we never keep a session alive longer than the transport does.
_tracked_sessions: weakref.WeakSet = weakref.WeakSet()

# URIs that should be pushed on next change event
_MONITORED_URIS = ("tcg://agencies/live", "tcg://agencies/changes")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw_dsn() -> str:
    """Strip the SQLAlchemy dialect prefix so asyncpg can use the DSN directly."""
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


def _agency_to_dict(agency: Agency) -> dict:
    return {
        "id": str(agency.id),
        "name": agency.name,
        "short_name": agency.short_name,
        "description": agency.description,
        "status": agency.status,
        "connection_type": agency.connection_type,
        "data_scope": agency.data_scope or [],
        "endpoint_url": agency.endpoint_url,
        "auth_method": agency.auth_method,
        "rate_limit_rpm": agency.rate_limit_rpm,
        "total_calls": agency.total_calls,
        "api_endpoints": [
            {
                "method": ep.get("method"),
                "path": ep.get("path"),
                "description": ep.get("description"),
            }
            for ep in (agency.api_endpoints or [])
        ],
        "response_schema": [
            {
                "field": f.get("field"),
                "type": f.get("type"),
                "description": f.get("description"),
            }
            for f in (agency.response_schema or [])
        ],
    }


async def _push_resource_updated(uri: str) -> None:
    """Send notifications/resources/updated to all tracked sessions."""
    dead = []
    for session in list(_tracked_sessions):
        try:
            await session.send_resource_updated(AnyUrl(uri))
        except Exception as exc:
            logger.debug("Session notification failed (%s), dropping.", exc)
            dead.append(session)
    for s in dead:
        _tracked_sessions.discard(s)


async def _on_db_notify(
    _conn: asyncpg.Connection,
    _pid: int,
    _channel: str,
    payload: str,
) -> None:
    """asyncpg NOTIFY callback — runs on the event loop thread."""
    try:
        data: dict = json.loads(payload) if payload else {}
    except json.JSONDecodeError:
        data = {"raw": payload}

    event = {
        "event": data.get("event", "CHANGED"),
        "agency_id": str(data.get("id", "")),
        "name": data.get("name", "unknown"),
        "short_name": data.get("short_name", ""),
        "status": data.get("status", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _change_log.appendleft(event)
    logger.info(
        "Agency change: %s %s (%s)",
        event["event"],
        event["name"],
        event["agency_id"],
    )

    # Push to all subscribed MCP clients
    for uri in _MONITORED_URIS:
        await _push_resource_updated(uri)


# ---------------------------------------------------------------------------
# Background monitor task
# ---------------------------------------------------------------------------

async def _db_monitor() -> None:
    """
    Connects to PostgreSQL via asyncpg (separate from SQLAlchemy pool) and
    listens on the 'agency_changes' NOTIFY channel.

    If the connection drops it reconnects automatically.
    Falls back to a lightweight poll-based check (max(updated_at)) as a
    secondary safety net so no change is ever silently missed.
    """
    dsn = _raw_dsn()
    last_updated_at: Optional[datetime] = None

    while True:
        conn: Optional[asyncpg.Connection] = None
        try:
            conn = await asyncpg.connect(dsn)
            logger.info("DB monitor listening on channel '%s'", NOTIFY_CHANNEL)
            await conn.add_listener(NOTIFY_CHANNEL, _on_db_notify)

            # Also run a periodic poll as belt-and-braces fallback
            while not conn.is_closed():
                await asyncio.sleep(POLL_INTERVAL)

                # Poll max(updated_at) to catch any missed events
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(func.max(Agency.updated_at))
                    )
                    latest: Optional[datetime] = result.scalar_one_or_none()

                if latest and latest != last_updated_at:
                    if last_updated_at is not None:
                        # A change was missed by NOTIFY — synthesise an event
                        missed = {
                            "event": "POLL_DETECTED",
                            "agency_id": "",
                            "name": "(poll fallback)",
                            "short_name": "",
                            "status": "",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        _change_log.appendleft(missed)
                        logger.info("Poll detected agency change not caught by NOTIFY")
                        for uri in _MONITORED_URIS:
                            await _push_resource_updated(uri)
                    last_updated_at = latest

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("DB monitor error (%s), reconnecting in 5s…", exc)
            await asyncio.sleep(5)
        finally:
            if conn and not conn.is_closed():
                try:
                    await conn.remove_listener(NOTIFY_CHANNEL, _on_db_notify)
                    await conn.close()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# FastMCP lifespan — starts / stops the monitor
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(server: FastMCP):
    task = asyncio.create_task(_db_monitor())
    logger.info("Agency change monitor started")
    try:
        yield
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        logger.info("Agency change monitor stopped")


# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Thai Citizen Guide",
    lifespan=_lifespan,
    instructions=(
        "You have access to the Thai Citizen Guide system — a platform connecting "
        "Thai citizens to government agencies (FDA, Revenue Dept, DOPA, Land Dept, etc.). "
        "Use get_agencies to discover agencies and their data scopes. "
        "Use ask_agency to answer citizen questions. "
        "Subscribe to tcg://agencies/live or tcg://agencies/changes to be notified "
        "automatically whenever agency data changes in the database."
    ),
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_agencies(ctx: Context, status: str = "active") -> list[dict]:
    """
    List all government agencies integrated into the Thai Citizen Guide.

    Returns name, description, data topics (data_scope), connection type
    (MCP / API / A2A), status, and available API endpoints with response schema.

    Args:
        status: "active" (default), "inactive", or "all".
    """
    _tracked_sessions.add(ctx.session)
    async with AsyncSessionLocal() as db:
        q = select(Agency)
        if status != "all":
            q = q.where(Agency.status == status)
        result = await db.execute(q.order_by(Agency.name))
        return [_agency_to_dict(a) for a in result.scalars().all()]


@mcp.tool()
async def get_agency(ctx: Context, agency_id: str) -> dict | None:
    """
    Get full details for a single agency by UUID or short name.

    Args:
        agency_id: UUID or short_name, e.g. "fda" or "revenue".

    Returns:
        Agency object with metadata, endpoints, and response schema — or null.
    """
    _tracked_sessions.add(ctx.session)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Agency).where(
                or_(Agency.id == agency_id, Agency.short_name == agency_id)
            )
        )
        agency = result.scalar_one_or_none()
        return _agency_to_dict(agency) if agency else None


@mcp.tool()
async def ask_agency(ctx: Context, query: str, agency_id: Optional[str] = None) -> dict:
    """
    Ask a question through the Thai Citizen Guide AI pipeline.

    The pipeline auto-detects relevant agencies, fetches live data in parallel,
    and synthesises a citizen-friendly answer in Thai or English.

    Args:
        query: e.g. "ยื่นภาษีออนไลน์ได้ที่ไหน?" or "How do I renew my ID card?"
        agency_id: Optional short_name/UUID to restrict to one agency.

    Returns:
        answer, agencies_used, references, confidence, response_time_ms
    """
    _tracked_sessions.add(ctx.session)

    effective_query = query
    if agency_id:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Agency).where(
                    or_(Agency.id == agency_id, Agency.short_name == agency_id)
                )
            )
            agency = result.scalar_one_or_none()
            if agency:
                effective_query = f"[หน่วยงาน: {agency.name}] {query}"

    t0 = time.monotonic()
    async with AsyncSessionLocal() as db:
        state = await run_chat_pipeline(effective_query, db)
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    return {
        "answer": state.get("synthesized_answer", ""),
        "agencies_used": list({r.get("agency") for r in (state.get("references") or [])}),
        "references": state.get("references") or [],
        "confidence": state.get("confidence", 0.0),
        "response_time_ms": elapsed_ms,
    }


@mcp.tool()
async def get_agency_changes(ctx: Context, last_n: int = 20) -> list[dict]:
    """
    Return the most recent agency change events detected by the DB monitor.

    Each event contains: event (INSERT/UPDATE/DELETE/POLL_DETECTED),
    agency_id, name, short_name, status, timestamp (ISO-8601 UTC).

    Args:
        last_n: How many events to return (max 100, default 20).
    """
    _tracked_sessions.add(ctx.session)
    return list(_change_log)[: min(last_n, CHANGE_LOG_SIZE)]


# ---------------------------------------------------------------------------
# Resources (subscribable — push notifications sent on change)
# ---------------------------------------------------------------------------

@mcp.resource("tcg://agencies/live")
async def live_agencies_resource() -> str:
    """
    Live agency directory.

    Subscribe to this URI to receive notifications/resources/updated whenever
    an agency is added, modified, or removed. Re-fetch after each notification
    to get the latest snapshot.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Agency).where(Agency.status == "active").order_by(Agency.name)
        )
        agencies = result.scalars().all()

    lines = [
        "# Thai Citizen Guide — Live Agency Directory",
        f"*Last fetched: {datetime.now(timezone.utc).isoformat()}*",
        f"*Active agencies: {len(agencies)}*",
        "",
    ]
    for a in agencies:
        scope = ", ".join(a.data_scope or [])
        lines += [
            f"## {a.name} ({a.short_name})",
            f"**Type:** {a.connection_type} | **Status:** {a.status}",
            a.description or "",
            f"**Data topics:** {scope}" if scope else "",
            f"**Endpoint:** `{a.endpoint_url}`" if a.endpoint_url else "",
            "",
        ]
    return "\n".join(lines)


@mcp.resource("tcg://agencies/changes")
async def agency_changes_resource() -> str:
    """
    Rolling log of recent agency change events.

    Subscribe to this URI to be notified whenever an agency row changes.
    Re-fetch to get the latest log. Each event shows operation type (INSERT /
    UPDATE / DELETE), agency name/id, and UTC timestamp.
    """
    if not _change_log:
        return "# Agency Change Log\n\n*No changes recorded since server start.*"

    lines = [
        "# Agency Change Log",
        f"*{len(_change_log)} event(s) recorded since server start*",
        "",
        "| Timestamp (UTC) | Event | Agency | ID |",
        "|---|---|---|---|",
    ]
    for ev in _change_log:
        lines.append(
            f"| {ev['timestamp']} | {ev['event']} | {ev['name']} ({ev['short_name']}) | {ev['agency_id']} |"
        )
    return "\n".join(lines)


@mcp.resource("tcg://system/overview")
async def system_overview() -> str:
    """Static overview of the Thai Citizen Guide system for LLM context."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Agency.name, Agency.short_name, Agency.description, Agency.data_scope)
            .where(Agency.status == "active")
            .order_by(Agency.name)
        )
        rows = result.all()

    lines = [
        "# Thai Citizen Guide — System Overview",
        "",
        "Connects Thai citizens to government agencies via MCP, REST API, and A2A protocols.",
        "",
        "## Active Agencies",
        "",
    ]
    for name, short_name, description, data_scope in rows:
        scope = ", ".join(data_scope or [])
        lines += [
            f"### {name} ({short_name})",
            description or "",
            f"**Data topics:** {scope}" if scope else "",
            "",
        ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    port = int(os.getenv("MCP_PORT", "8090"))

    if transport == "sse":
        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")
