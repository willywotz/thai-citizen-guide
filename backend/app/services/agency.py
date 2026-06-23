import json as _json
import time
import uuid
from typing import Any

import httpx

from app.config import settings
from app.models.agency import Agency


async def test_connection(connection_type: str, agency: Agency) -> dict[str, Any]:
    if connection_type == "API":
        return await _test_rest(agency)
    if connection_type == "MCP":
        return await _test_mcp(agency)
    if connection_type == "A2A":
        return await _test_a2a(agency)
    return {
        "success": False,
        "protocol": "UNKNOWN",
        "version": "-",
        "steps": [],
        "latency": "0ms",
        "error": "Unsupported connection type",
    }


async def parse_spec(spec_text: str) -> dict[str, Any]:
    """Call LLM to parse an OpenAPI spec and extract structured metadata.

    Raises ValueError on LLM API error or missing tool call arguments.
    """
    payload = {
        "model": settings.PARSE_SPEC_LLM_MODEL,
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
                            "rate_limit_rpm": {
                                "type": "integer",
                                "description": "Rate limit in requests per minute if specified, null otherwise",
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

    async with httpx.AsyncClient(timeout=settings.PARSE_SPEC_TIMEOUT) as client:
        resp = await client.post(
            settings.PARSE_SPEC_URL,
            headers={"Content-Type": "application/json", "apikey": settings.PARSE_SPEC_API_KEY},
            json=payload,
        )

    resp.raise_for_status()  # raises httpx.HTTPStatusError for non-2xx

    data = resp.json()
    tool_call = (data.get("choices") or [{}])[0].get("message", {}).get("tool_calls", [{}])[0]
    args_raw = tool_call.get("function", {}).get("arguments")

    if not args_raw:
        raise ValueError("Failed to parse specification")

    return _json.loads(args_raw)


async def _test_rest(agency: Agency) -> dict[str, Any]:
    """Real REST API probe: HEAD with GET fallback, captures status + headers."""
    url = agency.endpoint_url.strip()
    if not url:
        return {"success": False, "protocol": "REST API", "version": "-", "steps": [], "latency": "0ms", "error": "Endpoint URL is required"}

    steps: list[dict] = []
    total_start = time.monotonic()
    headers = {"User-Agent": f"{settings.USER_AGENT_PREFIX} ConnectionTest"}

    s1 = time.monotonic()
    response = None
    method = "HEAD"
    last_exc: Exception | None = None

    async with httpx.AsyncClient(timeout=settings.CONNECTION_TEST_TIMEOUT) as client:
        # Probe reachability with HEAD, falling back to GET. Some endpoints reject
        # HEAD (404/405/501/...); a 2xx from either means the endpoint is reachable.
        for probe_method in ("HEAD", "GET"):
            try:
                response = await getattr(client, probe_method.lower())(url, headers=headers)
                method = probe_method
            except Exception as exc:
                last_exc = exc
                continue
            if 200 <= response.status_code < 300:
                break

        s1_ms = int((time.monotonic() - s1) * 1000)

        if response is None:
            fetch_error = (
                f"Connection timeout ({settings.CONNECTION_TEST_TIMEOUT}s)"
                if isinstance(last_exc, httpx.TimeoutException)
                else str(last_exc)
            )
            steps.append({"step": 1, "label": "TCP Connection", "status": "error", "time": s1_ms})
            total_ms = int((time.monotonic() - total_start) * 1000)
            steps.append({"step": 2, "label": "HTTP Response", "status": "error", "time": 0})
            return {"success": False, "protocol": "REST API", "version": "-", "steps": steps, "latency": f"{total_ms}ms", "error": fetch_error}

        steps.append({"step": 1, "label": "TCP Connection", "status": "done", "time": s1_ms})

        # POST-only endpoints (e.g. chat APIs) reject a HEAD/GET probe with a non-2xx
        # status. Don't fail on that — POST a probe and judge by the real response.
        if not (200 <= response.status_code < 300):
            from app.services.chat.dispatch import build_api_headers, build_api_payload

            s2 = time.monotonic()
            post_headers = build_api_headers(agency.api_headers)
            post_headers["user-agent"] = headers["User-Agent"]
            probe = build_api_payload(agency.expected_payload or {}, "ทดสอบการเชื่อมต่อ", "")
            try:
                response = await client.post(url, headers=post_headers, json=probe)
                method = "POST"
            except httpx.TimeoutException:
                total_ms = int((time.monotonic() - total_start) * 1000)
                steps.append({"step": 2, "label": "POST probe", "status": "error", "time": int((time.monotonic() - s2) * 1000)})
                return {"success": False, "protocol": "REST API", "version": "-", "steps": steps, "latency": f"{total_ms}ms", "error": f"POST probe timeout ({settings.CONNECTION_TEST_TIMEOUT}s)"}
            except Exception as exc:
                total_ms = int((time.monotonic() - total_start) * 1000)
                steps.append({"step": 2, "label": "POST probe", "status": "error", "time": int((time.monotonic() - s2) * 1000)})
                return {"success": False, "protocol": "REST API", "version": "-", "steps": steps, "latency": f"{total_ms}ms", "error": str(exc)}

    status_code = response.status_code
    steps.append({"step": 2, "label": f"{method} {status_code} {response.reason_phrase}", "status": "done" if status_code < 500 else "error", "time": s1_ms})

    content_type = response.headers.get("content-type", "unknown").split(";")[0]
    server = response.headers.get("server", "unknown")
    steps.append({"step": 3, "label": f"Content-Type: {content_type}", "status": "done", "time": 0})

    total_ms = int((time.monotonic() - total_start) * 1000)

    # HEAD/GET path: only a 2xx reaches here (any other status fell through to POST),
    # so the endpoint is reachable. POST path: only a 2xx confirms the chat method works.
    if method == "POST":
        is_success = 200 <= status_code < 300
        last_label = "API verified (POST)" if is_success else f"POST returned HTTP {status_code}"
    else:
        is_success = True
        last_label = "API Reachable"
    steps.append({"step": 4, "label": last_label, "status": "done" if is_success else "error", "time": 0})

    result = {
        "success": is_success,
        "protocol": "REST API",
        "version": "v1",
        "steps": steps,
        "latency": f"{total_ms}ms",
        "statusCode": status_code,
        "statusText": response.reason_phrase,
        "server": server,
        "contentType": content_type,
    }
    if not is_success and method == "POST":
        result["error"] = f"POST probe returned HTTP {status_code} {response.reason_phrase}"
    return result


async def _test_mcp(agency: Agency) -> dict[str, Any]:
    """Real MCP probe: send a JSON-RPC 2.0 `initialize` request and verify the
    server returns a valid capabilities response.

    MCP spec: https://modelcontextprotocol.io/specification
    """
    steps: list[dict] = []
    total_start = time.monotonic()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": f"{settings.USER_AGENT_PREFIX} MCPProbe",
    }

    if not agency.endpoint_url:
        return {"success": False, "protocol": "MCP", "version": "-", "steps": [], "latency": "0ms", "error": "Endpoint URL is required"}

    url = agency.endpoint_url.strip()

    # Step 1 — TCP / HTTP reachability
    s1 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=settings.CONNECTION_TEST_TIMEOUT) as client:
            # Step 2 — MCP initialize handshake
            init_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": settings.MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": settings.USER_AGENT_PREFIX.split("/")[0], "version": settings.MCP_CLIENT_VERSION},
                },
            }
            s1_ms = int((time.monotonic() - s1) * 1000)
            steps.append({"step": 1, "label": "TCP Connection", "status": "done", "time": s1_ms})

            s2 = time.monotonic()
            resp = await client.post(url, json=init_payload, headers=headers)
            s2_ms = int((time.monotonic() - s2) * 1000)

            if resp.status_code >= 500:
                steps.append({"step": 2, "label": f"MCP Handshake — HTTP {resp.status_code}", "status": "error", "time": s2_ms})
                total_ms = int((time.monotonic() - total_start) * 1000)
                return {"success": False, "protocol": "MCP", "version": "-", "steps": steps, "latency": f"{total_ms}ms",
                        "error": f"Server error: HTTP {resp.status_code}"}

            steps.append({"step": 2, "label": "MCP Handshake", "status": "done", "time": s2_ms})

            # Step 3 — parse capabilities from the JSON-RPC result
            s3 = time.monotonic()
            try:
                body = resp.json()
            except Exception:
                body = {}

            result = body.get("result", {})
            server_info = result.get("serverInfo", {})
            raw_caps = result.get("capabilities", {})
            protocol_version = result.get("protocolVersion", "unknown")

            # Flatten capabilities into a human-readable list
            capabilities: list[str] = []
            for group, val in raw_caps.items():
                if isinstance(val, dict):
                    for method in val:
                        capabilities.append(f"{group}/{method}")
                else:
                    capabilities.append(group)
            if not capabilities:
                capabilities = list(raw_caps.keys()) or ["(none advertised)"]

            s3_ms = int((time.monotonic() - s3) * 1000)
            steps.append({"step": 3, "label": f"Capability Exchange — {len(capabilities)} cap(s)", "status": "done", "time": s3_ms})
            steps.append({"step": 4, "label": "Session Established", "status": "done", "time": 0})

    except httpx.TimeoutException:
        total_ms = int((time.monotonic() - total_start) * 1000)
        if not steps:
            steps.append({"step": 1, "label": "TCP Connection", "status": "error", "time": total_ms})
        steps.append({"step": 2, "label": "MCP Handshake", "status": "error", "time": 0})
        return {"success": False, "protocol": "MCP", "version": "-", "steps": steps, "latency": f"{total_ms}ms", "error": f"Connection timeout ({settings.CONNECTION_TEST_TIMEOUT}s)"}
    except Exception as exc:
        total_ms = int((time.monotonic() - total_start) * 1000)
        if not steps:
            steps.append({"step": 1, "label": "TCP Connection", "status": "error", "time": total_ms})
        return {"success": False, "protocol": "MCP", "version": "-", "steps": steps, "latency": f"{total_ms}ms", "error": str(exc)}

    total_ms = int((time.monotonic() - total_start) * 1000)
    return {
        "success": True,
        "protocol": "MCP",
        "version": protocol_version,
        "steps": steps,
        "latency": f"{total_ms}ms",
        "capabilities": capabilities,
        "serverInfo": server_info,
    }


