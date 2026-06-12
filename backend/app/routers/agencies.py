"""
REST API routes for agency management.

Endpoints
---------
  GET    /agencies                          List agencies (with optional filters)
  POST   /agencies                          Create a new agency
  POST   /agencies/parse-spec               Parse an OpenAPI spec via LLM
  GET    /agencies/{id}                     Get a single agency
  PUT    /agencies/{id}                     Full replace of an agency
  PATCH  /agencies/{id}                     Partial update of an agency
  DELETE /agencies/{id}                     Delete an agency
  POST   /agencies/{id}/increment-calls     Increment the total_calls counter
  GET    /agencies/{id}/test                Test agency connection
  GET    /agencies/{id}/connection-logs     List connection logs for an agency
"""

import logging
import uuid
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.auth.dependencies import require_admin
from app.models.user import User
from pydantic import BaseModel
from tortoise.exceptions import DoesNotExist

from app.models.agency import Agency
from app.models.connection_log import ConnectionLog
from app.services.agency import parse_spec, test_connection
from app.services.cache_flush import flush_similarity_cache
from app.schemas.agency import (
    AgencyCreate,
    AgencyHealthEmbed,
    AgencyListResponse,
    AgencyResponse,
    AgencyUpdate,
    HealthHistoryBucket,
    HealthHistoryResponse,
    McpDiscoverRequest,
    McpDiscoverResponse,
    McpToolInfo,
    StatusUpdateRequest,
)
from app.services.agency_health import embedded_health, health_history
from app.services.log_sanitize import sanitize_body
from app.services.mcp_discovery import discover_tools
from app.services.agency_lifecycle import is_legal_transition

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agencies", tags=["Agencies"])


async def _with_health(agency: Agency) -> AgencyResponse:
    resp = AgencyResponse.model_validate(agency)
    resp.health = AgencyHealthEmbed(**(await embedded_health(agency.id)))
    return resp


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get("", response_model=AgencyListResponse, summary="List agencies")
async def list_agencies(
    status_filter: Literal["active", "inactive", "draft", "maintenance", "disabled", "all"] = Query(
        "all", alias="status", description="Filter by agency status"
    ),
    connection_type: str | None = Query(None, description="Filter by connection type: MCP, API, A2A"),
    search: str | None = Query(None, description="Search by name or short_name"),
):
    qs = Agency.all()

    if status_filter != "all":
        qs = qs.filter(status=status_filter)

    if connection_type:
        qs = qs.filter(connection_type=connection_type.upper())

    if search:
        qs = qs.filter(name__icontains=search)

    agencies = await qs
    total = await qs.count()

    data = [await _with_health(a) for a in agencies]
    return AgencyListResponse(data=data, total=total)


# ---------------------------------------------------------------------------
# MCP tool discovery
#
# NOTE: must be registered BEFORE any "/{agency_id}" route, otherwise FastAPI
# matches "mcp" as an agency_id UUID path parameter.
# ---------------------------------------------------------------------------

@router.post("/mcp/discover", response_model=McpDiscoverResponse, summary="Discover MCP tools at an endpoint")
async def mcp_discover(body: McpDiscoverRequest, _: User = Depends(require_admin)):
    if not body.endpoint_url.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="endpoint_url is required")
    try:
        tools = await discover_tools(body.endpoint_url)
    except Exception as exc:  # noqa: BLE001 — surface any MCP/connection failure to the client
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"MCP discovery failed: {exc}")
    return McpDiscoverResponse(tools=[McpToolInfo(**t) for t in tools])


# ---------------------------------------------------------------------------
# Get single
# ---------------------------------------------------------------------------

