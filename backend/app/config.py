from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "AI Chatbot Portal API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    TIMEZONE: str = "Asia/Bangkok"
    USER_AGENT_PREFIX: str = "AI-Chatbot-Portal/1.0"

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgres://postgres:postgres@localhost:5432/ai_chatbot"

    # ── CORS ─────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"]

    # ── Auth ─────────────────────────────────────────────────────────────────
    JWT_SECRET: str = "change-me-in-production-use-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    MIN_PASSWORD_LENGTH: int = 6
    RESET_TOKEN_EXPIRE_HOURS: int = 1
    RESET_TOKEN_BYTES: int = 32

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


settings = Settings()

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