from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "llm_providers" (
    "id" UUID NOT NULL PRIMARY KEY,
    "name" VARCHAR(50) NOT NULL UNIQUE,
    "base_url" VARCHAR(500) NOT NULL,
    "api_key" TEXT NOT NULL,
    "auth_header" VARCHAR(100) NOT NULL DEFAULT 'Authorization',
    "auth_scheme" VARCHAR(50) NOT NULL DEFAULT 'Bearer',
    "timeout_seconds" DOUBLE PRECISION NOT NULL DEFAULT 60,
    "request_usage" BOOL NOT NULL DEFAULT False,
    "rate_limit_rps" INT,
    "rate_limit_rpm" INT,
    "max_queue_size" INT NOT NULL DEFAULT 50,
    "enabled" BOOL NOT NULL DEFAULT True,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
        CREATE TABLE IF NOT EXISTS "llm_routes" (
    "id" UUID NOT NULL PRIMARY KEY,
    "purpose" VARCHAR(50) NOT NULL UNIQUE,
    "model" VARCHAR(200) NOT NULL,
    "timeout_override" DOUBLE PRECISION,
    "enabled" BOOL NOT NULL DEFAULT True,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "provider_id" UUID NOT NULL REFERENCES "llm_providers" ("id") ON DELETE RESTRICT
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "llm_routes";
        DROP TABLE IF EXISTS "llm_providers";"""


MODELS_STATE = (
    "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"
    "UIbW2iXVutr60GUn/5P/zJfZg="
)
