from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@/postgres"

    class Config:
        env_file = ".env"

settings = Settings()
