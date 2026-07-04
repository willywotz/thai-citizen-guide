from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import LlmProvider, LlmRoute, LlmUsage
from app.services.llm import client as c


def _mock_httpx(json_body, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_body
    resp.text = "body"
    client = MagicMock()
    client.post = AsyncMock(return_value=resp)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=cm), client


@pytest.mark.asyncio
async def test_chat_returns_result_and_records_usage(db):
    c.invalidate()
    p = await LlmProvider.create(name="openrouter", base_url="https://api/x", api_key="sk",
                                 auth_header="Authorization", auth_scheme="Bearer", request_usage=True)
    await LlmRoute.create(purpose="classification", provider=p, model="m1")
    body = {"model": "m1", "choices": [{"message": {"content": "hi", "tool_calls": None}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "cost": 0.001}}
    factory, client = _mock_httpx(body)
    with patch.object(c.httpx, "AsyncClient", factory):
        res = await c.chat(purpose="classification", messages=[{"role": "user", "content": "x"}])
    assert res.content == "hi"
    # auth header + usage-include injected
    _, kwargs = client.post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer sk"
    assert kwargs["json"]["usage"] == {"include": True}
    assert await LlmUsage.filter(purpose="classification").count() == 1


@pytest.mark.asyncio
async def test_chat_non_2xx_raises_llmerror(db):
    c.invalidate()
    p = await LlmProvider.create(name="p", base_url="u", api_key="k")
    await LlmRoute.create(purpose="judge", provider=p, model="m")
    factory, _ = _mock_httpx({"error": "x"}, status=500)
    with patch.object(c.httpx, "AsyncClient", factory):
        with pytest.raises(c.LlmError) as e:
            await c.chat(purpose="judge", messages=[])
    assert e.value.status == 500
