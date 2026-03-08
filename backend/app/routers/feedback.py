from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..database import get_db
from ..models import Message, Conversation

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.get("/stats")
async def get_feedback_stats(db: AsyncSession = Depends(get_db)):
    # Get all rated messages
    result = await db.execute(
        select(Message)
        .where(Message.rating.isnot(None))
        .order_by(Message.created_at.desc())
    )
    messages = result.scalars().all()

    up_count = sum(1 for m in messages if m.rating == "up")
    down_count = sum(1 for m in messages if m.rating == "down")
    total_ratings = up_count + down_count
    satisfaction_rate = round((up_count / total_ratings) * 100) if total_ratings > 0 else 0

    # Daily trend (last 14 days)
    now = datetime.now(timezone.utc)
    daily_map: dict[str, dict] = {}
    for i in range(13, -1, -1):
        d = now - timedelta(days=i)
        key = d.date().isoformat()
        daily_map[key] = {"up": 0, "down": 0}

    for m in messages:
        if m.created_at:
            day = m.created_at.date().isoformat()
            if day in daily_map:
                if m.rating == "up":
                    daily_map[day]["up"] += 1
                elif m.rating == "down":
                    daily_map[day]["down"] += 1

    daily_trend = [
        {
            "date": key[5:],  # MM-DD
            "up": v["up"],
            "down": v["down"],
            "rate": round((v["up"] / (v["up"] + v["down"])) * 100) if (v["up"] + v["down"]) > 0 else 0,
        }
        for key, v in daily_map.items()
    ]

    # Low rated questions
    down_rated = [m for m in messages if m.rating == "down"][:10]
    low_rated_questions = []
    for dr in down_rated:
        user_msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == dr.conversation_id, Message.role == "user")
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        user_msg = user_msg_result.scalar_one_or_none()

        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == dr.conversation_id)
        )
        conv = conv_result.scalar_one_or_none()

        low_rated_questions.append({
            "content": user_msg.content if user_msg else "ไม่ทราบคำถาม",
            "feedback_text": dr.feedback_text,
            "agency": ", ".join(conv.agencies or []) if conv else "-",
            "created_at": dr.created_at.isoformat() if dr.created_at else None,
        })

    # Agency breakdown
    agency_map: dict[str, dict] = {}
    for m in messages:
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == m.conversation_id)
        )
        conv = conv_result.scalar_one_or_none()
        for ag in (conv.agencies or []) if conv else []:
            if ag not in agency_map:
                agency_map[ag] = {"up": 0, "down": 0}
            if m.rating == "up":
                agency_map[ag]["up"] += 1
            else:
                agency_map[ag]["down"] += 1

    agency_breakdown = sorted(
        [
            {
                "agency": ag,
                "up": v["up"],
                "down": v["down"],
                "rate": round((v["up"] / (v["up"] + v["down"])) * 100) if (v["up"] + v["down"]) > 0 else 0,
            }
            for ag, v in agency_map.items()
        ],
        key=lambda x: x["up"] + x["down"],
        reverse=True,
    )

    return {
        "totalRatings": total_ratings,
        "upCount": up_count,
        "downCount": down_count,
        "satisfactionRate": satisfaction_rate,
        "dailyTrend": daily_trend,
        "lowRatedQuestions": low_rated_questions,
        "agencyBreakdown": agency_breakdown,
    }
