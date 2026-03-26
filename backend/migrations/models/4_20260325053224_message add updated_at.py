from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "messages" ADD "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "messages" DROP COLUMN "updated_at";"""


MODELS_STATE = (
    "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"
)
