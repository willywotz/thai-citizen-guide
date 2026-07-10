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
    placeholder = "$1" if conn.capabilities.dialect == "postgres" else "?"
    rows = await conn.execute_query_dict(
        f"""
        SELECT agency_id,
               COUNT(*) AS total,
               SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS ok
        FROM connection_logs
        WHERE created_at >= {placeholder}
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


async def public_agencies() -> list[dict]:
    """Display-safe agency list for the public portal — no internals."""
    return [
        {
            "id": str(ag.id),
            "name": ag.name,
            "short_name": ag.short_name,
            "logo": ag.logo,
            "description": ag.description,
            "connection_type": ag.connection_type.value,
            "status": ag.status.value,
        }
        for ag in await Agency.exclude(status="draft").order_by("name")
    ]


@router.get("/agencies", summary="Public agency directory")
async def get_public_agencies() -> list[dict]:
    return await public_agencies()
