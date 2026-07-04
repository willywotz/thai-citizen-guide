from app.config import SETTINGS_GROUPS


def test_llm_provider_settings_not_editable_via_generic_ui():
    flat = {k for v in SETTINGS_GROUPS.values() for k in v}
    for key in ("OPENROUTER_API_KEY", "OPENROUTER_API_URL", "CLASSIFICATION_MODEL",
                "PARSE_SPEC_URL", "PARSE_SPEC_API_KEY", "PARSE_SPEC_LLM_MODEL"):
        assert key not in flat
