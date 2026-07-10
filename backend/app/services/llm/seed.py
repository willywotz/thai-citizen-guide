from app.config import settings
from app.models import LlmProvider, LlmRoute


async def seed_llm_defaults() -> None:
    """Insert default providers/routes from env settings. Never overwrites edits."""
    openrouter, _ = await LlmProvider.get_or_create(
        name="openrouter",
        defaults={
            "base_url": settings.OPENROUTER_API_URL,
            "api_key": settings.OPENROUTER_API_KEY,
            "auth_header": "Authorization",
            "auth_scheme": "Bearer",
            "timeout_seconds": float(settings.LLM_CALL_TIMEOUT),
            "request_usage": True,
        },
    )
    thaillm, _ = await LlmProvider.get_or_create(
        name="thaillm",
        defaults={
            "base_url": settings.PARSE_SPEC_URL,
            "api_key": settings.PARSE_SPEC_API_KEY,
            "auth_header": "apikey",
            "auth_scheme": "",
            "timeout_seconds": float(settings.PARSE_SPEC_TIMEOUT),
            "request_usage": False,
        },
    )
    routes = [
        ("classification", openrouter, settings.CLASSIFICATION_MODEL, None),
        ("brief", openrouter, settings.CLASSIFICATION_MODEL, float(settings.WEEKLY_BRIEF_TIMEOUT)),
        ("judge", openrouter, settings.CLASSIFICATION_MODEL, None),
        ("parse_spec", thaillm, settings.PARSE_SPEC_LLM_MODEL, None),
        # Falls back to the classification model/provider until configured otherwise.
        ("popular_questions", openrouter, settings.CLASSIFICATION_MODEL, None),
    ]
    for purpose, provider, model, timeout_override in routes:
        await LlmRoute.get_or_create(
            purpose=purpose,
            defaults={"provider": provider, "model": model, "timeout_override": timeout_override},
        )
