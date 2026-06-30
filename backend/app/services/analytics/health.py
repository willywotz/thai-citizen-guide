import logging
from datetime import timedelta

from tortoise.expressions import RawSQL
from tortoise.transactions import in_transaction

from app.config import settings
from app.models import Agency, ConnectionLog
from app.schemas.insight import AgencyHealthData, Agency as AgencyHealth
from app.services.agency_health import error_window
from app.utils import now

logger = logging.getLogger(__name__)


async def get_agency_health() -> AgencyHealthData:
    async with in_transaction() as conn:
        await conn.execute_query(f"SET TIME ZONE '{settings.TIMEZONE}';")

        agencies = await Agency.all().values("id", "name", "short_name", "status", "stats_reset_at")

        if not agencies:
            return AgencyHealthData(
                agencies=[],
                historical=[],
                incidents=[],
                slaCompliance=[],
                generatedAt=now(),
            )

        current_cutoff = now() - timedelta(minutes=settings.HEALTH_CHECK_INTERVAL_MINUTES)
        week_cutoff = now() - timedelta(days=7)
        day_cutoff = now() - timedelta(days=settings.AVG_LATENCY_WINDOW_DAYS)

        placeholder = "$1" if conn.capabilities.dialect == "postgres" else "?"

        current_latency_rows = await conn.execute_query_dict(
            f"""
            SELECT agency_id, AVG(latency_ms) AS avg_latency
            FROM connection_logs
            WHERE created_at >= {placeholder}
            GROUP BY agency_id
            """,
            [current_cutoff],
        )
        current_latency = {str(r["agency_id"]): r["avg_latency"] for r in current_latency_rows}

        avg_latency_rows = await conn.execute_query_dict(
            f"""
            SELECT agency_id, AVG(latency_ms) AS avg_latency
            FROM connection_logs
            WHERE created_at >= {placeholder}
            GROUP BY agency_id
            """,
            [week_cutoff],
        )
        avg_latency = {str(r["agency_id"]): r["avg_latency"] for r in avg_latency_rows}

        day_count_rows = await conn.execute_query_dict(
            f"""
            SELECT agency_id, COUNT(*) AS total
            FROM connection_logs
            WHERE created_at >= {placeholder}
            GROUP BY agency_id
            """,
            [day_cutoff],
        )
        day_counts = {str(r["agency_id"]): r["total"] for r in day_count_rows}

        agencies_health = []
        for ag in agencies:
            ag_id = str(ag["id"])
            status = {"active": "healthy"}.get(ag["status"], "down")

            cur_lat = current_latency.get(ag_id) or 0
            avg_lat = avg_latency.get(ag_id) or 0
            # Uptime/error rate over the trailing 24h, honoring per-agency
            # stats_reset_at — identical window to the /agencies embed.
            checks, failures = await error_window(ag["id"], ag["stats_reset_at"])
            error_rate = (failures / checks * 100) if checks else 0
            total_day = day_counts.get(ag_id, 0)

            agencies_health.append(AgencyHealth(
                id=ag_id,
                name=ag["name"],
                shortName=ag["short_name"],
                status=status,
                uptime=round(100.0 - error_rate, 2),
                currentLatency=cur_lat // 1,
                avgLatency=avg_lat // 1,
                errorRate=round(error_rate, 2),
                requestsPerMin=round(total_day / (settings.AVG_LATENCY_WINDOW_DAYS * 1440), 2),
                lastCheckedAt=now(),
            ))

        rawHistorical = await ConnectionLog \
            .annotate(
                date=RawSQL("TO_CHAR(created_at, 'MM-DD HH24:00')"),
                latency=RawSQL("AVG(latency_ms)"),
                uptime=RawSQL("AVG(CASE WHEN status >= 'success' THEN 1 ELSE 0 END) * 100")
            ) \
            .filter(created_at__gte=now() - timedelta(days=settings.AVG_LATENCY_WINDOW_DAYS)) \
            .group_by("date", "agency_id") \
            .values("date", "agency_id", "latency", "uptime")

        historical = {}
        for entry in rawHistorical:
            date = entry["date"]
            agency_id = str(entry["agency_id"])
            if date not in historical:
                historical[date] = {"time": date}
            historical[date][f"{agency_id}_latency"] = entry["latency"] // 1
            historical[date][f"{agency_id}_uptime"] = round(entry["uptime"], 2)

        historical = sorted(historical.values(), key=lambda x: x["time"])

    return AgencyHealthData(
        agencies=agencies_health,
        historical=historical,
        incidents=[],
        slaCompliance=[],
        generatedAt=now(),
    )
