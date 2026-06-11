from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "executive_briefs" (
    "id" UUID NOT NULL PRIMARY KEY,
    "content" TEXT NOT NULL,
    "status" VARCHAR(16) NOT NULL DEFAULT 'ok',
    "generated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "executive_briefs";"""


MODELS_STATE = (
    "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"
    "0Z3GVf34Gz3SuJk="
)
