import httpx

from opentelemetry import trace

from app.config import settings
from app.models.conversation import Conversation, Message


tracer = trace.get_tracer(__name__)

async def ensure_session_warmed(
    conversation: Conversation,
    onechat_url: str,
    mcp_endpoint_url: str,
) -> None:
    with tracer.start_as_current_span("chat_stream_endpoint") as span:

        if conversation.external_session_id is not None:
            span.set_attribute("session_already_warmed", True)
            return

        first_msg = await Message.filter(
            conversation_id=conversation.id,
            role="user",
        ).order_by("created_at").first()

        if first_msg is None:
            span.set_attribute("no_first_message", True)
            return

        payload = {
            "query": first_msg.content,
            "mcp_endpoint_url": mcp_endpoint_url,
            "session_id": str(conversation.id),
        }

        span.set_attribute("warming_session_for_conversation", str(conversation.id))
        span.set_attribute("query", first_msg.content)

        try:
            async with httpx.AsyncClient(timeout=settings.EXTERNAL_CHAT_TIMEOUT) as client:
                resp = await client.post(onechat_url, json=payload)
                resp.raise_for_status()
                data = resp.json().get("data", {})
                conversation.external_session_id = data.get("session_id") or str(conversation.id)
                span.set_attribute("warmed_session_id", conversation.external_session_id)
        except Exception as e:
            span.set_status(trace.StatusCode.ERROR, f"Session warm-up failed: {str(e)}")
            span.set_attributes({"error": "Session warm-up failed", "exception": str(e)})
            raise e

        try:
            await conversation.save(update_fields=["external_session_id"])
        except Exception as e:
            span.set_status(trace.StatusCode.ERROR, f"Failed to save warmed session: {str(e)}")
            span.set_attributes({"error": "Failed to save warmed session", "exception": str(e)})
            raise e
