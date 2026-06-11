from fastapi import APIRouter, Depends

from app.auth.dependencies import require_admin
from app.models.user import User
from app.schemas.executive_summary import ExecutiveData
from app.services.analytics import get_executive_summary, regenerate_weekly_brief

router = APIRouter(tags=["executive"])


@router.get("/executive-summary", operation_id="get_executive_summary")
async def executive_summary_endpoint() -> ExecutiveData:
    return await get_executive_summary()


@router.post("/executive-summary/regenerate", operation_id="regenerate_executive_summary")
async def regenerate_executive_summary_endpoint(_: User = Depends(require_admin)) -> dict:
    brief = await regenerate_weekly_brief()
    return {"weeklyBrief": brief.content, "status": brief.status, "generatedAt": brief.generated_at}
