from uuid import uuid4

import httpx

from app.models import LlmUsage
from app.services import llm_client
from app.services.usage_context import current_api_key_id, current_user_id


class _FakeResponse:
    status_code = 200

    def json(self):
        return {
            "choices": [{"message": {"content": "ok"}}],
            "model": "google/gemini-2.5-flash-lite",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.00002},
        }


async def test_openrouter_chat_records_usage(db, monkeypatch):
    async def fake_post(self, url, **kwargs):
        return _FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    resp = await llm_client.openrouter_chat(
        {"model": "google/gemini-2.5-flash-lite", "messages": []}, purpose="classification",
    )
    assert resp.status_code == 200
    row = await LlmUsage.first()
    assert row.prompt_tokens == 10 and row.completion_tokens == 5
    assert row.cost_usd == 0.00002 and row.purpose == "classification"


async def test_records_attribution_from_context(db, monkeypatch):
    async def fake_post(self, url, **kwargs):
        return _FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    uid, kid = uuid4(), uuid4()
    ut = current_user_id.set(uid)
    kt = current_api_key_id.set(kid)
    try:
        await llm_client.openrouter_chat(
            {"model": "m", "messages": []}, purpose="classification",
        )
    finally:
        current_user_id.reset(ut)
        current_api_key_id.reset(kt)

    row = await LlmUsage.first()
    assert row.user_id == uid
    assert row.api_key_id == kid


async def test_explicit_user_id_overrides_context(db, monkeypatch):
    async def fake_post(self, url, **kwargs):
        return _FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    explicit = uuid4()
    ctx = uuid4()
    tok = current_user_id.set(ctx)
    try:
        await llm_client.openrouter_chat(
            {"model": "m", "messages": []}, purpose="classification", user_id=explicit,
        )
    finally:
        current_user_id.reset(tok)
    row = await LlmUsage.first()
    assert row.user_id == explicit
