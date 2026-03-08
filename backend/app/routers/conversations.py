import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from ..database import get_db
from ..models import Conversation, Message

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class MessageInput(BaseModel):
    id: str | None = None
    role: str
    content: str
    agentSteps: list | None = None
    sources: list | None = None
    rating: str | None = None


class SaveConversationRequest(BaseModel):
    title: str = "สนทนาใหม่"
    preview: str = ""
    agencies: list[str] = []
    status: str = "success"
    responseTime: str | None = None
    messages: list[MessageInput] = []


@router.get("")
async def list_conversations(
    search: str = "",
    filterAgency: str = "",
    db: AsyncSession = Depends(get_db),
):
    start_time = __import__("time").time()

    q = select(Conversation).order_by(Conversation.created_at.desc())

    if search:
        q = q.where(or_(
            Conversation.title.ilike(f"%{search}%"),
            Conversation.preview.ilike(f"%{search}%"),
        ))

    if filterAgency:
        q = q.where(Conversation.agencies.contains([filterAgency]))

    result = await db.execute(q)
    convs = result.scalars().all()

    data = [
        {
            "id": str(c.id),
            "title": c.title,
            "preview": c.preview,
            "date": c.created_at.date().isoformat() if c.created_at else "",
            "agencies": c.agencies or [],
            "status": c.status,
            "messageCount": c.message_count,
            "responseTime": c.response_time or "",
        }
        for c in convs
    ]

    return {
        "success": True,
        "data": data,
        "total": len(data),
        "responseTime": int((__import__("time").time() - start_time) * 1000),
    }


@router.post("")
async def save_conversation(body: SaveConversationRequest, db: AsyncSession = Depends(get_db)):
    conv = Conversation(
        title=body.title or "สนทนาใหม่",
        preview=body.preview or "",
        agencies=body.agencies or [],
        status=body.status or "success",
        message_count=len(body.messages),
        response_time=body.responseTime,
    )
    db.add(conv)
    await db.flush()

    for m in body.messages:
        msg_id = None
        if m.id:
            try:
                msg_id = uuid.UUID(m.id)
            except ValueError:
                pass

        msg = Message(
            id=msg_id or uuid.uuid4(),
            conversation_id=conv.id,
            role=m.role,
            content=m.content,
            agent_steps=m.agentSteps,
            sources=m.sources,
            rating=m.rating,
        )
        db.add(msg)

    await db.commit()
    await db.refresh(conv)
    return {"success": True, "conversationId": str(conv.id)}


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.delete(conv)
    await db.commit()
    return {"success": True}


@router.get("/{conversation_id}/messages")
async def get_messages(conversation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "conversation_id": str(m.conversation_id),
            "role": m.role,
            "content": m.content,
            "agent_steps": m.agent_steps,
            "sources": m.sources,
            "rating": m.rating,
            "feedback_text": m.feedback_text,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]


@router.patch("/messages/{message_id}/rating")
async def update_message_rating(
    message_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    if "rating" in body:
        msg.rating = body["rating"]
    if "feedback_text" in body:
        msg.feedback_text = body["feedback_text"]

    await db.commit()
    return {"success": True}
