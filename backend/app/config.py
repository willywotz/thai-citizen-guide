import json
from typing import get_origin

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "AI Chatbot Portal API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    TIMEZONE: str = "Asia/Bangkok"
    USER_AGENT_PREFIX: str = "AI-Chatbot-Portal/1.0"

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgres://postgres:postgres@localhost:5432/chatbot"

    # ── CORS ─────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"]

    # ── Auth ─────────────────────────────────────────────────────────────────
    JWT_SECRET: str = "change-me-in-production-use-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    MIN_PASSWORD_LENGTH: int = 6
    RESET_TOKEN_EXPIRE_HOURS: int = 1
    RESET_TOKEN_BYTES: int = 32
    EXPOSE_PASSWORD_RESET_TOKEN: bool = True  # Set False in production; deliver token by email instead

    # ── LLM / OpenRouter ────────────────────────────────────────────────────
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_API_URL: str = "https://openrouter.ai/api/v1/chat/completions"
    CLASSIFICATION_MODEL: str = "google/gemini-2.5-flash-lite"
    LLM_CALL_TIMEOUT: float = 60.0

    # ── Parse spec (ThaiLLM) ─────────────────────────────────────────────────
    PARSE_SPEC_URL: str = "http://thaillm.or.th/api/openthaigpt/v1/chat/completions"
    PARSE_SPEC_API_KEY: str = ""
    PARSE_SPEC_TIMEOUT: int = 60
    PARSE_SPEC_LLM_MODEL: str = "/model"

    # ── OneChat endpoints ────────────────────────────────────────────────────
    ONECHAT_V3_URL: str = "http://185.84.160.55:8000/v3/chat"
    ONECHAT_V4_URL: str = "http://185.84.160.55:8000/v4/chat"
    MCP_ENDPOINT_URL: str = "http://185.84.161.145/mcp/"

    # ── MCP ──────────────────────────────────────────────────────────────────
    MCP_CLIENT_URL: str = "http://localhost:8080/mcp/"
    MCP_PROTOCOL_VERSION: str = "2024-11-05"
    MCP_CLIENT_VERSION: str = "1.0"

    # ── Chat ─────────────────────────────────────────────────────────────────
    A2A_DISPATCH_TIMEOUT: int = 30
    V4_STREAM_TIMEOUT: float = 300.0
    EXTERNAL_CHAT_TIMEOUT: float = 180.0
    TITLE_MAX_LENGTH: int = 50
    PREVIEW_MAX_LENGTH: int = 100
    CONN_LOG_BODY_MAX: int = 5000
    SPEC_TEXT_MAX_CHARS: int = 30000

    # ── Agency health / scheduler ────────────────────────────────────────────
    AGENCY_CHAT_TIMEOUT: int = 180
    AGENCY_CHAT_CONCURRENCY: int = 5
    HEALTH_CHECK_INTERVAL_MINUTES: int = 15
    CONNECTION_TEST_TIMEOUT: float = 10.0

    # ── Executive summary ────────────────────────────────────────────────────
    WEEKLY_BRIEF_CACHE_TTL_MINUTES: int = 60
    WEEKLY_BRIEF_TIMEOUT: float = 30.0

    # ── Analytics windows ────────────────────────────────────────────────────
    AVG_LATENCY_WINDOW_DAYS: int = 1
    FEEDBACK_TREND_DAYS: int = 14
    BUSINESS_HOURS_START: int = 8
    BUSINESS_HOURS_END: int = 18

    # ── Embedding / similarity ──────────────────────────────────────────────
    EMBEDDING_API_URL: str = "https://api.openai.com/v1/embeddings"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 384
    EMBEDDING_TIMEOUT: int = 5
    SIMILARITY_THRESHOLD: float = 0.95
    SIMILARITY_WINDOW_SECONDS: int = 259200  # 3 days
    SIMILARITY_FALLBACK: str = "both"  # "similarity", "levenshtein", or "both"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def apply_overrides(self, overrides: dict[str, str]) -> None:
        for key, raw_value in overrides.items():
            field_info = self.model_fields.get(key)
            if field_info is None:
                continue
            try:
                parsed = _deserialize(raw_value, field_info.annotation)
                object.__setattr__(self, key, parsed)
            except Exception:
                pass


