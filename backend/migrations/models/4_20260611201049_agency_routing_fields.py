from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "agencies" ADD "priority" INT;
        ALTER TABLE "agencies" ADD "dispatch_timeout_s" INT;
        ALTER TABLE "agencies" ADD "router_hint" TEXT NOT NULL DEFAULT '';
        ALTER TABLE "agencies" ADD "mcp_tool_name" VARCHAR(255);
        COMMENT ON COLUMN "agencies"."status" IS 'draft: draft
active: active
maintenance: maintenance
disabled: disabled
inactive: inactive';
        UPDATE "agencies" SET "status" = 'disabled' WHERE "status" = 'inactive';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        UPDATE "agencies" SET "status" = 'inactive' WHERE "status" = 'disabled';
        ALTER TABLE "agencies" DROP COLUMN "priority";
        ALTER TABLE "agencies" DROP COLUMN "dispatch_timeout_s";
        ALTER TABLE "agencies" DROP COLUMN "router_hint";
        ALTER TABLE "agencies" DROP COLUMN "mcp_tool_name";
        COMMENT ON COLUMN "agencies"."status" IS 'active: active
inactive: inactive';"""


MODELS_STATE = (
    "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"
    "RrcaV/Xjb/xDd3s="
)
