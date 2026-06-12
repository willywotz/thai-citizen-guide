from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "golden_questions" (
    "id" UUID NOT NULL PRIMARY KEY,
    "question" TEXT NOT NULL,
    "expected_topics" JSONB NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "agency_id" UUID NOT NULL REFERENCES "agencies" ("id") ON DELETE CASCADE
);
        CREATE TABLE IF NOT EXISTS "eval_results" (
    "id" UUID NOT NULL PRIMARY KEY,
    "score" DOUBLE PRECISION NOT NULL,
    "answer" TEXT NOT NULL,
    "judge_reason" TEXT NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "golden_question_id" UUID NOT NULL REFERENCES "golden_questions" ("id") ON DELETE CASCADE
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "golden_questions";
        DROP TABLE IF EXISTS "eval_results";"""


MODELS_STATE = (
    "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"
    "inQYdf/w/Mvg9I"
)
