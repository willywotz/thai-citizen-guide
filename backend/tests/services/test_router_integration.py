from app.config import settings
from app.services.chat.dispatch import _dispatch_timeout
from app.services.chat.llm import build_router_prompt


def test_router_prompt_includes_router_hint():
    agencies = [{
        "id": "1", "name": "RD", "connection_type": "API",
        "endpoint_url": "https://x", "description": "tax",
        "data_scope": ["ภาษี"], "router_hint": "คำถามภาษีนำเข้า",
    }]
    prompt = build_router_prompt(agencies)
    assert "คำถามภาษีนำเข้า" in prompt


def test_router_prompt_without_hint_is_fine():
    agencies = [{
        "id": "1", "name": "RD", "connection_type": "API",
        "endpoint_url": "https://x", "description": "tax", "data_scope": [],
    }]
    prompt = build_router_prompt(agencies)  # no router_hint key → no crash
    assert "RD" in prompt


def test_dispatch_timeout_prefers_per_agency():
    assert _dispatch_timeout({"dispatch_timeout_s": 45}) == 45


def test_dispatch_timeout_falls_back_to_global():
    assert _dispatch_timeout({"dispatch_timeout_s": None}) == settings.AGENCY_CHAT_TIMEOUT
    assert _dispatch_timeout({}) == settings.AGENCY_CHAT_TIMEOUT
