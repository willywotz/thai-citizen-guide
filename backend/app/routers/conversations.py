"""
Conversation & message-history routes.

Endpoints
---------
  POST   /conversations                Save a new conversation (with messages)
  GET    /conversations                List conversations (history) — with search/filter
  GET    /conversations/{id}           Get single conversation with messages
  DELETE /conversations/{id}           Delete conversation (cascades to messages)
"""

import time
import uuid

from fastapi import APIRouter, HTTPException, Query, status, Depends
from app.auth.dependencies import require_admin, get_current_user, get_current_user_optional
from app.models.user import User
from tortoise.exceptions import DoesNotExist

from app.models.conversation import Conversation, Message
from app.schemas.conversation import (
    ConversationResponse,
    HistoryItem,
    HistoryResponse,
    SaveConversationRequest,
)
from app.utils import now

router = APIRouter(prefix="/conversations", tags=["Conversations"])


# ---------------------------------------------------------------------------
# Save conversation  (mirrors save-conversation edge function)
# ---------------------------------------------------------------------------

@router.post(
    "",
    summary="Save conversation with messages",
    status_code=status.HTTP_201_CREATED,
)
async def save_conversation(body: SaveConversationRequest, user: User | None = Depends(get_current_user_optional)) -> dict:
    # Create conversation record
    conv = await Conversation.create(
        title=body.title or "สนทนาใหม่",
        preview=body.preview or "",
        agencies=body.agencies,
        status=body.status,
        message_count=len(body.messages),
        response_time=body.response_time,
        user_id=user.id if user else None,
    )

    # Bulk-insert messages
    if body.messages:
        msg_rows = []
        for m in body.messages:
            msg_rows.append(
                Message(
                    id=m.id or uuid.uuid4(),
                    conversation_id=conv.id,
                    role=m.role,
                    content=m.content,
                    agent_steps=m.agent_steps or [],
                    sources=m.sources or [],
                    rating=m.rating,
                    feedback_text=m.feedback_text,
                    user_id=user.id if user else None,
                )
            )
        await Message.bulk_create(msg_rows, ignore_conflicts=True)

    return {"success": True, "conversationId": str(conv.id)}


# ---------------------------------------------------------------------------
# List / history  (mirrors chat-history edge function)
# ---------------------------------------------------------------------------

@router.get("", summary="List conversations (history)")
async def list_conversations(
    search: str = Query("", description="Search in title or preview"),
    filter_agency: str = Query("", alias="filterAgency", description="Filter by agency name"),
    user: User = Depends(get_current_user),
) -> HistoryResponse:
    start = time.time()

    qs = Conversation.all()

    if not user.is_admin:
        qs = qs.filter(user_id=user.id)

    if search:
        qs = qs.filter(title__icontains=search)

    if filter_agency:
        # JSON array contains check via raw filter
        qs = qs.filter(agencies__contains=filter_agency)

    convs = await qs.order_by("-created_at")

    items = [
        HistoryItem(
            id=str(c.id),
            title=c.title,
            preview=c.preview or "",
            date=c.created_at.strftime("%Y-%m-%d"),
            # agencies=c.agencies or [],
            agencies=[],
            status=c.status,
            message_count=c.message_count or 0,
            response_time=c.response_time or "",
        )
        for c in convs
    ]

    return HistoryResponse(
        success=True,
        data=items,
        total=len(items),
        response_time=int((time.time() - start) * 1000),
    )


# ---------------------------------------------------------------------------
# Get single conversation with messages
# ---------------------------------------------------------------------------

@router.get("/{conversation_id}", summary="Get conversation with messages")
async def get_conversation(conversation_id: uuid.UUID, user: User = Depends(get_current_user)) -> dict:
    try:
        conv = await Conversation.get(id=conversation_id)
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conv.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="ไม่สามารถเข้าถึงสนทนานี้ได้")

    messages = await Message.filter(conversation_id=conversation_id).order_by("created_at")

    return {
        "id": str(conv.id),
        "title": conv.title,
        "preview": conv.preview,
        "agencies": conv.agencies,
        "status": conv.status,
        "message_count": conv.message_count,
        "response_time": conv.response_time,
        "created_at": conv.created_at.isoformat(),
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "agent_steps": m.agent_steps,
                "sources": m.sources,
                "rating": m.rating,
                "feedback_text": m.feedback_text,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }

@router.get("/{conversation_id}/messages", summary="Get messages for a conversation")
async def get_conversation_messages(conversation_id: uuid.UUID, user: User = Depends(get_current_user)) -> list[dict]:
    try:
        conv = await Conversation.get(id=conversation_id)
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conv.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="ไม่สามารถเข้าถึงสนทนานี้ได้")

    messages = await Message.filter(conversation_id=conversation_id).order_by("created_at")

    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "agent_steps": m.agent_steps,
            "sources": m.sources,
            "rating": m.rating,
            "feedback_text": m.feedback_text,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


# ---------------------------------------------------------------------------
# Delete conversation (cascade to messages via DB FK)
# ---------------------------------------------------------------------------

@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete conversation")
async def delete_conversation(conversation_id: uuid.UUID, user: User = Depends(get_current_user)) -> None:
    try:
        conv = await Conversation.get(id=conversation_id)
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="ไม่สามารถลบสนทนานี้ได้")
    await conv.delete()
