import uuid

import pytest

from app.config import settings
from app.models import LlmUsage
from app.services.quota import QuotaExceeded, check_global_budget, check_user_quota

USER_ID = uuid.UUID(int=0)


async def test_user_over_monthly_quota_raises(db, monkeypatch):
    monkeypatch.setattr(settings, "USER_MONTHLY_TOKEN_QUOTA", 100)
    await LlmUsage.create(model="m", purpose="synthesis", prompt_tokens=90, completion_tokens=20, user_id=USER_ID)
    with pytest.raises(QuotaExceeded):
        await check_user_quota(USER_ID)


async def test_zero_quota_means_unlimited(db, monkeypatch):
    monkeypatch.setattr(settings, "USER_MONTHLY_TOKEN_QUOTA", 0)
    await LlmUsage.create(model="m", purpose="synthesis", prompt_tokens=90, completion_tokens=20, user_id=USER_ID)
    await check_user_quota(USER_ID)  # no raise


async def test_global_daily_cost_kill_switch(db, monkeypatch):
    monkeypatch.setattr(settings, "GLOBAL_DAILY_COST_LIMIT_USD", 0.01)
    await LlmUsage.create(model="m", purpose="synthesis", cost_usd=0.02)
    with pytest.raises(QuotaExceeded):
        await check_global_budget()
