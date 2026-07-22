"""OpenAI-compatible Responses API.

    POST /api/v1/responses    stream=false → a complete Response object
                              stream=true  → OpenAI SSE
    WS   /api/v1/responses    response.create frames in, the same events out

All three transports drive one `run_response()` generator, so their wire output
cannot drift. Errors use OpenAI's envelope (services/responses/errors.py), not
the portal's.
"""
import json
import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from opentelemetry import trace

from app.auth.dependencies import get_current_user_optional
from app.models.user import User
from app.schemas.responses import ResponsesRequest
from app.services.chat.stream import ConversationNotFound, prepare_turn, run_turn
from app.services.quota import QuotaExceeded, check_global_budget, check_user_quota
from app.services.rate_limit import user_limiter
from app.config import settings
from app.services.responses.continuity import resolve_conversation, response_id_for
from app.services.responses.errors import ResponsesApiError
from app.services.responses.request import extract_query, resolve_model
from app.services.responses.translate import ResponseAccumulator

router = APIRouter(prefix="/responses", tags=["Responses"])
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)


async def _enforce_limits(user: User | None) -> None:
    """Rate limit and quota, in OpenAI's error vocabulary."""
    if user is not None:
        result = await user_limiter.check(f"user:{user.id}", limit=settings.USER_RATE_LIMIT_RPM)
        if not result.allowed:
            raise ResponsesApiError(
                "Rate limit exceeded", type="rate_limit_error",
                code="rate_limit_exceeded", status=429,
            )
    try:
        await check_global_budget()
        if user is not None:
            await check_user_quota(user.id)
    except QuotaExceeded as e:
        raise ResponsesApiError(
            str(e), type="rate_limit_error", code="quota_exceeded", status=429,
        )


async def run_response(
    request: ResponsesRequest,
    *,
    user: User | None,
    background_tasks: BackgroundTasks | None,
    cache: dict[str, str] | None = None,
) -> AsyncIterator[dict]:
    """Drive one turn and yield OpenAI Responses events.

    Shared by every transport. `cache` is a WebSocket connection's local
    response-id → conversation-id map; None on HTTP.
    """
    await _enforce_limits(user)
    model, stream_version = resolve_model(request.model)
    query = extract_query(request.input)
    conversation_id, is_continuation = await resolve_conversation(
        previous_response_id=request.previous_response_id,
        conversation=request.conversation,
        cache=cache,
    )

    try:
        plan = await prepare_turn(
            query=query, conversation_id=conversation_id, user=user,
            is_continuation=is_continuation,
        )
    except ConversationNotFound:
        raise ResponsesApiError(
            f"Conversation '{conversation_id}' not found",
            param="conversation", code="conversation_not_found", status=404,
        )

    # A model id that pins a version wins over CHAT_STREAM_VERSION.
    if plan.stream_version != stream_version:
        plan.stream_version = stream_version
        plan.upstream_url = (
            settings.ONECHAT_V4_URL if stream_version == "v4" else settings.ONECHAT_V5_URL
        )

    accumulator = ResponseAccumulator(
        response_id=response_id_for(plan.assistant_message_id),
        model=model,
        conversation_id=conversation_id,
        cached=plan.cached is not None,
        stream_version=plan.stream_version,
    )
    yield accumulator.created_event()

    async for chat_event in run_turn(plan, background_tasks=background_tasks):
        for event in accumulator.consume(chat_event):
            yield event

    if cache is not None:
        cache[accumulator.response_id] = conversation_id


@router.post("", summary="Create a model response (OpenAI Responses API compatible)")
async def create_response(
    body: ResponsesRequest,
    background_tasks: BackgroundTasks,
    user: User | None = Depends(get_current_user_optional),
) -> Any:
    with tracer.start_as_current_span("responses_endpoint") as span:
        span.set_attribute("stream", body.stream)

        if body.stream:
            async def sse() -> AsyncIterator[str]:
                async for event in run_response(
                    body, user=user, background_tasks=background_tasks,
                ):
                    yield f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                sse(), media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        final = None
        async for event in run_response(body, user=user, background_tasks=background_tasks):
            if event["type"] in ("response.completed", "response.failed"):
                final = event["response"]
        if final is None:
            raise ResponsesApiError(
                "The upstream produced no answer.", type="server_error",
                code="no_answer", status=502,
            )
        return final
