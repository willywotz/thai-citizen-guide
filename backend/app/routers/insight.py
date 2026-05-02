from datetime import timedelta

from fastapi import APIRouter
from tortoise.expressions import RawSQL
from tortoise.functions import Count

from app.utils import now
from app.schemas.insight import AnalyticsInsightsData, AgencyHealthData, BusiestInsight, HeatmapInsights, UsageHeatmapData, HeatmapRange
from app.models import Agency, Conversation, Message

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
    return AgencyHealthData(
        agencies=[],
        historical=[],
        incidents=[],
        slaCompliance=[],
        generatedAt=now()
    )

@router.get("/usage-heatmap")
async def get_insight_usage_heatmap(range: HeatmapRange) -> UsageHeatmapData:

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
            agency=RawSQL("ANY(agency_ids)"),
            hour=RawSQL("extract(hour from created_at)"),
            cnt=Count("id")
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

        business_hours_count += sum([int(x) for x in list(data)[8:18]])

    dayHourMatrix = list(dayHourMatrix.values())

    peakDay = await Message \
        .annotate(
            day=RawSQL("extract(dow from created_at)"),
            cnt=Count("id")
        ) \
        .filter(role="user", created_at__gte=target_date) \
        .group_by("day") \
        .order_by("-cnt") \
        .values("day")
    
    peakHour = await Message \
        .annotate(
            hour=RawSQL("extract(hour from created_at)"),
            cnt=Count("id")
        ) \
        .filter(role="user", created_at__gte=target_date) \
        .group_by("hour") \
        .order_by("-cnt") \
        .values("hour")
    
    try:
        peakDay = int(peakDay[0]["day"])
        peakDay = days_labels[peakDay]
        peakHour = f"{int(peakHour[0]['hour']):02d}:00"
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
            peakDay=peakDay or "",
            peakHour=peakHour or "",
            peakValue=0,
            totalRequests=0,
            businessHoursPercent=businessHoursPercent,
            busiest=BusiestInsight(
                agency=agencyPeak["agency"] if agencyPeak else "",
                total=agencyPeak["total"] if agencyPeak else 0,
                peakHour=agencyPeak['peakHour'] if agencyPeak else 0,
            ),
            recommendation=""
        ),
        generatedAt=now()
    )