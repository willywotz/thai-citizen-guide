"""
AI-powered OpenAPI spec parser — equivalent of the parse-api-spec edge function.
"""
import json
import httpx
from app.config import settings


async def parse_api_spec(spec_text: str) -> dict:
    if not settings.AI_GATEWAY_KEY:
        raise ValueError("AI_GATEWAY_KEY not configured")

    extract_function = {
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
                    },
                    "auth_header": {"type": "string"},
                    "base_path": {"type": "string"},
                    "rate_limit_rpm": {"type": "integer"},
                    "request_format": {"type": "string", "enum": ["json", "xml"]},
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
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"},
                                "type": {"type": "string"},
                                "description": {"type": "string"},
                                "example": {"type": "string"},
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
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.AI_GATEWAY_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.AI_GATEWAY_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.AI_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an API specification parser. Extract structured information from OpenAPI/Swagger specs.",
                    },
                    {
                        "role": "user",
                        "content": f"Parse this API specification and extract details:\n\n{spec_text[:30000]}",
                    },
                ],
                "tools": [extract_function],
                "tool_choice": {"type": "function", "function": {"name": "extract_api_spec"}},
            },
        )

    if resp.status_code == 429:
        raise ValueError("Rate limit exceeded, please try again later.")
    if resp.status_code == 402:
        raise ValueError("Payment required.")
    if not resp.is_success:
        raise ValueError(f"AI gateway error: {resp.status_code}")

    data = resp.json()
    tool_call = data["choices"][0]["message"]["tool_calls"][0]
    return json.loads(tool_call["function"]["arguments"])
