"""Single entry point for OpenRouter chat calls — records LlmUsage for every call."""
import logging

import httpx

from app.config import settings
from app.models import LlmUsage
from app.services.usage_context import current_api_key_id, current_user_id

logger = logging.getLogger(__name__)


async def openrouter_chat(
    payload: dict,
    *,
    purpose: str,
    user_id=None,
    agency_id=None,
    conversation_id=None,
    timeout: float | None = None,
) -> httpx.Response:
    payload = {**payload, "usage": {"include": True}}  # OpenRouter returns cost when asked
    async with httpx.AsyncClient(timeout=timeout or settings.LLM_CALL_TIMEOUT) as client:
        resp = await client.post(
            settings.OPENROUTER_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            },
            json=payload,
        )
    await _record_usage(resp, payload, purpose, user_id, agency_id, conversation_id)
    return resp


async def _record_usage(resp, payload, purpose, user_id, agency_id, conversation_id) -> None:
    try:
        body = resp.json()
        usage = body.get("usage") or {}
        await LlmUsage.create(
            model=body.get("model") or payload.get("model", ""),
            purpose=purpose,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            cost_usd=usage.get("cost"),
            user_id=user_id if user_id is not None else current_user_id.get(),
            agency_id=agency_id,
            conversation_id=conversation_id,
            api_key_id=current_api_key_id.get(),
        )
    except Exception:  # accounting must never break the chat path
        logger.exception("failed to record llm usage")
