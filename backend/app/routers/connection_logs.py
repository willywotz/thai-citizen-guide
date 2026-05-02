import uuid
import time
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from tortoise.functions import Avg
from tortoise.exceptions import DoesNotExist
from app.models import Agency, ConnectionLog, User
from app.auth.dependencies import require_admin
from datetime import datetime, timedelta
from app.utils import now

router = APIRouter(prefix="/connection-logs", tags=["Connection Logs"])

# ---------------------------------------------------------------------------
# Connection logs
# ---------------------------------------------------------------------------

class ConnectionLogItem(BaseModel):
    id: str
    agency_id: str
    action: str
    connection_type: str
    status: str
    latency_ms: int
    detail: str
    created_at: str

class ListConnectionLogResponse(BaseModel):
    search: str | None = None
    page: int
    page_size: int

    items: list[ConnectionLogItem]
    total_items: int

    total_connections: int
    successful_connections: int
    failed_connections: int
    average_latency_ms: int

@router.get(
    "",
    
    response_model=ListConnectionLogResponse,
    summary="List connection logs",
)
async def list_connection_logs(
    search: str | None = Query(None, description="Search in detail"),
    agency_id: str | None = Query(None, description="Filter by agency ID"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(require_admin),
)-> ListConnectionLogResponse:
    
    start = time.time()

    qs = ConnectionLog.all()

    if search:
        qs = qs.filter(detail__icontains=search)
    
    if agency_id:
        try:
            agency_uuid = uuid.UUID(agency_id)
            await Agency.get(id=agency_uuid)  # Check if agency exists
            qs = qs.filter(agency_id=agency_uuid)
        except (ValueError, DoesNotExist):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agency ID")

    qs_pagination = qs

    if page and limit:
        offset = (page - 1) * limit
        qs_pagination = qs.offset(offset).limit(limit)

    logs = await qs_pagination.order_by("-created_at")

    total_connections = await qs.count()
    successful_connections = await qs.filter(status="success").count()
    failed_connections = await qs.filter(status="error").count()

    last_day_date = now() - timedelta(days=1)
    average_latency_ms = await qs.filter(created_at__gte=last_day_date).annotate(avg=Avg("latency_ms")).values("avg")
    average_latency_ms = int(average_latency_ms[0]["avg"] or 0) if average_latency_ms else 0

    return ListConnectionLogResponse(
        search=search,
        page=page,
        page_size=limit,
        items=[
            ConnectionLogItem(
                id=str(log.id),
                agency_id=str(log.agency_id) if log.agency_id else "",
                action=log.action,
                connection_type=log.connection_type,
                status=log.status,
                latency_ms=log.latency_ms,
                detail=log.detail,
                created_at=log.created_at.isoformat(),
            )
            for log in logs
        ],
        total_items=await qs.count(),

        total_connections=total_connections,
        successful_connections=successful_connections,
        failed_connections=failed_connections,
        average_latency_ms=average_latency_ms,
    )

@router.get("/items/{id}", summary="Get connection log detail", response_model=ConnectionLogItem)
async def get_connection_log_detail(id: str, _: User = Depends(require_admin)) -> ConnectionLogItem:
    try:
        log = await ConnectionLog.get(id=id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection log not found")

    return ConnectionLogItem(
        id=str(log.id),
        agency_id=str(log.agency_id) if log.agency_id else "",
        action=log.action,
        connection_type=log.connection_type,
        status=log.status,
        latency_ms=log.latency_ms,
        detail=log.detail,
        created_at=log.created_at.isoformat(),
    )

class ConnectionLogInfoResponse(BaseModel):
    total_connections: int
    successful_connections: int
    failed_connections: int
    average_latency_ms: int

@router.get("/info", summary="Get connection log info", response_model=ConnectionLogInfoResponse)
async def get_connection_log_info(_: User = Depends(require_admin)) -> ConnectionLogInfoResponse:
    total_connections = await ConnectionLog.all().count()
    successful_connections = await ConnectionLog.filter(status="success").count()
    failed_connections = await ConnectionLog.filter(status="error").count()
    
    last_day_date = now() - timedelta(days=1)
    average_latency_ms = await ConnectionLog.filter(created_at__gte=last_day_date).annotate(avg=Avg("latency_ms")).values("avg")
    average_latency_ms = int(average_latency_ms[0]["avg"] or 0) if average_latency_ms else 0

    return ConnectionLogInfoResponse(
        total_connections=total_connections,
        successful_connections=successful_connections,
        failed_connections=failed_connections,
        average_latency_ms=average_latency_ms,
    )