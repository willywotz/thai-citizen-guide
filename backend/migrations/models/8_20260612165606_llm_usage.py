from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "llm_usage" (
    "id" UUID NOT NULL PRIMARY KEY,
    "model" VARCHAR(100) NOT NULL,
    "purpose" VARCHAR(30) NOT NULL,
    "prompt_tokens" INT NOT NULL DEFAULT 0,
    "completion_tokens" INT NOT NULL DEFAULT 0,
    "cost_usd" DOUBLE PRECISION,
    "user_id" UUID,
    "agency_id" UUID,
    "conversation_id" UUID,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "llm_usage";"""


MODELS_STATE = (
    "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"
)
