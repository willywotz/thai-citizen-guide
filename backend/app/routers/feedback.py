from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_permission
from app.models import Message, Conversation
from app.schemas.dashboard import FeedbackStats

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("/stats")
async def get_feedback_stats(
    db: AsyncSession = Depends(get_db),
    auth=Depends(require_permission("dashboard.read")),
):
    now = datetime.now(timezone.utc)

    # Total ratings
    total_result = await db.execute(
        select(
            func.count(Message.id).filter(Message.rating.in_(["up", "down"])).label("total"),
            func.count(Message.id).filter(Message.rating == "up").label("up_count"),
            func.count(Message.id).filter(Message.rating == "down").label("down_count"),
        )
    )
    row = total_result.one()
    total = row.total or 0
    up_count = row.up_count or 0
    down_count = row.down_count or 0
    satisfaction = round((up_count / total * 100) if total else 0.0, 1)

    # Daily trend (last 14 days)
    daily_trend = []
    for i in range(13, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        result = await db.execute(
            select(
                func.count(Message.id).filter(Message.rating == "up").label("up"),
                func.count(Message.id).filter(Message.rating == "down").label("down"),
            ).where(
                Message.created_at >= day_start,
                Message.created_at < day_end,
                Message.rating.in_(["up", "down"]),
            )
        )
        dr = result.one()
        day_total = (dr.up or 0) + (dr.down or 0)
        daily_trend.append({
            "date": day.strftime("%m-%d"),
            "up": dr.up or 0,
            "down": dr.down or 0,
            "rate": round(((dr.up or 0) / day_total * 100) if day_total else 0.0, 1),
        })

    # Low-rated questions (down-rated with feedback)
    low_result = await db.execute(
        select(Message.content, Message.feedback_text, Message.created_at, Conversation.agencies)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Message.rating == "down", Message.role == "user")
        .order_by(Message.created_at.desc())
        .limit(10)
    )
    low_rated = [
        {
            "content": r.content[:200],
            "feedback_text": r.feedback_text,
            "agency": (r.agencies[0] if r.agencies else "unknown"),
            "created_at": r.created_at.isoformat(),
        }
        for r in low_result.fetchall()
    ]

    # Agency breakdown
    agency_result = await db.execute(
        select(
            func.unnest(Conversation.agencies).label("agency"),
            func.count(Message.id).filter(Message.rating == "up").label("up"),
            func.count(Message.id).filter(Message.rating == "down").label("down"),
        )
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Message.rating.in_(["up", "down"]))
        .group_by(func.unnest(Conversation.agencies))
    )
    agency_breakdown = []
    for ar in agency_result.fetchall():
        at = (ar.up or 0) + (ar.down or 0)
        agency_breakdown.append({
            "agency": ar.agency,
            "up": ar.up or 0,
            "down": ar.down or 0,
            "rate": round(((ar.up or 0) / at * 100) if at else 0.0, 1),
        })

    return {
        "success": True,
        "data": FeedbackStats(
            totalRatings=total,
            upCount=up_count,
            downCount=down_count,
            satisfactionRate=satisfaction,
            dailyTrend=daily_trend,
            lowRatedQuestions=low_rated,
            agencyBreakdown=agency_breakdown,
        ).model_dump(),
    }
