from datetime import timedelta

from fastapi import APIRouter
from tortoise import Tortoise
from tortoise.expressions import RawSQL
from tortoise.functions import Count
from tortoise.transactions import in_transaction

from app.config import settings
from app.utils import now
from app.schemas.insight import AnalyticsInsightsData, AgencyHealthData, BusiestInsight, HeatmapInsights, UsageHeatmapData, HeatmapRange, Agency as AgencyHealth
from app.models import Agency, Conversation, Message, ConnectionLog

router = APIRouter(tags=["insight"])
days_labels = ["อาทิตย์", "จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์"]
hours_labels = list(range(24))

@router.get("/analytics-insights")
async def get_insight_analytics_insights() -> AnalyticsInsightsData:
    return AnalyticsInsightsData(
        totalWeekQuestions=0,
        topicClusters=[],
        sentimentDist={"positive": 0, "neutral": 0, "negative": 0},
        noAnswerByAgency=[],
        dailyVolume=[],
        trendingTopics=[],
        decliningTopics=[],
        aiInsights="",
        recommendations=[],
        generatedAt=now()
    )

@router.get("/agency-health")
async def get_insight_agency_health() -> AgencyHealthData:

    async with in_transaction() as conn:
        await conn.execute_query(f"SET TIME ZONE '{settings.TIMEZONE}';")

        agencies = await Agency.all().values("id", "name", "short_name", "status")

        agencies_health = []

        for ag in agencies:
            status = {"active": "healthy", "inactive": "down"}.get(ag["status"], "down")

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

            errorRate = await ConnectionLog \
                .annotate(error_count=RawSQL("SUM(CASE WHEN status >= 'success' THEN 1 ELSE 0 END)"), total_count=RawSQL("COUNT(*)")) \
                .filter(agency_id=ag["id"], created_at__gte=now() - timedelta(days=7)) \
                .group_by("agency_id") \
                .values("error_count", "total_count")
            errorRate = (errorRate[0]["error_count"] / errorRate[0]["total_count"]) if len(errorRate) > 0 and errorRate[0]["total_count"] > 0 else 0

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
                requestsPerMin=totalDayRequest // (settings.AVG_LATENCY_WINDOW_DAYS * 1440),
                lastCheckedAt=now()
            ))

        rawHistorical =  await ConnectionLog \
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

