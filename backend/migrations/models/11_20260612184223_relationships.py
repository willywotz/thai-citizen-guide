from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "relationships" (
    "id" UUID NOT NULL PRIMARY KEY,
    "subject_type" VARCHAR(20) NOT NULL,
    "subject_id" UUID NOT NULL,
    "relation" VARCHAR(30) NOT NULL,
    "object_type" VARCHAR(30) NOT NULL,
    "object_id" UUID NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "uid_relationshi_subject_5be248" UNIQUE ("subject_type", "subject_id", "relation", "object_type", "object_id")
);
        COMMENT ON COLUMN "agencies"."status" IS 'draft: draft
active: active
maintenance: maintenance
disabled: disabled';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        COMMENT ON COLUMN "agencies"."status" IS 'draft: draft
active: active
maintenance: maintenance
disabled: disabled
inactive: inactive';
        DROP TABLE IF EXISTS "relationships";"""


MODELS_STATE = (
    "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"
)