@router.get("/{agency_id}", response_model=AgencyResponse, summary="Get agency by ID")
async def get_agency(agency_id: uuid.UUID):
    try:
        agency = await Agency.get(id=agency_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    return await _with_health(agency)


# ---------------------------------------------------------------------------
# Health history
# ---------------------------------------------------------------------------

@router.get("/{agency_id}/health/history", response_model=HealthHistoryResponse, summary="Agency health history")
async def agency_health_history(agency_id: uuid.UUID, window: str = "24h"):
    try:
        await Agency.get(id=agency_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    buckets = await health_history(agency_id, window)
    return HealthHistoryResponse(data=[HealthHistoryBucket(**b) for b in buckets])


# ---------------------------------------------------------------------------
# Lifecycle status transition
# ---------------------------------------------------------------------------

@router.patch("/{agency_id}/status", response_model=AgencyResponse, summary="Transition agency lifecycle status")
async def update_agency_status(agency_id: uuid.UUID, body: StatusUpdateRequest, _: User = Depends(require_admin)):
    try:
        agency = await Agency.get(id=agency_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    if not is_legal_transition(agency.status.value, body.status):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Illegal status transition: {agency.status.value} → {body.status}",
        )
    agency.status = body.status
    agency.auto_maintenance = False
    await agency.save(update_fields=["status", "auto_maintenance", "updated_at"])
    return await _with_health(agency)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@router.post("", response_model=AgencyResponse, status_code=status.HTTP_201_CREATED, summary="Create agency")
async def create_agency(body: AgencyCreate, _: User = Depends(require_admin)):
    data = body.model_dump()

    # Serialise nested Pydantic objects to plain dicts for JSON fields
    data["api_endpoints"] = [e.model_dump() for e in body.api_endpoints]
    data["response_schema"] = [f.model_dump() for f in body.response_schema]
    data["api_headers"] = [h.model_dump() for h in body.api_headers] if body.api_headers else []

    agency = await Agency.create(**data)
    return await _with_health(agency)


# ---------------------------------------------------------------------------
# Full update (PUT)
# ---------------------------------------------------------------------------

@router.put("/{agency_id}", response_model=AgencyResponse, summary="Replace agency")
async def replace_agency(agency_id: uuid.UUID, body: AgencyCreate, _: User = Depends(require_admin)):
    try:
        agency = await Agency.get(id=agency_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")

    data = body.model_dump()
    data["api_endpoints"] = [e.model_dump() for e in body.api_endpoints]
    data["response_schema"] = [f.model_dump() for f in body.response_schema]
    data["api_headers"] = [h.model_dump() for h in body.api_headers] if body.api_headers else []
    await agency.update_from_dict(data).save()
    try:
        await flush_similarity_cache()
    except Exception:
        logger.exception("failed to flush similarity cache after agency update")
    return await _with_health(agency)


# ---------------------------------------------------------------------------
# Partial update (PATCH)
# ---------------------------------------------------------------------------

@router.patch("/{agency_id}", response_model=AgencyResponse, summary="Partial update agency")
async def update_agency(agency_id: uuid.UUID, body: AgencyUpdate, _: User = Depends(require_admin)):
    try:
        agency = await Agency.get(id=agency_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")

    update_data = body.model_dump(exclude_unset=True)

    # Serialise nested objects if present
    if "api_endpoints" in update_data and update_data["api_endpoints"] is not None:
        update_data["api_endpoints"] = [
            e.model_dump() if hasattr(e, "model_dump") else e
            for e in update_data["api_endpoints"]
        ]
    if "response_schema" in update_data and update_data["response_schema"] is not None:
        update_data["response_schema"] = [
            f.model_dump() if hasattr(f, "model_dump") else f
            for f in update_data["response_schema"]
        ]
    if "api_headers" in update_data and update_data["api_headers"] is not None:
        update_data["api_headers"] = [
            h.model_dump() if hasattr(h, "model_dump") else h
            for h in update_data["api_headers"]
        ]

    await agency.update_from_dict(update_data).save()
    try:
        await flush_similarity_cache()
    except Exception:
        logger.exception("failed to flush similarity cache after agency update")
    return await _with_health(agency)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.delete("/{agency_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete agency")
async def delete_agency(agency_id: uuid.UUID, _: User = Depends(require_admin)):
    try:
        agency = await Agency.get(id=agency_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    await agency.delete()


# ---------------------------------------------------------------------------
# Increment total_calls
# ---------------------------------------------------------------------------

@router.post(
    "/{agency_id}/increment-calls",
    response_model=AgencyResponse,
    summary="Increment agency call counter",
)
async def increment_calls(agency_id: uuid.UUID, _: User = Depends(require_admin)):
    try:
        agency = await Agency.get(id=agency_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")

    agency.total_calls += 1
    await agency.save(update_fields=["total_calls"])
    return AgencyResponse.model_validate(agency)


# ---------------------------------------------------------------------------
# Test connection — response model
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Parse API spec (LLM-assisted)
# ---------------------------------------------------------------------------

class ParseSpecRequest(BaseModel):
    spec_text: str


@router.post("/parse-spec", summary="Parse an OpenAPI spec via LLM and extract structured metadata")
async def parse_api_spec(body: ParseSpecRequest):
    if not body.spec_text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="spec_text is required")

    try:
        parsed = await parse_spec(body.spec_text)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"gateway error: {exc}")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text[:500])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return {"success": True, "data": parsed}
