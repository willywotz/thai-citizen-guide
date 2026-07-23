from app.config import settings
from app.models import LlmProvider, LlmRoute
from app.services.llm.purpose import Purpose


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
        (Purpose.CLASSIFICATION, openrouter, settings.CLASSIFICATION_MODEL, None),
        (Purpose.BRIEF, openrouter, settings.CLASSIFICATION_MODEL, float(settings.WEEKLY_BRIEF_TIMEOUT)),
        (Purpose.JUDGE, openrouter, settings.CLASSIFICATION_MODEL, None),
        (Purpose.PARSE_SPEC, thaillm, settings.PARSE_SPEC_LLM_MODEL, None),
        # Falls back to the classification model/provider until configured otherwise.
        (Purpose.POPULAR_QUESTIONS, openrouter, settings.CLASSIFICATION_MODEL, None),
    ]
    for purpose, provider, model, timeout_override in routes:
        await LlmRoute.get_or_create(
            purpose=purpose,
            defaults={"provider": provider, "model": model, "timeout_override": timeout_override},
        )
