"""Public, unauthenticated agency status — name, status, 24h uptime. No internals."""
from datetime import timedelta

from fastapi import APIRouter

from app.models import Agency, ConnectionLog
from app.utils import now

router = APIRouter(prefix="/public", tags=["Public"])


async def public_status() -> list[dict]:
    cutoff = now() - timedelta(hours=24)
    out: list[dict] = []
    for ag in await Agency.exclude(status="draft").order_by("name"):
        total = await ConnectionLog.filter(agency_id=ag.id, created_at__gte=cutoff).count()
        ok = await ConnectionLog.filter(agency_id=ag.id, created_at__gte=cutoff, status="success").count()
        uptime = round(ok / total * 100, 1) if total else None
        out.append({"name": ag.name, "status": ag.status.value, "uptime_24h_pct": uptime})
    return out


@router.get("/status", summary="Public agency status")
async def get_public_status() -> list[dict]:
    return await public_status()
