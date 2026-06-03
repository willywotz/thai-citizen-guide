from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE "settings" (
            "key" VARCHAR(100) NOT NULL PRIMARY KEY,
            "value" TEXT NOT NULL,
            "field_type" VARCHAR(20) NOT NULL DEFAULT 'str',
            "group" VARCHAR(50) NOT NULL,
            "is_secret" BOOL NOT NULL DEFAULT FALSE,
            "updated_at" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            "updated_by" VARCHAR(255)
        );"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "settings";"""
