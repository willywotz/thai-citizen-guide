import pytest

from app.models import LlmProvider, LlmRoute


@pytest.mark.asyncio
async def test_provider_and_route_create_with_fk(db):
    p = await LlmProvider.create(name="openrouter", base_url="https://x/v1/chat/completions",
                                 api_key="k", auth_header="Authorization", auth_scheme="Bearer",
                                 timeout_seconds=60.0, request_usage=True)
    r = await LlmRoute.create(purpose="classification", provider=p, model="m1")
    assert r.purpose == "classification"
    assert (await r.provider).name == "openrouter"
    assert p.max_queue_size == 50 and p.enabled is True
    assert p.rate_limit_rps is None and p.rate_limit_rpm is None


@pytest.mark.asyncio
async def test_purpose_is_unique(db):
    p = await LlmProvider.create(name="p", base_url="u", api_key="k")
    await LlmRoute.create(purpose="brief", provider=p, model="m")
    with pytest.raises(Exception):
        await LlmRoute.create(purpose="brief", provider=p, model="m2")
