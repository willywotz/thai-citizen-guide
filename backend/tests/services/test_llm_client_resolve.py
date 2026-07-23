import pytest

from app.models import LlmProvider, LlmRoute
from app.services.llm import client as c


@pytest.mark.asyncio
async def test_resolve_returns_provider_and_model(db):
    c.invalidate()
    p = await LlmProvider.create(name="openrouter", base_url="u", api_key="k",
                                  auth_header="Authorization", auth_scheme="Bearer",
                                  timeout_seconds=12.0, request_usage=True)
    await LlmRoute.create(purpose="classification", provider=p, model="m1")
    r = await c._resolve("classification")
    assert r.model == "m1" and r.base_url == "u" and r.timeout == 12.0
    assert r.auth_header == "Authorization" and r.request_usage is True


@pytest.mark.asyncio
async def test_resolve_missing_route_raises_config(db):
    c.invalidate()
    with pytest.raises(c.LlmError) as e:
        await c._resolve("nope")
    assert e.value.kind == "config"


@pytest.mark.asyncio
async def test_route_timeout_override_wins(db):
    c.invalidate()
    p = await LlmProvider.create(name="p", base_url="u", api_key="k", timeout_seconds=60.0)
    await LlmRoute.create(purpose="brief", provider=p, model="m", timeout_override=99.0)
    assert (await c._resolve("brief")).timeout == 99.0