def _deserialize(raw: str, annotation: type):
    origin = get_origin(annotation)
    if annotation is bool:
        return raw.lower() in ("true", "1", "yes")
    if annotation is int:
        return int(raw)
    if annotation is float:
        return float(raw)
    if origin is list or annotation in (list, list[str]):
        return json.loads(raw)
    return raw


SETTINGS_GROUPS: dict[str, list[str]] = {
    "App": ["APP_NAME", "APP_VERSION", "DEBUG", "TIMEZONE", "USER_AGENT_PREFIX"],
    "Database": ["DATABASE_URL"],
    "CORS": ["CORS_ORIGINS"],
    "Auth": ["JWT_SECRET", "JWT_ALGORITHM", "JWT_EXPIRE_MINUTES", "MIN_PASSWORD_LENGTH", "RESET_TOKEN_EXPIRE_HOURS", "RESET_TOKEN_BYTES", "EXPOSE_PASSWORD_RESET_TOKEN"],
    "LLM / OpenRouter": ["OPENROUTER_API_KEY", "OPENROUTER_API_URL", "CLASSIFICATION_MODEL", "LLM_CALL_TIMEOUT"],
    "Parse spec": ["PARSE_SPEC_URL", "PARSE_SPEC_API_KEY", "PARSE_SPEC_TIMEOUT", "PARSE_SPEC_LLM_MODEL"],
    "OneChat": ["ONECHAT_V3_URL", "ONECHAT_V4_URL", "MCP_ENDPOINT_URL"],
    "MCP": ["MCP_CLIENT_URL", "MCP_PROTOCOL_VERSION", "MCP_CLIENT_VERSION"],
    "Chat": ["A2A_DISPATCH_TIMEOUT", "V4_STREAM_TIMEOUT", "EXTERNAL_CHAT_TIMEOUT", "TITLE_MAX_LENGTH", "PREVIEW_MAX_LENGTH", "CONN_LOG_BODY_MAX", "SPEC_TEXT_MAX_CHARS"],
    "Agency health": ["AGENCY_CHAT_TIMEOUT", "AGENCY_CHAT_CONCURRENCY", "HEALTH_CHECK_INTERVAL_MINUTES", "CONNECTION_TEST_TIMEOUT"],
    "Executive summary": ["WEEKLY_BRIEF_CACHE_TTL_MINUTES", "WEEKLY_BRIEF_TIMEOUT"],
    "Analytics": ["AVG_LATENCY_WINDOW_DAYS", "FEEDBACK_TREND_DAYS", "BUSINESS_HOURS_START", "BUSINESS_HOURS_END"],
    "Embedding / similarity": ["EMBEDDING_API_URL", "EMBEDDING_API_KEY", "EMBEDDING_MODEL", "EMBEDDING_DIMENSIONS", "EMBEDDING_TIMEOUT", "SIMILARITY_THRESHOLD", "SIMILARITY_WINDOW_SECONDS", "SIMILARITY_FALLBACK"],
}

SECRET_FIELD_NAMES: set[str] = {
    "JWT_SECRET", "OPENROUTER_API_KEY", "PARSE_SPEC_API_KEY", "EMBEDDING_API_KEY",
}

settings = Settings()


async def load_settings_from_db() -> None:
    from app.models.setting import Setting as SettingModel
    rows = await SettingModel.all()
    overrides = {row.key: row.value for row in rows}
    settings.apply_overrides(overrides)

# Tortoise ORM config (used by aerich and register_tortoise)
TORTOISE_ORM = {
    "connections": {
        "default": settings.DATABASE_URL,
    },
    "apps": {
        "models": {
            "models": [
                "app.models",
                "aerich.models",
            ],
            "default_connection": "default",
        },
    }
}
