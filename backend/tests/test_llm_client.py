import httpx

from app.models import LlmUsage
from app.services import llm_client


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
