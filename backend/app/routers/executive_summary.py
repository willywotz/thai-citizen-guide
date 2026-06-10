from fastapi import APIRouter

from app.schemas.executive_summary import ExecutiveData
from app.services.analytics import get_executive_summary

router = APIRouter(tags=["executive"])


@router.get("/executive-summary")
async def executive_summary_endpoint() -> ExecutiveData:
    return await get_executive_summary()
