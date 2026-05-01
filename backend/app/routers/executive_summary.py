from fastapi import APIRouter

from app.utils import now
from app.schemas.executive_summary import ExecutiveData, ExecutiveKPIs
from app.models import Message

router = APIRouter(tags=["executive"])

@router.get("/executive-summary")
async def get_executive_summary() -> ExecutiveData:

    thisMonthQuestions = await Message.filter(role="user", created_at__month=now().month).count()
    lastMonthQuestions = await Message.filter(role="user", created_at__month=now().month-1).count()
    thisYearQuestions = await Message.filter(role="user", created_at__year=now().year).count()
    lastYearQuestions = await Message.filter(role="user", created_at__year=now().year-1).count()

    momGrowth = ((thisMonthQuestions - lastMonthQuestions) / lastMonthQuestions * 100) if lastMonthQuestions > 0 else 0.0
    yoyGrowth = ((thisYearQuestions - lastYearQuestions) / lastYearQuestions * 100) if lastYearQuestions > 0 else 0.0

    return ExecutiveData(
        kpis=ExecutiveKPIs(
            totalQuestions=thisYearQuestions,
            momGrowth=momGrowth,
            yoyGrowth=yoyGrowth,
            uniqueCitizens=0,
            totalHoursSaved=0.0,
            costSaved=0.0,
            healthScore=0.0,
            uptime=0.0,
            satisfaction=0.0,
            avgResponseTime=0.0
        ),
        agencyScorecard=[],
        monthlyTrend=[],
        topIssues=[],
        weeklyBrief="",
        generatedAt=now()
    )