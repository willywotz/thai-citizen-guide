from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "user_api_keys" ADD "key_hash" VARCHAR(64) UNIQUE;
        ALTER TABLE "user_api_keys" ADD "key_prefix" VARCHAR(16) NOT NULL DEFAULT '';
        ALTER TABLE "user_api_keys" ADD "last_used_at" TIMESTAMPTZ;
        ALTER TABLE "user_api_keys" ALTER COLUMN "key" DROP NOT NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS "uid_user_api_ke_key_has_935e25";
        ALTER TABLE "user_api_keys" DROP COLUMN "key_hash";
        ALTER TABLE "user_api_keys" DROP COLUMN "key_prefix";
        ALTER TABLE "user_api_keys" DROP COLUMN "last_used_at";
        ALTER TABLE "user_api_keys" ALTER COLUMN "key" SET NOT NULL;"""


MODELS_STATE = (
    "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"
)