async def _test_a2a(agency: Agency) -> dict[str, Any]:
    steps: list[dict] = []
    total_start = time.monotonic()

    if not agency.endpoint_url:
        return {"success": False, "protocol": "A2A", "version": "-", "steps": [], "latency": "0ms", "error": "Endpoint URL is required"}

    rpc_headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": f"{settings.USER_AGENT_PREFIX} A2AProbe"}

    try:
        async with httpx.AsyncClient(timeout=settings.CONNECTION_TEST_TIMEOUT, follow_redirects=True) as client:
            # ── Phase 1: TCP Connection ──────────────────────────────────────────
            s1 = time.monotonic()
            await client.get(agency.endpoint_url)
            steps.append({"step": 1, "label": "TCP Connection", "status": "done", "time": int((time.monotonic() - s1) * 1000)})

            # ── Phase 2: Chat Query ─────────────────────────
            chat_payload = {"session_id": uuid.uuid4().hex, "query": "ทดสอบการเชื่อมต่อ"}
            s2 = time.monotonic()
            try:
                await client.post(agency.endpoint_url, json=chat_payload, headers=rpc_headers)
                s2_ms = int((time.monotonic() - s2) * 1000)
                steps.append({"step": 2, "label": "Chat Query", "status": "done", "time": s2_ms})
            except Exception as chat_exc:
                s2_ms = int((time.monotonic() - s2) * 1000)
                steps.append({"step": 2, "label": f"Chat failed — {chat_exc}", "status": "error", "time": s2_ms})
    except httpx.TimeoutException:
        total_ms = int((time.monotonic() - total_start) * 1000)
        if not steps:
            steps.append({"step": 1, "label": "TCP Connection", "status": "error", "time": total_ms})
        if len(steps) < 4:
            steps.append({"step": len(steps) + 1, "label": "Timeout", "status": "error", "time": 0})
        return {"success": False, "protocol": "A2A", "version": "-", "steps": steps,
                "latency": f"{total_ms}ms", "error": f"Connection timeout ({settings.CONNECTION_TEST_TIMEOUT}s)"}
    except Exception as exc:
        total_ms = int((time.monotonic() - total_start) * 1000)
        if not steps:
            steps.append({"step": 1, "label": "TCP Connection", "status": "error", "time": total_ms})
        return {"success": False, "protocol": "A2A", "version": "-", "steps": steps,
                "latency": f"{total_ms}ms", "error": str(exc)}

    total_ms = int((time.monotonic() - total_start) * 1000)
    return {
        "success": True,
        "protocol": "A2A",
        "version": "-",
        "steps": steps,
        "latency": f"{total_ms}ms",
    }
