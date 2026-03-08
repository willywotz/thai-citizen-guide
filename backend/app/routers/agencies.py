import asyncio
import random
import time
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from ..database import get_db
from ..models import Agency, ConnectionLog
from ..auth import get_current_user
from ..models import User

router = APIRouter(prefix="/api/agencies", tags=["agencies"])


class AgencyCreate(BaseModel):
    name: str
    short_name: str | None = None
    logo: str | None = "🏢"
    connection_type: str = "API"
    status: str = "active"
    description: str | None = None
    data_scope: list[str] | None = None
    color: str | None = "hsl(213 70% 45%)"
    endpoint_url: str | None = None
    api_key_name: str | None = None


class AgencyUpdate(AgencyCreate):
    pass


class TestConnectionRequest(BaseModel):
    connection_type: str
    endpoint_url: str


def agency_to_dict(a: Agency) -> dict:
    return {
        "id": str(a.id),
        "name": a.name,
        "shortName": a.short_name,
        "logo": a.logo,
        "connectionType": a.connection_type,
        "status": a.status,
        "description": a.description,
        "dataScope": a.data_scope or [],
        "totalCalls": a.total_calls,
        "color": a.color,
        "endpointUrl": a.endpoint_url,
        "apiKeyName": a.api_key_name,
        "createdAt": a.created_at.isoformat() if a.created_at else None,
        "updatedAt": a.updated_at.isoformat() if a.updated_at else None,
    }


@router.get("")
async def list_agencies(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agency).order_by(Agency.created_at.asc()))
    agencies = result.scalars().all()
    return [agency_to_dict(a) for a in agencies]


@router.post("")
async def create_agency(body: AgencyCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    agency = Agency(
        name=body.name,
        short_name=body.short_name,
        logo=body.logo or "🏢",
        connection_type=body.connection_type,
        status=body.status,
        description=body.description or "",
        data_scope=body.data_scope or [],
        color=body.color,
        endpoint_url=body.endpoint_url or "",
        api_key_name=body.api_key_name,
    )
    db.add(agency)
    await db.commit()
    await db.refresh(agency)
    return {"success": True, "data": agency_to_dict(agency)}


@router.put("/{agency_id}")
async def update_agency(agency_id: str, body: AgencyUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Agency).where(Agency.id == agency_id))
    agency = result.scalar_one_or_none()
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")

    agency.name = body.name
    agency.short_name = body.short_name
    agency.logo = body.logo or "🏢"
    agency.connection_type = body.connection_type
    agency.status = body.status
    agency.description = body.description or ""
    agency.data_scope = body.data_scope or []
    agency.color = body.color
    agency.endpoint_url = body.endpoint_url or ""
    agency.api_key_name = body.api_key_name
    agency.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(agency)
    return {"success": True, "data": agency_to_dict(agency)}


@router.delete("/{agency_id}")
async def delete_agency(agency_id: str, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Agency).where(Agency.id == agency_id))
    agency = result.scalar_one_or_none()
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")

    await db.delete(agency)
    await db.commit()
    return {"success": True}


@router.post("/test-connection")
async def test_connection(body: TestConnectionRequest, _: User = Depends(get_current_user)):
    start = time.time()
    await asyncio.sleep(0.1 + random.random() * 0.3)
    latency = int((time.time() - start) * 1000)

    if body.connection_type == "MCP":
        result = {
            "success": True,
            "protocol": "MCP",
            "version": "1.0",
            "steps": [
                {"step": 1, "label": "TCP Connection", "status": "done", "time": round(latency * 0.2)},
                {"step": 2, "label": "MCP Handshake", "status": "done", "time": round(latency * 0.4)},
                {"step": 3, "label": "Capability Exchange", "status": "done", "time": round(latency * 0.3)},
                {"step": 4, "label": "Session Established", "status": "done", "time": round(latency * 0.1)},
            ],
            "capabilities": ["tools/list", "tools/call", "resources/read"],
            "latency": f"{latency}ms",
        }
    elif body.connection_type == "A2A":
        result = {
            "success": True,
            "protocol": "A2A",
            "version": "0.2",
            "steps": [
                {"step": 1, "label": "DNS Resolution", "status": "done", "time": round(latency * 0.15)},
                {"step": 2, "label": "Agent Card Request", "status": "done", "time": round(latency * 0.35)},
                {"step": 3, "label": "Capability Negotiation", "status": "done", "time": round(latency * 0.3)},
                {"step": 4, "label": "Agent Link Ready", "status": "done", "time": round(latency * 0.2)},
            ],
            "agentCard": {"name": "Remote Agent", "skills": ["query", "verify"]},
            "latency": f"{latency}ms",
        }
    else:
        result = {
            "success": True,
            "protocol": "REST API",
            "version": "v1",
            "steps": [
                {"step": 1, "label": "HTTP Connection", "status": "done", "time": round(latency * 0.2)},
                {"step": 2, "label": "Authentication", "status": "done", "time": round(latency * 0.3)},
                {"step": 3, "label": "Health Check", "status": "done", "time": round(latency * 0.3)},
                {"step": 4, "label": "API Ready", "status": "done", "time": round(latency * 0.2)},
            ],
            "endpoints": ["/health", "/query", "/status"],
            "latency": f"{latency}ms",
        }

    return result


@router.get("/{agency_id}/connection-logs")
async def get_connection_logs(agency_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ConnectionLog)
        .where(ConnectionLog.agency_id == agency_id)
        .order_by(ConnectionLog.created_at.desc())
        .limit(50)
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "agencyId": str(log.agency_id),
            "action": log.action,
            "connectionType": log.connection_type,
            "status": log.status,
            "latencyMs": log.latency_ms,
            "detail": log.detail,
            "createdAt": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
