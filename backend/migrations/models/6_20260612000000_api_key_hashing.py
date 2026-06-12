from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "user_api_keys" ALTER COLUMN "key" DROP NOT NULL;
        ALTER TABLE "user_api_keys" ADD "key_hash" VARCHAR(64) UNIQUE;
        ALTER TABLE "user_api_keys" ADD "key_prefix" VARCHAR(16) NOT NULL DEFAULT '';
        ALTER TABLE "user_api_keys" ADD "last_used_at" TIMESTAMPTZ;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "user_api_keys" ALTER COLUMN "key" SET NOT NULL;
        ALTER TABLE "user_api_keys" DROP COLUMN "key_hash";
        ALTER TABLE "user_api_keys" DROP COLUMN "key_prefix";
        ALTER TABLE "user_api_keys" DROP COLUMN "last_used_at";"""
