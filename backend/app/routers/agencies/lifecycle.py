"""Lifecycle endpoints: status transitions, conformance, test connection, health history."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from tortoise.exceptions import DoesNotExist

from app.auth.authz import authorize_or_403
from app.auth.dependencies import get_current_user, require_admin
from app.errors import ApiError
from app.models.agency import Agency
from app.models.connection_log import ConnectionLog
from app.models.user import User
from app.routers.agencies._utils import _with_health
from app.schemas.agency import (
    AgencyResponse,
    HealthHistoryBucket,
    HealthHistoryResponse,
    StatusUpdateRequest,
)
from app.services.agency import test_connection
from app.services.agency_health import health_history
from app.services.agency_lifecycle import is_legal_transition
from app.services.audit import record_audit
from app.services.log_sanitize import sanitize_body

router = APIRouter()


class TestStep(BaseModel):
    step: int
    label: str
    status: str   # "done" | "error"
    time: int     # milliseconds


class AgentCardInfo(BaseModel):
    name: str
    skills: list[str] = []
    capabilities: dict[str, Any] = {}


class TestConnectionResponse(BaseModel):
    success: bool
    protocol: str          # "REST API" | "MCP" | "A2A" | "UNKNOWN"
    version: str
    steps: list[TestStep]
    latency: str           # e.g. "142ms"

    # REST-only
    status_code: int | None = None
    status_text: str | None = None
    server: str | None = None
    content_type: str | None = None

    # MCP-only
    capabilities: list[str] | None = None
    server_info: dict[str, Any] | None = None

    # A2A-only
    agent_card: AgentCardInfo | None = None

    # Error (any protocol)
    error: str | None = None

    model_config = {"populate_by_name": True}


@router.patch("/{agency_id}/status", response_model=AgencyResponse, summary="Transition agency lifecycle status")
async def update_agency_status(agency_id: uuid.UUID, body: StatusUpdateRequest, user: User = Depends(get_current_user)):
    try:
        agency = await Agency.get(id=agency_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    await authorize_or_403(user, "agency:change_status", agency)
    if not is_legal_transition(agency.status.value, body.status):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Illegal status transition: {agency.status.value} → {body.status}",
        )
    if agency.status.value == "draft" and body.status == "active":
        report = agency.conformance_report or {}
        if not report.get("passed"):
            raise ApiError("invalid_request", "conformance test must pass before activation", status=400)
    old_status = agency.status.value
    agency.status = body.status
    agency.auto_maintenance = False
    await agency.save(update_fields=["status", "auto_maintenance", "updated_at"])
    await record_audit(user, "agency.status_change", object_type="agency", object_id=agency.id, detail={"from": old_status, "to": body.status})
    return await _with_health(agency)


@router.post("/{agency_id}/conformance", summary="Run the conformance battery (owner or admin)")
async def run_agency_conformance(agency_id: str, user: User = Depends(get_current_user)):
    agency = await Agency.get_or_none(id=agency_id)
    if agency is None:
        raise HTTPException(status_code=404, detail="Agency not found")
    await authorize_or_403(user, "agency:edit", agency)
    from app.services.conformance import run_conformance
    return await run_conformance(agency)


@router.get("/{agency_id}/health/history", response_model=HealthHistoryResponse, summary="Agency health history")
async def agency_health_history(agency_id: uuid.UUID, window: str = "24h"):
    try:
        await Agency.get(id=agency_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    buckets = await health_history(agency_id, window)
    return HealthHistoryResponse(data=[HealthHistoryBucket(**b) for b in buckets])


@router.get(
    "/{agency_id}/test",
    response_model=TestConnectionResponse,
    summary="Test agency connection and record a connection log",
)
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
        detail=sanitize_body(response.error or (f"HTTP {response.status_code}" if response.status_code else response.protocol)),
    )

    return response
