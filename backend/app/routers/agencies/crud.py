"""CRUD endpoints: list, get, create, replace, partial-update, delete, increment-calls.

list_agencies and create_agency are exported as bare functions; the package
__init__.py registers them directly on the prefix router to avoid the FastAPI
empty-path constraint with include_router.
"""

import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from tortoise.exceptions import DoesNotExist

from app.auth.authz import authorize_or_403
from app.auth.dependencies import get_current_user, require_admin
from app.models.agency import Agency
from app.models.user import User
from app.routers.agencies._utils import _with_health
from app.routers.agencies.logo import sweep_agency_logo_files
from app.schemas.agency import (
    AgencyCreate,
    AgencyListResponse,
    AgencyResponse,
    AgencyUpdate,
)
from app.services.audit import record_audit
from app.services.cache_flush import flush_similarity_cache

logger = logging.getLogger(__name__)

router = APIRouter()

# Fields that identify *how* an agency is reached. Changing any of these on a
# live agency invalidates its conformance battery, so it must be re-vetted.
_CONNECTION_IDENTITY_FIELDS = frozenset(
    {"connection_type", "endpoint_url", "api_headers", "expected_payload", "mcp_tool_name"}
)


# list_agencies and create_agency are registered by __init__.py directly
# on the /agencies prefix router to avoid FastAPI's empty-path constraint.

async def list_agencies(
    status_filter: Literal["active", "draft", "maintenance", "disabled", "all"] = Query(
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


async def create_agency(body: AgencyCreate, _: User = Depends(require_admin)):
    data = body.model_dump()

    data["api_endpoints"] = [e.model_dump() for e in body.api_endpoints]
    data["response_schema"] = [f.model_dump() for f in body.response_schema]
    data["api_headers"] = [h.model_dump() for h in body.api_headers] if body.api_headers else []

    agency = await Agency.create(**data)
    return await _with_health(agency)


@router.get("/{agency_id}", response_model=AgencyResponse, summary="Get agency by ID")
async def get_agency(agency_id: uuid.UUID):
    try:
        agency = await Agency.get(id=agency_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    return await _with_health(agency)


@router.put("/{agency_id}", response_model=AgencyResponse, summary="Replace agency")
async def replace_agency(agency_id: uuid.UUID, body: AgencyCreate, user: User = Depends(get_current_user)):
    try:
        agency = await Agency.get(id=agency_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    await authorize_or_403(user, "agency:edit", agency)

    data = body.model_dump()
    data["api_endpoints"] = [e.model_dump() for e in body.api_endpoints]
    data["response_schema"] = [f.model_dump() for f in body.response_schema]
    data["api_headers"] = [h.model_dump() for h in body.api_headers] if body.api_headers else []
    await agency.update_from_dict(data).save()
    try:
        await flush_similarity_cache()
    except Exception:
        logger.exception("failed to flush similarity cache after agency update")
    await record_audit(user, "agency.update", object_type="agency", object_id=agency.id)
    return await _with_health(agency)


@router.patch("/{agency_id}", response_model=AgencyResponse, summary="Partial update agency")
async def update_agency(agency_id: uuid.UUID, body: AgencyUpdate, user: User = Depends(get_current_user)):
    try:
        agency = await Agency.get(id=agency_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    await authorize_or_403(user, "agency:edit", agency)

    update_data = body.model_dump(exclude_unset=True)

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

    connection_changed = any(
        field in update_data and update_data[field] != getattr(agency, field)
        for field in _CONNECTION_IDENTITY_FIELDS
    )
    if connection_changed and agency.status in ("active", "maintenance"):
        update_data["status"] = "draft"
        update_data["conformance_report"] = None

    await agency.update_from_dict(update_data).save()
    try:
        await flush_similarity_cache()
    except Exception:
        logger.exception("failed to flush similarity cache after agency update")
    await record_audit(user, "agency.update", object_type="agency", object_id=agency.id)
    return await _with_health(agency)


@router.delete("/{agency_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete agency")
async def delete_agency(agency_id: uuid.UUID, user: User = Depends(get_current_user)):
    try:
        agency = await Agency.get(id=agency_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    await authorize_or_403(user, "agency:delete", agency)
    await agency.delete()
    sweep_agency_logo_files(agency_id)
    await record_audit(user, "agency.delete", object_type="agency", object_id=agency_id)


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
