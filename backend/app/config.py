from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_NAME: str = "AI Chatbot Portal API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgres://postgres:postgres@localhost:5432/ai_chatbot"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"]

    # JWT authentication
    JWT_SECRET: str = "change-me-in-production-use-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7   # 7 days

    PARSE_SPEC_URL: str = "http://thaillm.or.th/api/openthaigpt/v1/chat/completions"
    PARSE_SPEC_API_KEY: str = ""
    PARSE_SPEC_TIMEOUT: int = 60
    PARSE_SPEC_LLM_MODEL: str = "/model"

    OPENROUTER_API_KEY: str = ""

    # Embedding service
    EMBEDDING_API_URL: str = "https://api.openai.com/v1/embeddings"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 384
    EMBEDDING_TIMEOUT: int = 5
    SIMILARITY_THRESHOLD: float = 0.95
    SIMILARITY_WINDOW_SECONDS: int = 259200  # 3 days in seconds
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
