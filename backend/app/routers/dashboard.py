"""
Dashboard stats route — port of the Supabase `dashboard-stats` edge function.

Endpoint
--------
  GET  /dashboard/stats
"""

import random
import time
from datetime import datetime, time as dt_time

from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import require_admin, get_current_user
from app.models.user import User
from app.models.conversation import Message
from app.models.agency import Agency
from tortoise import Tortoise
from tortoise.functions import Count
from tortoise.transactions import in_transaction

from app.utils import now


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", summary="Get dashboard statistics and charts data")
async def dashboard_stats(user: User = Depends(get_current_user)) -> dict:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="ไม่สามารถเข้าถึงข้อมูลนี้ได้")

    async with in_transaction() as conn:
        await conn.execute_query("SET TIME ZONE 'Asia/Bangkok';")

        start = time.time()

        stats = {
            # "totalQuestions": 48290 + random.randint(0, 50),
            # "todayQuestions": 150 + random.randint(0, 20),
            # "avgResponseTime": f"{(2.0 + random.random() * 0.6):.1f} วินาที",
            # "satisfactionRate": round(93.5 + random.random() * 2, 1),
        }

        stats["totalQuestions"] = await Message.filter(role="user").count()

        today_start = datetime.combine(now().date(), dt_time.min)
        today_end = datetime.combine(now().date(), dt_time.max)
        stats["todayQuestions"] = await Message.filter(role="user", created_at__range=(today_start, today_end)).count()

        raw_data = await conn.execute_query_dict("SELECT AVG(response_time) AS avg_response_time FROM messages")
        avg_response_time = (raw_data[0]["avg_response_time"] if raw_data else 0) / 1000
        stats["avgResponseTime"] = f"{avg_response_time:.2f} วินาที"

        raw_data = await conn.execute_query_dict("SELECT rating, count(1) as cnt FROM messages where rating IS NOT NULL group BY rating")
        rating_counts = {row["rating"]: row["cnt"] for row in raw_data}
        total_rated = sum(rating_counts.values())
        satisfaction_rate = (rating_counts.get("up", 0) / total_rated * 100) if total_rated > 0 else 0
        stats["satisfactionRate"] = round(satisfaction_rate, 1)

        # agency_usage = [
        #     {"name": "อย.", "value": 12450 + random.randint(0, 100), "fill": "hsl(145 55% 40%)"},
        #     {"name": "กรมสรรพากร", "value": 18320 + random.randint(0, 100), "fill": "hsl(213 70% 45%)"},
        #     {"name": "กรมการปกครอง", "value": 9870 + random.randint(0, 100), "fill": "hsl(25 85% 55%)"},
        #     {"name": "กรมที่ดิน", "value": 7650 + random.randint(0, 100), "fill": "hsl(280 50% 50%)"},
        # ]

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
        weekly_trend = [
            {"day": day_names[i], "questions": dow_map.get(i, 0)}
            for i in range(len(day_names))
        ]

        categories = await Message.filter(category__isnull=False).annotate(cnt=Count("id")).group_by("category").values("category", "cnt")
        category_data = sorted([{"category": row["category"], "count": row["cnt"]} for row in categories], key=lambda x: x["count"], reverse=True)

        return {
            "success": True,
            "data": {
                "stats": stats,
                "agencyUsage": agency_usage,
                "weeklyTrend": weekly_trend,
                "categoryData": category_data,
            },
            "responseTime": int((time.time() - start) * 1000),
        }
