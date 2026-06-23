"""Single transactional writer for a chat turn (conversation + 2 messages)."""
from dataclasses import dataclass

from tortoise.exceptions import DoesNotExist
from tortoise.transactions import in_transaction

from app.config import settings
from app.models.conversation import Conversation, Message
from app.utils import now


@dataclass
class SavedTurn:
    user_message_id: str
    assistant_message_id: str
    conversation_id: str


async def save_turn(
    *,
    query: str,
    conversation_id: str,
    answer: str,
    references: list,
    category: str | None,
    agency_ids: list[str],
    response_time: int,
    user,
    succeeded: bool,
    external_session_id: str | None = None,
    errors: list | None = None,
) -> SavedTurn:
    """Create/extend a conversation and write the user+assistant messages atomically.

    `succeeded=False` records the conversation as status="failed" so it never
    seeds the similarity cache (find_similar_question filters status="success").
    """
    status = "success" if succeeded else "failed"
    async with in_transaction():
        try:
            conv = await Conversation.get(id=conversation_id)
            conv.message_count += 2
            conv.updated_at = now()
            if not succeeded:
                # One-way ratchet: once "failed", status is never restored to "success",
                # keeping the conversation out of the similarity cache on recovery.
                conv.status = "failed"
            await conv.save()
        except DoesNotExist:
            conv = await Conversation.create(
                id=conversation_id,
                title=query[: settings.TITLE_MAX_LENGTH],
                preview=query[: settings.PREVIEW_MAX_LENGTH],
                agencies=[],
                status=status,
                message_count=2,
                response_time=response_time,
                user_id=user.id if user else None,
                external_session_id=external_session_id,
            )
        user_msg = await Message.create(
            conversation_id=conversation_id, role="user", content=query, category=category,
        )
        asst_msg = await Message.create(
            parent_id=user_msg.id,
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            sources=references,
            response_time=response_time,
            agency_ids=agency_ids,
            errors=errors or [],
        )
    return SavedTurn(str(user_msg.id), str(asst_msg.id), conversation_id)
