from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "popular_questions" (
    "id" UUID NOT NULL PRIMARY KEY,
    "text" TEXT NOT NULL,
    "text_key" VARCHAR(500) NOT NULL UNIQUE,
    "source" VARCHAR(10) NOT NULL DEFAULT 'manual',
    "pinned" BOOL NOT NULL DEFAULT False,
    "hidden" BOOL NOT NULL DEFAULT False,
    "sort_order" INT NOT NULL DEFAULT 0,
    "score" DOUBLE PRECISION,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "agency_id" UUID REFERENCES "agencies" ("id") ON DELETE SET NULL
);
COMMENT ON COLUMN "popular_questions"."source" IS 'seed: seed\nauto: auto\nmanual: manual';
COMMENT ON TABLE "popular_questions" IS 'A frequently-asked citizen question surfaced on the public chat landing page.';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "popular_questions";"""


MODELS_STATE = (
    "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"
    "Qb26intol2bRX3txpI/fX/KkpB2g=="
)
