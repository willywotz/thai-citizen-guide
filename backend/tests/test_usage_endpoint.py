from app.models import LlmUsage
from app.routers.insight import usage_summary


async def test_usage_groups_by_purpose(db):
    await LlmUsage.create(model="m", purpose="router", prompt_tokens=10, completion_tokens=2, cost_usd=0.01)
    await LlmUsage.create(model="m", purpose="router", prompt_tokens=5, completion_tokens=1, cost_usd=0.02)
    await LlmUsage.create(model="m", purpose="synthesis", prompt_tokens=7, completion_tokens=3, cost_usd=0.005)

    rows = await usage_summary(group_by="purpose")

    by_key = {r["key"]: r for r in rows}
    assert by_key["router"]["prompt_tokens"] == 15
    assert by_key["router"]["cost_usd"] == 0.03


async def test_usage_groups_by_api_key_with_metadata(db):
    from app.models.user import User, UserAPIKey
    user = await User.create(email="owner@x.com", hashed_password="h", is_active=True)
    key = await UserAPIKey.create(user_id=user.id, name="prod", key_hash="h1", key_prefix="tcg_abc123")

    await LlmUsage.create(model="m", purpose="router", prompt_tokens=10, completion_tokens=2,
                          cost_usd=0.01, api_key_id=key.id)
    await LlmUsage.create(model="m", purpose="router", prompt_tokens=5, completion_tokens=1,
                          cost_usd=0.02)  # keyless

    rows = await usage_summary(group_by="api_key")
    by_key = {r["key"]: r for r in rows}

    keyed = by_key[str(key.id)]
    assert keyed["prompt_tokens"] == 10
    assert keyed["name"] == "prod"
    assert keyed["key_prefix"] == "tcg_abc123"
    assert keyed["owner_email"] == "owner@x.com"

    bucket = by_key["—"]
    assert bucket["prompt_tokens"] == 5
    assert bucket["name"] == "web/session"


async def test_usage_date_filter(db):
    from datetime import datetime, timezone
    old = await LlmUsage.create(model="m", purpose="router", prompt_tokens=1, completion_tokens=0)
    await LlmUsage.filter(id=old.id).update(created_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
    await LlmUsage.create(model="m", purpose="router", prompt_tokens=9, completion_tokens=0)

    rows = await usage_summary(group_by="purpose", date_from=datetime(2021, 1, 1, tzinfo=timezone.utc))
    by_key = {r["key"]: r for r in rows}
    assert by_key["router"]["prompt_tokens"] == 9
