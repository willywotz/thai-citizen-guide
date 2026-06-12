from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "agencies" ADD "auto_maintenance" BOOL NOT NULL DEFAULT FALSE;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "agencies" DROP COLUMN "auto_maintenance";"""
