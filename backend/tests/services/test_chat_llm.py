from unittest.mock import AsyncMock, patch, MagicMock
import pytest


def test_build_router_prompt_includes_agency_names():
    from app.services.chat.llm import build_router_prompt

    agencies = [
        {
            "id": "abc-123",
            "name": "กรมสรรพากร",
            "description": "ด้านภาษี",
            "connection_type": "API",
            "endpoint_url": "http://example.com",
            "data_scope": ["ภาษี", "VAT"],
        }
    ]
    result = build_router_prompt(agencies)

    assert "กรมสรรพากร" in result
    assert "abc-123" in result
    assert "ภาษี, VAT" in result


def test_build_router_prompt_empty_agencies():
    from app.services.chat.llm import build_router_prompt

    result = build_router_prompt([])
    assert "routes" in result
    assert "Available sources:" in result


@pytest.mark.asyncio
async def test_call_llm_raises_on_missing_key(monkeypatch):
    monkeypatch.setenv("PARSE_SPEC_API_KEY", "")

    from app.services.chat.llm import call_llm

    with pytest.raises(ValueError, match="Missing LLM API key"):
        await call_llm([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_call_llm_returns_message_on_success(monkeypatch):
    monkeypatch.setenv("PARSE_SPEC_API_KEY", "test-key")
    monkeypatch.setenv("PARSE_SPEC_URL", "http://fake-llm/v1/chat")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "hello"}}]
    }

    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        from app.services.chat.llm import call_llm
        result = await call_llm([{"role": "user", "content": "hi"}])

    assert result == {"role": "assistant", "content": "hello"}
