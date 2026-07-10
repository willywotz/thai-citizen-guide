import pytest

from app.models import LlmProvider, LlmRoute
from app.services.llm.seed import seed_llm_defaults


@pytest.mark.asyncio
async def test_seed_creates_defaults_and_is_idempotent(db):
    await seed_llm_defaults()
    assert await LlmProvider.filter(name="openrouter").exists()
    assert await LlmProvider.filter(name="thaillm").exists()
    assert {r.purpose for r in await LlmRoute.all()} == {
        "classification", "brief", "judge", "parse_spec", "popular_questions",
    }

    # editing then re-seeding must NOT overwrite
    p = await LlmProvider.get(name="openrouter")
    p.base_url = "https://edited"
    await p.save()
    await seed_llm_defaults()
    assert (await LlmProvider.get(name="openrouter")).base_url == "https://edited"
    assert await LlmRoute.all().count() == 5
