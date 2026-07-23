import json as _json
import time
from typing import Any

import httpx

from app.config import settings
from app.models.agency import Agency

_PROTOCOL = {"API": "REST API", "MCP": "MCP", "A2A": "A2A"}


def _failure(protocol: str, error: str, steps: list[dict] | None = None, latency_ms: int = 0) -> dict[str, Any]:
    return {"success": False, "protocol": protocol, "version": "-", "steps": steps or [],
            "latency": f"{latency_ms}ms", "error": error}


async def test_connection(connection_type: str, agency: Agency) -> dict[str, Any]:
    """Reachability probe: HEAD with a GET fallback.

    Any HTTP response — including 4xx/5xx — means the endpoint is reachable and
    counts as success. Only a transport failure (refused, DNS, timeout) is an
    error. No protocol-level handshake is performed for any connection type.
    """
    protocol = _PROTOCOL.get(connection_type)
    if protocol is None:
        return _failure("UNKNOWN", "Unsupported connection type")

    url = (agency.endpoint_url or "").strip()
    if not url:
        return _failure(protocol, "Endpoint URL is required")

    headers = {"User-Agent": f"{settings.USER_AGENT_PREFIX} ConnectionTest"}
    start = time.monotonic()
    response = None
    method = "HEAD"
    last_exc: Exception | None = None

    async with httpx.AsyncClient(timeout=settings.CONNECTION_TEST_TIMEOUT) as client:
        for probe_method in ("HEAD", "GET"):
            try:
                response = await getattr(client, probe_method.lower())(url, headers=headers)
                method = probe_method
                break
            except Exception as exc:
                last_exc = exc

    elapsed = int((time.monotonic() - start) * 1000)

    if response is None:
        error = (
            f"Connection timeout ({settings.CONNECTION_TEST_TIMEOUT}s)"
            if isinstance(last_exc, httpx.TimeoutException)
            else str(last_exc)
        )
        steps = [{"step": 1, "label": "TCP Connection", "status": "error", "time": elapsed}]
        return _failure(protocol, error, steps, elapsed)

    return {
        "success": True,
        "protocol": protocol,
        "version": "-",
        "steps": [
            {"step": 1, "label": "TCP Connection", "status": "done", "time": elapsed},
            {"step": 2, "label": f"{method} {response.status_code} {response.reason_phrase}", "status": "done", "time": 0},
        ],
        "latency": f"{elapsed}ms",
        "statusCode": response.status_code,
        "statusText": response.reason_phrase,
        "server": response.headers.get("server", "unknown"),
        "contentType": response.headers.get("content-type", "unknown").split(";")[0],
    }


async def parse_spec(spec_text: str) -> dict[str, Any]:
    """Call LLM to parse an OpenAPI spec and extract structured metadata.

    Raises ValueError on LLM API error or missing tool call arguments.
    """
    payload = {
        "messages": [
            {
                "role": "system",
                "content": "You are an API specification parser. Extract structured information from OpenAPI/Swagger specs including response schemas.",
            },
            {
                "role": "user",
                "content": f"Parse this API specification and extract the details including response field schemas:\n\n{spec_text[:settings.SPEC_TEXT_MAX_CHARS]}",
            },
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "extract_api_spec",
                    "description": "Extract structured API specification details including response schemas",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "auth_method": {
                                "type": "string",
                                "enum": ["api_key", "oauth2", "basic_auth", "none"],
                                "description": "Authentication method used by the API",
                            },
                            "auth_header": {
                                "type": "string",
                                "description": "Authentication header name, e.g. X-API-Key, Authorization",
                            },
                            "base_path": {
                                "type": "string",
                                "description": "Base path prefix for all endpoints, e.g. /api/v1",
                            },
                            "request_format": {
                                "type": "string",
                                "enum": ["json", "xml"],
                                "description": "Default request/response format",
                            },
                            "endpoints": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]},
                                        "path": {"type": "string"},
                                        "description": {"type": "string"},
                                    },
                                    "required": ["method", "path", "description"],
                                    "additionalProperties": False,
                                },
                            },
                            "response_schema": {
                                "type": "array",
                                "description": "Common response fields found across endpoint responses",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "field": {"type": "string", "description": "Field name or dot-notation path e.g. data.items[].name"},
                                        "type": {"type": "string", "description": "Data type: string, number, boolean, array, object, date"},
                                        "description": {"type": "string", "description": "What this field contains"},
                                        "example": {"type": "string", "description": "Example value"},
                                    },
                                    "required": ["field", "type", "description"],
                                    "additionalProperties": False,
                                },
                            },
                        },
                        "required": ["auth_method", "auth_header", "base_path", "request_format", "endpoints", "response_schema"],
                        "additionalProperties": False,
                    },
                },
            },
        ],
        "tool_choice": {"type": "function", "function": {"name": "extract_api_spec"}},
    }

    from app.services.llm import Purpose, chat
    res = await chat(purpose=Purpose.PARSE_SPEC, messages=payload["messages"],
                     tools=payload["tools"], tool_choice=payload["tool_choice"])
    tool_call = (res.tool_calls or [{}])[0]
    args_raw = tool_call.get("function", {}).get("arguments")
    if not args_raw:
        raise ValueError("Failed to parse specification")
    return _json.loads(args_raw)
