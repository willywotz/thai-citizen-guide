import httpx

from app.models.conversation import Conversation, Message


async def ensure_session_warmed(
    conversation: Conversation,
    onechat_url: str,
    mcp_endpoint_url: str,
) -> None:
    if conversation.external_session_id is not None:
        return

    first_msg = await Message.filter(
        conversation_id=conversation.id,
        role="user",
    ).order_by("created_at").first()

    if first_msg is None:
        return

    payload = {
        "query": first_msg.content,
        "mcp_endpoint_url": mcp_endpoint_url,
        "session_id": str(conversation.id),
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(onechat_url, json=payload)
        resp.raise_for_status()

    data = resp.json().get("data", {})
    conversation.external_session_id = data.get("session_id") or str(conversation.id)
    await conversation.save(update_fields=["external_session_id"])
