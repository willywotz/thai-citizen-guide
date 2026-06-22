import logging

from tortoise.expressions import RawSQL
from tortoise.functions import Count
from tortoise.transactions import in_transaction

from app.config import settings
from app.models import Agency, Message
from app.utils import now

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
