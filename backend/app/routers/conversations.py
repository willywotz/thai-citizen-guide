import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth, require_permission, get_optional_auth, AuthContext
from app.models import Conversation, Message
from app.schemas.conversation import (
    ConversationCreate, ConversationOut, MessageOut, RatingUpdate,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    search: Optional[str] = Query(None),
    agency: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    from app.models import RolePermission
    # Check if user can read all conversations
    perm_result = await db.execute(
        select(RolePermission.permission)
        .where(
            RolePermission.role.in_(auth.roles),
            RolePermission.permission == "conversations.read.all",
        )
        .limit(1)
    )
    can_read_all = perm_result.scalar_one_or_none() is not None

    q = select(Conversation).order_by(Conversation.created_at.desc())

    if not can_read_all:
        q = q.where(Conversation.user_id == uuid.UUID(auth.user_id))

    if search:
        q = q.where(
            Conversation.title.ilike(f"%{search}%") |
            Conversation.preview.ilike(f"%{search}%")
        )
    if agency:
        q = q.where(Conversation.agencies.contains([agency]))

    result = await db.execute(q)
    convs = result.scalars().all()

    return [
        ConversationOut(
            id=c.id,
            title=c.title,
            preview=c.preview,
            date=c.created_at.strftime("%Y-%m-%d"),
            agencies=c.agencies or [],
            status=c.status,
            messageCount=c.message_count,
            responseTime=c.response_time,
        )
        for c in convs
    ]


@router.post("", status_code=201)
async def save_conversation(
    body: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    auth=Depends(get_optional_auth),
):
    user_id = uuid.UUID(auth.user_id) if auth else None
    is_public = auth is None

    conv = Conversation(
        title=body.title or "สนทนาใหม่",
        preview=body.preview,
        agencies=body.agencies,
        status=body.status,
        message_count=len(body.messages),
        response_time=body.responseTime,
        user_id=user_id,
        is_public=is_public,
    )
    db.add(conv)
    await db.flush()  # get conv.id before inserting messages

    for m in body.messages:
        msg_id = uuid.UUID(m.id) if m.id else uuid.uuid4()
        message = Message(
            id=msg_id,
            conversation_id=conv.id,
            role=m.role,
            content=m.content,
            agent_steps=m.agentSteps,
            sources=m.sources,
            rating=m.rating,
        )
        db.add(message)

    await db.commit()
    return {"success": True, "conversationId": str(conv.id)}


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def get_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == uuid.UUID(conversation_id))
    )
    conv = conv_result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Access check
    if not conv.is_public and str(conv.user_id) != auth.user_id and not auth.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    return result.scalars().all()


@router.patch("/{conversation_id}/messages/{message_id}/rating")
async def update_rating(
    conversation_id: str,
    message_id: str,
    body: RatingUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    await db.execute(
        update(Message)
        .where(Message.id == uuid.UUID(message_id))
        .values(rating=body.rating, feedback_text=body.feedback_text)
    )
    await db.commit()
    return {"success": True}


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == uuid.UUID(conversation_id))
    )
    conv = conv_result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Not found")

    if str(conv.user_id) != auth.user_id and not auth.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    await db.execute(delete(Conversation).where(Conversation.id == conv.id))
    await db.commit()
    return {"success": True}
