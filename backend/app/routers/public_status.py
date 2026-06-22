"""Public, unauthenticated agency status — name, status, 24h uptime. No internals."""
from datetime import timedelta

from fastapi import APIRouter
from tortoise import Tortoise

from app.models import Agency
from app.utils import now

router = APIRouter(prefix="/public", tags=["Public"])


async def public_status() -> list[dict]:
    cutoff = now() - timedelta(hours=24)
    conn = Tortoise.get_connection("default")
    rows = await conn.execute_query_dict(
        """
        SELECT agency_id,
               COUNT(*) AS total,
               SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS ok
        FROM connection_logs
        WHERE created_at >= $1
        GROUP BY agency_id
        """,
        [cutoff],
    )
    counts = {str(r["agency_id"]): (r["total"], r["ok"]) for r in rows}
    out: list[dict] = []
    for ag in await Agency.exclude(status="draft").order_by("name"):
        total, ok = counts.get(str(ag.id), (0, 0))
        uptime = round(ok / total * 100, 1) if total else None
        out.append({"name": ag.name, "status": ag.status.value, "uptime_24h_pct": uptime})
    return out


@router.get("/status", summary="Public agency status")
async def get_public_status() -> list[dict]:
    return await public_status()
