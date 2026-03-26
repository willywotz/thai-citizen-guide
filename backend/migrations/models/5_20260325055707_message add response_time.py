from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "messages" ADD "response_time" INT;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "messages" DROP COLUMN "response_time";"""


MODELS_STATE = (
    "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"
    "bLVsLp2P3t5en/qu3Mng=="
)
