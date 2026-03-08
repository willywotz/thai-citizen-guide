import random
import time
from fastapi import APIRouter

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard_stats():
    start = time.time()

    stats = {
        "totalQuestions": 48290 + random.randint(0, 50),
        "todayQuestions": 150 + random.randint(0, 20),
        "avgResponseTime": f"{(2.0 + random.random() * 0.6):.1f} วินาที",
        "satisfactionRate": round(93.5 + random.random() * 2, 1),
    }

    agency_usage = [
        {"name": "อย.", "value": 12450 + random.randint(0, 100), "fill": "hsl(145 55% 40%)"},
        {"name": "กรมสรรพากร", "value": 18320 + random.randint(0, 100), "fill": "hsl(213 70% 45%)"},
        {"name": "กรมการปกครอง", "value": 9870 + random.randint(0, 100), "fill": "hsl(25 85% 55%)"},
        {"name": "กรมที่ดิน", "value": 7650 + random.randint(0, 100), "fill": "hsl(280 50% 50%)"},
    ]

    weekly_trend = [
        {"day": "จันทร์", "questions": 170 + random.randint(0, 30)},
        {"day": "อังคาร", "questions": 200 + random.randint(0, 30)},
        {"day": "พุธ", "questions": 185 + random.randint(0, 30)},
        {"day": "พฤหัสบดี", "questions": 230 + random.randint(0, 30)},
        {"day": "ศุกร์", "questions": 210 + random.randint(0, 30)},
        {"day": "เสาร์", "questions": 80 + random.randint(0, 30)},
        {"day": "อาทิตย์", "questions": 55 + random.randint(0, 30)},
    ]

    category_data = [
        {"category": "สอบถามข้อมูล", "count": 22450 + random.randint(0, 200)},
        {"category": "ตรวจสอบสถานะ", "count": 12300 + random.randint(0, 200)},
        {"category": "ขั้นตอนดำเนินการ", "count": 8900 + random.randint(0, 200)},
        {"category": "กฎหมาย/ระเบียบ", "count": 4640 + random.randint(0, 200)},
    ]

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
