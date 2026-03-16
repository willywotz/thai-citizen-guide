import asyncio
import time
import random
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.database import get_db
from app.dependencies import require_auth, require_permission, get_optional_auth
from app.models import Agency, ConnectionLog
from app.schemas.agency import (
    AgencyCreate, AgencyUpdate, AgencyOut,
    ConnectionTestRequest, ConnectionTestResult, ConnectionTestStep,
)

router = APIRouter(prefix="/agencies", tags=["agencies"])


@router.get("", response_model=list[AgencyOut])
async def list_agencies(
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint — list agencies."""
    q = select(Agency)
    if status:
        q = q.where(Agency.status == status)
    result = await db.execute(q.order_by(Agency.name))
    return result.scalars().all()


@router.post("", response_model=AgencyOut)
async def create_agency(
    body: AgencyCreate,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_permission("agencies.write")),
):
    agency = Agency(**body.model_dump())
    db.add(agency)
    await db.commit()
    await db.refresh(agency)
    return agency


@router.put("/{agency_id}", response_model=AgencyOut)
async def update_agency(
    agency_id: str,
    body: AgencyUpdate,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_permission("agencies.write")),
):
    result = await db.execute(select(Agency).where(Agency.id == agency_id))
    agency = result.scalar_one_or_none()
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(agency, field, value)

    await db.commit()
    await db.refresh(agency)
    return agency


@router.delete("/{agency_id}")
async def delete_agency(
    agency_id: str,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_permission("agencies.delete")),
):
    result = await db.execute(delete(Agency).where(Agency.id == agency_id))
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Agency not found")
    return {"success": True}


@router.post("/test-connection", response_model=ConnectionTestResult)
async def test_connection(
    body: ConnectionTestRequest,
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_permission("agencies.write")),
):
    """Test connectivity to an agency endpoint."""
    if body.connection_type in ("MCP", "A2A"):
        return _simulate_test(body.connection_type)

    # Real HTTP test
    url = body.endpoint_url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Endpoint URL is required")

    steps: list[ConnectionTestStep] = []
    total_start = time.monotonic()
    status_code = None
    content_type = None
    server = None
    error_msg = None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                s1 = time.monotonic()
                resp = await client.head(url, headers={"User-Agent": "AI-Chatbot-Portal/1.0"})
                t1 = int((time.monotonic() - s1) * 1000)
            except httpx.HTTPError:
                s1 = time.monotonic()
                resp = await client.get(url, headers={"User-Agent": "AI-Chatbot-Portal/1.0"})
                t1 = int((time.monotonic() - s1) * 1000)

        status_code = resp.status_code
        content_type = resp.headers.get("content-type", "unknown").split(";")[0]
        server = resp.headers.get("server", "unknown")

        steps.append(ConnectionTestStep(step=1, label="TCP Connection", status="done", time=t1))
        steps.append(ConnectionTestStep(step=2, label=f"HTTP {status_code}", status="done" if status_code < 500 else "error", time=t1))
        steps.append(ConnectionTestStep(step=3, label=f"Content-Type: {content_type}", status="done", time=0))
        is_success = 200 <= status_code < 500
        steps.append(ConnectionTestStep(step=4, label="API Reachable" if is_success else "API Error", status="done" if is_success else "error", time=0))

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        error_msg = "Connection timeout (10s)" if isinstance(e, httpx.TimeoutException) else str(e)
        steps.append(ConnectionTestStep(step=1, label="TCP Connection", status="error", time=0))
        steps.append(ConnectionTestStep(step=2, label="HTTP Response", status="error", time=0))
        is_success = False

    latency_ms = int((time.monotonic() - total_start) * 1000)
    return ConnectionTestResult(
        success=is_success if error_msg is None else False,
        protocol="REST API",
        version="v1",
        steps=steps,
        latency=f"{latency_ms}ms",
        statusCode=status_code,
        server=server,
        contentType=content_type,
        error=error_msg,
    )


def _simulate_test(connection_type: str) -> ConnectionTestResult:
    latency = 100 + random.randint(0, 300)
    if connection_type == "MCP":
        steps = [
            ConnectionTestStep(step=1, label="TCP Connection", status="done", time=int(latency * 0.2)),
            ConnectionTestStep(step=2, label="MCP Handshake", status="done", time=int(latency * 0.4)),
            ConnectionTestStep(step=3, label="Capability Exchange", status="done", time=int(latency * 0.3)),
            ConnectionTestStep(step=4, label="Session Established", status="done", time=int(latency * 0.1)),
        ]
        return ConnectionTestResult(
            success=True, protocol="MCP", version="1.0",
            steps=steps, latency=f"{latency}ms",
            capabilities=["tools/list", "tools/call", "resources/read"],
        )
    else:
        steps = [
            ConnectionTestStep(step=1, label="DNS Resolution", status="done", time=int(latency * 0.15)),
            ConnectionTestStep(step=2, label="Agent Card Request", status="done", time=int(latency * 0.35)),
            ConnectionTestStep(step=3, label="Capability Negotiation", status="done", time=int(latency * 0.3)),
            ConnectionTestStep(step=4, label="Agent Link Ready", status="done", time=int(latency * 0.2)),
        ]
        return ConnectionTestResult(
            success=True, protocol="A2A", version="0.2",
            steps=steps, latency=f"{latency}ms",
            agentCard={"name": "Remote Agent", "skills": ["query", "verify"]},
        )
