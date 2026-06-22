import logging
from datetime import timedelta

from tortoise.expressions import RawSQL
from tortoise.transactions import in_transaction

from app.config import settings
from app.models import Agency, ConnectionLog
from app.schemas.insight import AgencyHealthData, Agency as AgencyHealth
from app.utils import now

logger = logging.getLogger(__name__)


async def get_agency_health() -> AgencyHealthData:
    async with in_transaction() as conn:
        await conn.execute_query(f"SET TIME ZONE '{settings.TIMEZONE}';")

        agencies = await Agency.all().values("id", "name", "short_name", "status")

        agencies_health = []

        for ag in agencies:
            status = {"active": "healthy"}.get(ag["status"], "down")

            currentLatency = await ConnectionLog \
                .annotate(avg_latency=RawSQL("AVG(latency_ms)")) \
                .filter(agency_id=ag["id"], created_at__gte=now() - timedelta(minutes=settings.HEALTH_CHECK_INTERVAL_MINUTES)) \
                .group_by("agency_id") \
                .values("avg_latency")
            currentLatency = currentLatency[0]["avg_latency"] if len(currentLatency) > 0 and currentLatency[0]["avg_latency"] is not None else 0

            avgLatency = await ConnectionLog \
                .annotate(avg_latency=RawSQL("AVG(latency_ms)")) \
                .filter(agency_id=ag["id"], created_at__gte=now() - timedelta(days=7)) \
                .group_by("agency_id") \
                .values("avg_latency")
            avgLatency = avgLatency[0]["avg_latency"] if len(avgLatency) > 0 and avgLatency[0]["avg_latency"] is not None else 0

            # Assumption: status == 'success' marks success; anything else is a failure.
            # Consistent with ConnectionLog usage elsewhere ("success" on HTTP 200, "error" otherwise).
            errorRateRow = await ConnectionLog \
                .annotate(error_count=RawSQL("SUM(CASE WHEN status <> 'success' THEN 1 ELSE 0 END)"), total_count=RawSQL("COUNT(*)")) \
                .filter(agency_id=ag["id"], created_at__gte=now() - timedelta(days=7)) \
                .group_by("agency_id") \
                .values("error_count", "total_count")
            total_count = errorRateRow[0]["total_count"] if len(errorRateRow) > 0 else 0
            error_count = errorRateRow[0]["error_count"] if len(errorRateRow) > 0 else 0
            errorRate = (error_count / total_count * 100) if total_count > 0 else 0

            totalDayRequest = await ConnectionLog.filter(agency_id=ag["id"], created_at__gte=now() - timedelta(days=settings.AVG_LATENCY_WINDOW_DAYS)).count()

            agencies_health.append(AgencyHealth(
                id=str(ag["id"]),
                name=ag["name"],
                shortName=ag["short_name"],
                status=status,
                uptime=round(100.0 - errorRate, 2),
                currentLatency=currentLatency // 1,
                avgLatency=avgLatency // 1,
                errorRate=round(errorRate, 2),
                # Float division: low-traffic agencies (< AVG_LATENCY_WINDOW_DAYS*1440 requests)
                # would floor to 0 with integer division; use round() for a meaningful rate.
                requestsPerMin=round(totalDayRequest / (settings.AVG_LATENCY_WINDOW_DAYS * 1440), 2),
                lastCheckedAt=now()
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
        generatedAt=now()
    )