@router.get("/usage-heatmap")
async def get_insight_usage_heatmap(range: HeatmapRange) -> UsageHeatmapData:

    async with in_transaction() as conn:
        await conn.execute_query(f"SET TIME ZONE '{settings.TIMEZONE}';")

        target_date = {
            "7d": now() - timedelta(days=7),
            "30d": now() - timedelta(days=30),
            "90d": now() - timedelta(days=90),
        }[range]

        days = (now() - target_date).days

        agencies = await Agency.all().values("id", "name")
        agencies = [{"id": str(a["id"]), "name": a["name"]} for a in agencies]

        total_conversations = await Conversation.filter(created_at__gte=target_date).count()
        total_messages = await Message.filter(role="user", created_at__gte=target_date).count()

        hourlyByAgency = {a["id"]: {"agencyId": str(a["id"]), "agency": a["name"], "data": {h: 0 for h in hours_labels}} for a in agencies}

        rawHourlyByAgency = await Message \
            .annotate(
                hour=RawSQL("extract(hour from created_at)"),
                cnt=Count("id"),
            ) \
            .filter(created_at__gte=target_date) \
            .group_by("agency_ids", "hour") \
            .values("agency_ids", "hour", "cnt")
        
        for entry in rawHourlyByAgency:
            for agency_id in entry["agency_ids"]:
                if agency_id in hourlyByAgency:
                    hourlyByAgency[agency_id]["data"][int(entry["hour"])] += entry["cnt"]
        
        for index, agency in hourlyByAgency.items():
            hourlyByAgency[index]["data"] = agency["data"].values()

        hourlyByAgency = list(hourlyByAgency.values())

        rawDayHourMatrix = await Message \
            .annotate(
                day=RawSQL("extract(dow from created_at)"),
                hour=RawSQL("extract(hour from created_at)"),
                cnt=Count("id")
            ) \
            .filter(role="user", created_at__gte=target_date) \
            .group_by("day", "hour") \
            .values("day", "hour", "cnt")
        
        dayHourMatrix = {i: {"dayIndex": i, "day": day, "data": {h: 0 for h in hours_labels}} for i, day in enumerate(days_labels)}
        
        for entry in rawDayHourMatrix:
            entry["day"] = int(entry["day"])
            entry["hour"] = int(entry["hour"])

            dayHourMatrix[entry["day"]]["data"][entry["hour"]] += entry["cnt"]
            
        business_hours_count = 0

        for index, entry in dayHourMatrix.items():
            data = entry["data"].values()
            dayHourMatrix[index]["data"] = data

            business_hours_count += sum([int(x) for x in list(data)[settings.BUSINESS_HOURS_START:settings.BUSINESS_HOURS_END]])

        dayHourMatrix = list(dayHourMatrix.values())

        peakDay = ""
        peakHour = ""
        peakValue = 0
        
        try:
            rawPeakDay = await Message \
                .annotate(
                    day=RawSQL("extract(dow from created_at)"),
                    cnt=Count("id")
                ) \
                .filter(role="user", created_at__gte=target_date) \
                .group_by("day") \
                .order_by("-cnt") \
                .values("day")
            
            rawPeakHour = await Message \
                .annotate(
                    hour=RawSQL("extract(hour from created_at)"),
                    cnt=Count("id")
                ) \
                .filter(role="user", created_at__gte=target_date) \
                .group_by("hour") \
                .order_by("-cnt") \
                .values("hour", "cnt")
            
            peakDay = days_labels[int(rawPeakDay[0]["day"])] if len(rawPeakDay) > 0 and rawPeakDay[0]["day"] is not None else ""
            peakHour = f"{int(rawPeakHour[0]['hour']):02d}:00" if len(rawPeakHour) > 0 and rawPeakHour[0]["hour"] is not None else ""
            peakValue = int(rawPeakHour[0]["cnt"]) if len(rawPeakHour) > 0 and rawPeakHour[0]["cnt"] is not None else 0
        except:
            pass

        agencyPeak = {"agency": "", "total": 0, "peakHour": 0}

        try:
            listdata = [{
                "agency": entry["agency"],
                "total": sum(entry["data"]),
                "peakHour": max(enumerate(entry["data"]), key=lambda x: x[1])[0] \
                    if sum(entry["data"]) > 0 else 0
            } for entry in hourlyByAgency]

            # print(listdata)

            listdata = sorted(listdata, key=lambda x: x["total"], reverse=True)
            agencyPeak = listdata[0] if len(listdata) > 0 else {"agency": "", "total": 0, "peakHour": 0}
        except:
            pass

        businessHoursPercent = business_hours_count / total_messages * 100 if total_messages > 0 else 0
        businessHoursPercent = round(businessHoursPercent, 2)

        return UsageHeatmapData(
            range=range,
            days=days,
            sampleSize=total_conversations,
            totalMessages=total_messages,
            days_labels=days_labels,
            hours=hours_labels,
            agencies=agencies,
            hourlyByAgency=hourlyByAgency,
            dayHourMatrix=dayHourMatrix,
            insights=HeatmapInsights(
                peakDay=peakDay,
                peakHour=peakHour,
                peakValue=peakValue,
                totalRequests=0,
                businessHoursPercent=businessHoursPercent,
                busiest=BusiestInsight(
                    agency=agencyPeak["agency"] if agencyPeak and "agency" in agencyPeak else "",
                    total=agencyPeak["total"] if agencyPeak and "total" in agencyPeak else 0,
                    peakHour=agencyPeak['peakHour'] if agencyPeak and "peakHour" in agencyPeak else 0,
                ),
                recommendation=""
            ),
            generatedAt=now()
        )