import time
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_optional_auth, AuthContext
from app.schemas.chat import ChatRequest, ChatResponse, ChatResponseData, AgentStep, Reference, AgencyInfo
from app.graph.graph import run_chat_pipeline
from app.graph.nodes import AGENCY_NAME_MAP, AGENCY_ICON_MAP

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    auth=Depends(get_optional_auth),  # optional — public portal works unauthenticated
):
    start = time.monotonic()
    state = await run_chat_pipeline(body.query, db)
    elapsed_ms = int((time.monotonic() - start) * 1000)

    steps = [
        AgentStep(icon=s.icon, label=s.label, status=s.status)
        for s in state["agent_steps"]
    ]
    references = [
        Reference(agency=r["agency"], title=r["title"], url=r["url"])
        for r in state["references"]
    ]
    agencies = [
        AgencyInfo(
            id=aid,
            name=AGENCY_NAME_MAP.get(aid, aid),
            icon=AGENCY_ICON_MAP.get(aid, "🏢"),
        )
        for aid in state["target_agencies"]
    ]

    return ChatResponse(
        success=True,
        data=ChatResponseData(
            answer=state["synthesized_answer"] or "",
            references=references,
            agentSteps=steps,
            agencies=agencies,
            confidence=state["confidence"],
        ),
        responseTime=elapsed_ms,
    )
