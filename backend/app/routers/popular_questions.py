"""Popular Questions API.

``GET /public/popular-questions`` is anonymous (no auth dependency at all —
mirrors ``app/routers/public_status.py`` so it passes the global role
chokepoint untouched). Everything under ``/popular-questions`` is admin CRUD.
"""
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from tortoise.exceptions import DoesNotExist, IntegrityError

from app.auth.dependencies import require_admin
from app.models.agency import Agency
from app.models.popular_question import PopularQuestion, PopularQuestionSource
from app.models.user import User
from app.schemas.popular_question import (
    PopularQuestionAgency,
    PopularQuestionCreate,
    PopularQuestionListResponse,
    PopularQuestionResponse,
    PopularQuestionUpdate,
)
from app.services.popular_questions import normalize_text_key, published_questions, regenerate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Popular Questions"])


async def _to_response(pq: PopularQuestion) -> PopularQuestionResponse:
    agency = await pq.agency if pq.agency_id else None
    return PopularQuestionResponse(
        id=pq.id,
        text=pq.text,
        agency=PopularQuestionAgency(id=agency.id, name=agency.name, logo=agency.logo) if agency else None,
        source=pq.source,
        pinned=pq.pinned,
        hidden=pq.hidden,
        sort_order=pq.sort_order,
        score=pq.score,
        created_at=pq.created_at,
        updated_at=pq.updated_at,
    )


@router.get("/public/popular-questions", summary="Public popular questions")
async def get_public_popular_questions() -> dict:
    return {"data": await published_questions()}


@router.get(
    "/popular-questions",
    response_model=PopularQuestionListResponse,
    dependencies=[Depends(require_admin)],
    summary="List all popular questions (admin)",
)
async def list_popular_questions():
    rows = await PopularQuestion.all().prefetch_related("agency")
    data = [await _to_response(r) for r in rows]
    return PopularQuestionListResponse(data=data, total=len(data))


@router.post(
    "/popular-questions",
    response_model=PopularQuestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manual popular question",
)
async def create_popular_question(body: PopularQuestionCreate, _: User = Depends(require_admin)):
    if body.agency_id is not None and not await Agency.filter(id=body.agency_id).exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")

    text = body.text.strip()
    try:
        pq = await PopularQuestion.create(
            text=text,
            text_key=normalize_text_key(text),
            agency_id=body.agency_id,
            source=PopularQuestionSource.manual,
            pinned=body.pinned,
            hidden=body.hidden,
            sort_order=body.sort_order,
        )
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="a question with this text already exists")
    return await _to_response(pq)


@router.patch(
    "/popular-questions/{question_id}",
    response_model=PopularQuestionResponse,
    summary="Partial update a popular question",
)
async def update_popular_question(question_id: uuid.UUID, body: PopularQuestionUpdate, _: User = Depends(require_admin)):
    try:
        pq = await PopularQuestion.get(id=question_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Popular question not found")

    if body.agency_id is not None and not await Agency.filter(id=body.agency_id).exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")

    update_data = body.model_dump(exclude_unset=True)
    if update_data.get("text") is not None:
        new_text = update_data["text"].strip()
        update_data["text"] = new_text
        if new_text != pq.text:
            update_data["text_key"] = normalize_text_key(new_text)
            if pq.source == PopularQuestionSource.auto:
                update_data["source"] = PopularQuestionSource.manual

    try:
        await pq.update_from_dict(update_data).save()
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="a question with this text already exists")
    return await _to_response(pq)


@router.delete(
    "/popular-questions/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a popular question",
)
async def delete_popular_question(question_id: uuid.UUID, _: User = Depends(require_admin)):
    try:
        pq = await PopularQuestion.get(id=question_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Popular question not found")
    await pq.delete()


@router.post(
    "/popular-questions/regenerate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger popular questions regeneration",
)
async def trigger_regenerate(background_tasks: BackgroundTasks, _: User = Depends(require_admin)):
    background_tasks.add_task(regenerate)
    return {"status": "scheduled"}
