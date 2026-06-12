from app.models import LlmUsage


async def test_create_usage_row(db):
    row = await LlmUsage.create(
        model="google/gemini-2.5-flash-lite", purpose="classification",
        prompt_tokens=120, completion_tokens=8, cost_usd=0.000034,
    )
    assert row.total_tokens == 128
