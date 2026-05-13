from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "messages" ADD "parent_id" UUID;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "messages" DROP COLUMN "parent_id";"""


MODELS_STATE = (
    "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"
    "rbQIrb/PTy42+VSLaW"
)
