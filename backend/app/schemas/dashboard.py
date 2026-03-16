from pydantic import BaseModel
from typing import List, Optional


class DashboardStats(BaseModel):
    totalQuestions: int
    todayQuestions: int
    avgResponseTime: str
    satisfactionRate: float


class AgencyUsage(BaseModel):
    name: str
    value: int
    fill: str


class WeeklyTrend(BaseModel):
    day: str
    questions: int


class CategoryData(BaseModel):
    category: str
    count: int


class DashboardData(BaseModel):
    stats: DashboardStats
    agencyUsage: List[AgencyUsage]
    weeklyTrend: List[WeeklyTrend]
    categoryData: List[CategoryData]


class FeedbackStats(BaseModel):
    totalRatings: int
    upCount: int
    downCount: int
    satisfactionRate: float
    dailyTrend: List[dict]
    lowRatedQuestions: List[dict]
    agencyBreakdown: List[dict]


class ParseSpecRequest(BaseModel):
    specText: str
