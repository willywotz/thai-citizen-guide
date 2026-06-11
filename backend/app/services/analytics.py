import asyncio
import logging
from datetime import timedelta

import httpx
from tortoise.expressions import RawSQL
from tortoise.functions import Count
from tortoise.transactions import in_transaction

from app.config import settings
from app.utils import now
from app.models import Agency, Conversation, Message, ConnectionLog
from app.schemas.insight import AgencyHealthData, Agency as AgencyHealth
from app.schemas.executive_summary import ExecutiveData, ExecutiveKPIs

logger = logging.getLogger(__name__)


async def get_dashboard_stats() -> dict:
    async with in_transaction() as conn:
        await conn.execute_query(f"SET TIME ZONE '{settings.TIMEZONE}';")

        stats = {
            "totalQuestions": 0,
            "totalQuestionsTrend": 0.0,
            "todayQuestions": 0,
            "todayQuestionsTrend": 0.0,
            "avgResponseTime": 0.0,
            "avgResponseTimeTrend": 0.0,
            "satisfactionRate": 0.0,
            "satisfactionRateTrend": 0.0,
        }

        stats["totalQuestions"] = await Message.filter(role="user").count()

        today_start = now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now().replace(hour=23, minute=59, second=59, microsecond=999999)
        stats["todayQuestions"] = await Message.filter(role="user", created_at__range=(today_start, today_end)).count()

        avg_response_time = await Message.annotate(avg_time=RawSQL("AVG(response_time) / 1000")).values("avg_time")
        avg_response_time = avg_response_time[0]["avg_time"] if avg_response_time else 0
        stats["avgResponseTime"] = float(round(avg_response_time or 0, 2))

        rate = await Message.annotate(rate=RawSQL("avg(case when rating = 'up' then 1 else 0 end) * 100")).filter(rating__isnull=False).values("rate")
        rate = rate[0]["rate"] if rate else 0
        stats["satisfactionRate"] = float(round(rate or 0, 2))

        agency_usage = [
            {"name": a["name"], "value": a["total_calls"], "fill": a["color"]}
            for a in await Agency.all().values("name", "color", "total_calls")
        ]

        day_names = ["อาทิตย์", "จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์"]
        raw_weekly = await conn.execute_query_dict(
            """
            SELECT EXTRACT(DOW FROM created_at)::int AS dow, COUNT(*) AS questions
            FROM messages
            WHERE role = 'user' and created_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY dow
            """
        )
        dow_map = {row["dow"]: row["questions"] for row in raw_weekly}
        weekly_trend = [{"day": day_names[i], "questions": dow_map.get(i, 0)} for i in range(len(day_names))]

        categories = (
            await Message.filter(category__isnull=False)
            .annotate(cnt=Count("id"))
            .group_by("category")
            .values("category", "cnt")
        )
        category_data = sorted(
            [{"category": row["category"], "count": row["cnt"]} for row in categories],
            key=lambda x: x["count"],
            reverse=True,
        )

        return {
            "stats": stats,
            "agencyUsage": agency_usage,
            "weeklyTrend": weekly_trend,
            "categoryData": category_data,
        }


async def get_agency_health() -> AgencyHealthData:
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


_weekly_brief_lock = asyncio.Lock()
_weekly_brief_cache = ""
_weekly_brief_cache_time = now()


async def _get_weekly_brief(content: str) -> str:
    async with _weekly_brief_lock:
        global _weekly_brief_cache, _weekly_brief_cache_time

        if _weekly_brief_cache and _weekly_brief_cache_time and now() - _weekly_brief_cache_time < timedelta(minutes=settings.WEEKLY_BRIEF_CACHE_TTL_MINUTES):
            return _weekly_brief_cache

        try:
            url = settings.OPENROUTER_API_URL
            header = {"Content-Type": "application/json", "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"}
            payload = {"model": settings.CLASSIFICATION_MODEL, "messages": [{"role": "user", "content": content}]}

            async with httpx.AsyncClient(timeout=settings.WEEKLY_BRIEF_TIMEOUT) as client:
                resp = await client.post(url, headers=header, json=payload)

            weekly_brief = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error("Error generating weekly brief: %s", e)
            weekly_brief = "ไม่สามารถสร้างสรุปประจำสัปดาห์ได้ในขณะนี้"

        _weekly_brief_cache = weekly_brief
        _weekly_brief_cache_time = now()

        return weekly_brief


