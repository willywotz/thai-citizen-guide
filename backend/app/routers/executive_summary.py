import asyncio
from datetime import timedelta

from fastapi import APIRouter
import httpx

from app.config import settings
from app.utils import now
from app.schemas.executive_summary import ExecutiveData, ExecutiveKPIs
from app.models import Message, Conversation

router = APIRouter(tags=["executive"])

@router.get("/executive-summary")
async def get_executive_summary() -> ExecutiveData:

    thisMonthQuestions = await Message.filter(role="user", created_at__month=now().month).count()
    lastMonthQuestions = await Message.filter(role="user", created_at__month=now().month-1).count()
    thisYearQuestions = await Message.filter(role="user", created_at__year=now().year).count()
    lastYearQuestions = await Message.filter(role="user", created_at__year=now().year-1).count()

    momGrowthQuestions = ((thisMonthQuestions - lastMonthQuestions) / lastMonthQuestions * 100) if lastMonthQuestions > 0 else thisMonthQuestions * 100.0
    yoyGrowthQuestions = ((thisYearQuestions - lastYearQuestions) / lastYearQuestions * 100) if lastYearQuestions > 0 else thisYearQuestions * 100.0

    thisMonthCitizens = await Conversation.filter(created_at__month=now().month).count()
    lastMonthCitizens = await Conversation.filter(created_at__month=now().month-1).count()
    thisYearCitizens = await Conversation.filter(created_at__year=now().year).count()
    lastYearCitizens = await Conversation.filter(created_at__year=now().year-1).count()

    momGrowthCitizens = ((thisMonthCitizens - lastMonthCitizens) / lastMonthCitizens * 100) if lastMonthCitizens > 0 else thisMonthCitizens * 100.0
    yoyGrowthCitizens = ((thisYearCitizens - lastYearCitizens) / lastYearCitizens * 100) if lastYearCitizens > 0 else thisYearCitizens * 100.0

    content = f"""
    คุณเป็นนักวิเคราะห์ข้อมูลให้ผู้บริหารระดับสูงของรัฐบาลไทย กรุณาสรุปข้อมูลการใช้งาน AI Portal ในสัปดาห์นี้เป็นภาษาไทย ความยาว 3-4 ย่อหน้า เน้น insights เชิงกลยุทธ์และข้อเสนอแนะเชิงนโยบาย
ข้อมูล:
- คำถามรวมเดือนนี้: {thisMonthQuestions} (เพิ่มขึ้น {momGrowthQuestions:.2f}% จากเดือนก่อน, เพิ่มขึ้น {yoyGrowthQuestions:.2f}% จากปีก่อน)
- ประชาชนที่ได้รับบริการเดือนนี้: {thisMonthCitizens} คน (เพิ่มขึ้น {momGrowthCitizens:.2f}% จากเดือนก่อน, เพิ่มขึ้น {yoyGrowthCitizens:.2f}% จากปีก่อน)
- หน่วยงานที่ใช้งานสูงสุด: -
- หัวข้อที่ประชาชนถามบ่อย: -
โครงสร้าง:
1. ภาพรวมและไฮไลท์สัปดาห์
2. แนวโน้มที่น่าสนใจและสาเหตุที่เป็นไปได้
3. ข้อเสนอแนะเชิงนโยบายสำหรับผู้บริหาร
ใช้ภาษาทางการ กระชับ ชัดเจน มี emoji ประกอบเล็กน้อย"""
    
    weeklyBrief = await get_weeklyBrief(content)
    
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
        monthlyTrend=[],
        topIssues=[],
        weeklyBrief=weeklyBrief,
        generatedAt=now()
    )

weeklyBriefLock = asyncio.Lock()
weeklyBriefResultCache = ""
weeklyBriefResultTime = now()

async def get_weeklyBrief(content: str) -> str:
    async with weeklyBriefLock:
        global weeklyBriefResultCache, weeklyBriefResultTime

        if weeklyBriefResultCache and weeklyBriefResultTime and now() - weeklyBriefResultTime < timedelta(minutes=60):
            return weeklyBriefResultCache

        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            header = {"Content-Type": "application/json", "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"}
            payload = {"model": "google/gemma-4-26b-a4b-it", "messages": [{"role": "user", "content": content}]}

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=header, json=payload)

            weeklyBrief = resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            weeklyBrief = "ไม่สามารถสร้างสรุปประจำสัปดาห์ได้ในขณะนี้"

        weeklyBriefResultCache = weeklyBrief
        weeklyBriefResultTime = now()

        return weeklyBrief