async def get_executive_summary() -> ExecutiveData:
    async with in_transaction() as conn:
        await conn.execute_query(f"SET TIME ZONE '{settings.TIMEZONE}';")

        # (now().month - 1) is 0 in January, which is an invalid month value.
        # Use modular arithmetic so January wraps to December (month 12).
        prev_month = (now().month - 2) % 12 + 1

        thisMonthQuestions = await Message.filter(role="user", created_at__month=now().month).count()
        lastMonthQuestions = await Message.filter(role="user", created_at__month=prev_month).count()
        thisYearQuestions = await Message.filter(role="user", created_at__year=now().year).count()
        lastYearQuestions = await Message.filter(role="user", created_at__year=now().year - 1).count()

        momGrowthQuestions = ((thisMonthQuestions - lastMonthQuestions) / lastMonthQuestions * 100) if lastMonthQuestions > 0 else thisMonthQuestions * 100.0
        yoyGrowthQuestions = ((thisYearQuestions - lastYearQuestions) / lastYearQuestions * 100) if lastYearQuestions > 0 else thisYearQuestions * 100.0

        thisMonthCitizens = await Conversation.filter(created_at__month=now().month).count()
        lastMonthCitizens = await Conversation.filter(created_at__month=prev_month).count()
        thisYearCitizens = await Conversation.filter(created_at__year=now().year).count()
        lastYearCitizens = await Conversation.filter(created_at__year=now().year - 1).count()

        momGrowthCitizens = ((thisMonthCitizens - lastMonthCitizens) / lastMonthCitizens * 100) if lastMonthCitizens > 0 else thisMonthCitizens * 100.0
        yoyGrowthCitizens = ((thisYearCitizens - lastYearCitizens) / lastYearCitizens * 100) if lastYearCitizens > 0 else thisYearCitizens * 100.0

        monthlyTrend = await Message \
            .annotate(month=RawSQL("TO_CHAR(created_at, 'YYYY-MM')")) \
            .filter(created_at__gte=now() - timedelta(days=365)) \
            .group_by("month") \
            .annotate(questions=RawSQL("SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END)")) \
            .annotate(rating_up=RawSQL("SUM(CASE WHEN rating = 'up' THEN 1 ELSE 0 END)")) \
            .annotate(rating_down=RawSQL("SUM(CASE WHEN rating = 'down' THEN 1 ELSE 0 END)")) \
            .values("month", "questions", "rating_up", "rating_down")

        for index, entry in enumerate(monthlyTrend):
            satisfaction = (entry["rating_up"] / (entry["rating_up"] + entry["rating_down"]) * 100) if (entry["rating_up"] + entry["rating_down"]) > 0 else 0.0
            monthlyTrend[index]["satisfaction"] = round(satisfaction, 2)

        content = f"""
        คุณเป็นนักวิเคราะห์ข้อมูลให้ผู้บริหารระดับสูงของรัฐบาลไทย กรุณาสรุปข้อมูลการใช้งาน AI Portal ในสัปดาห์นี้เป็นภาษาไทย ความยาว 3-4 ย่อหน้า เน้น insights เชิงกลยุทธ์และข้อเสนอแนะเชิงนโยบาย
    ข้อมูล:
    - คำถามรวมเดือนนี้: {thisMonthQuestions} (เพิ่มขึ้น {momGrowthQuestions:.2f}% จากเดือนก่อน, เพิ่มขึ้น {yoyGrowthQuestions:.2f}% จากปีก่อน)
    - ประชาชนที่ได้รับบริการเดือนนี้: {thisMonthCitizens} คน (เพิ่มขึ้น {momGrowthCitizens:.2f}% จากเดือนก่อน, เพิ่มขึ้น {yoyGrowthCitizens:.2f}% จากปีก่อน)
    - แนวโน้มรายเดือน: {monthlyTrend}
    โครงสร้าง:
    1. ภาพรวมและไฮไลท์สัปดาห์
    2. แนวโน้มที่น่าสนใจและสาเหตุที่เป็นไปได้
    3. ข้อเสนอแนะเชิงนโยบายสำหรับผู้บริหาร
    ใช้ภาษาทางการ กระชับ ชัดเจน มี emoji ประกอบเล็กน้อย"""

        weeklyBrief = await _get_weekly_brief(content)

        return ExecutiveData(
            kpis=ExecutiveKPIs(
                totalQuestions=thisYearQuestions,
                momGrowth=float(f"{momGrowthQuestions:.2f}"),
                yoyGrowth=float(f"{yoyGrowthQuestions:.2f}"),
                uniqueCitizens=0,
                totalHoursSaved=0.0,
                costSaved=0.0,
                healthScore=0.0,
                uptime=0.0,
                satisfaction=0.0,
                avgResponseTime=0.0,

                thisMonthQuestions=thisMonthQuestions,
                lastMonthQuestions=lastMonthQuestions,
                thisYearQuestions=thisYearQuestions,
                lastYearQuestions=lastYearQuestions,
                momGrowthQuestions=float(f"{momGrowthQuestions:.2f}"),
                yoyGrowthQuestions=float(f"{yoyGrowthQuestions:.2f}"),

                thisMonthCitizens=thisMonthCitizens,
                lastMonthCitizens=lastMonthCitizens,
                thisYearCitizens=thisYearCitizens,
                lastYearCitizens=lastYearCitizens,
                momGrowthCitizens=float(f"{momGrowthCitizens:.2f}"),
                yoyGrowthCitizens=float(f"{yoyGrowthCitizens:.2f}")
            ),
            agencyScorecard=[],
            monthlyTrend=monthlyTrend,
            topIssues=[],
            weeklyBrief=weeklyBrief,
            generatedAt=now()
        )
