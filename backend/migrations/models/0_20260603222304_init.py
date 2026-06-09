from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "agencies" (
    "id" UUID NOT NULL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "short_name" VARCHAR(50),
    "logo" VARCHAR(20),
    "description" TEXT,
    "connection_type" VARCHAR(10) NOT NULL DEFAULT 'API',
    "status" VARCHAR(20) NOT NULL DEFAULT 'active',
    "data_scope" JSONB NOT NULL,
    "color" VARCHAR(50),
    "endpoint_url" VARCHAR(1000),
    "auth_method" VARCHAR(50),
    "auth_header" VARCHAR(100),
    "base_path" VARCHAR(255),
    "api_key_name" VARCHAR(100),
    "rate_limit_rpm" INT,
    "request_format" VARCHAR(50),
    "api_endpoints" JSONB NOT NULL,
    "response_schema" JSONB NOT NULL,
    "api_spec_raw" TEXT,
    "expected_payload" JSONB,
    "api_headers" JSONB,
    "total_calls" INT NOT NULL DEFAULT 0,
    "rating_up" INT NOT NULL DEFAULT 0,
    "rating_down" INT NOT NULL DEFAULT 0,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON COLUMN "agencies"."connection_type" IS 'MCP: MCP\nAPI: API\nA2A: A2A';
COMMENT ON COLUMN "agencies"."status" IS 'active: active\ninactive: inactive';
COMMENT ON TABLE "agencies" IS 'Government agency model.';
CREATE TABLE IF NOT EXISTS "connection_logs" (
    "id" UUID NOT NULL PRIMARY KEY,
    "action" VARCHAR(50) NOT NULL DEFAULT 'test',
    "connection_type" VARCHAR(20) NOT NULL,
    "status" VARCHAR(20) NOT NULL,
    "latency_ms" INT NOT NULL DEFAULT 0,
    "detail" TEXT NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "request_body" TEXT,
    "response_body" TEXT,
    "agency_id" UUID REFERENCES "agencies" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "settings" (
    "key" VARCHAR(100) NOT NULL PRIMARY KEY,
    "value" TEXT NOT NULL,
    "field_type" VARCHAR(20) NOT NULL DEFAULT 'str',
    "group" VARCHAR(50) NOT NULL,
    "is_secret" BOOL NOT NULL DEFAULT False,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_by" VARCHAR(255)
);
CREATE TABLE IF NOT EXISTS "users" (
    "id" UUID NOT NULL PRIMARY KEY,
    "email" VARCHAR(255) NOT NULL UNIQUE,
    "display_name" VARCHAR(255),
    "hashed_password" VARCHAR(500) NOT NULL,
    "role" VARCHAR(20) NOT NULL DEFAULT 'user',
    "avatar_url" VARCHAR(500),
    "is_active" BOOL NOT NULL DEFAULT True,
    "reset_token" VARCHAR(255),
    "reset_token_expires" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "users" IS 'Admin/user account for the AI Chatbot Portal.';
CREATE TABLE IF NOT EXISTS "conversations" (
    "id" UUID NOT NULL PRIMARY KEY,
    "title" VARCHAR(500) NOT NULL DEFAULT 'สนทนาใหม่',
    "preview" TEXT,
    "agencies" JSONB NOT NULL,
    "status" VARCHAR(20) NOT NULL DEFAULT 'success',
    "message_count" INT NOT NULL DEFAULT 0,
    "response_time" VARCHAR(50),
    "external_session_id" VARCHAR(100),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" UUID REFERENCES "users" ("id") ON DELETE SET NULL
);
COMMENT ON TABLE "conversations" IS 'Chat conversation — mirrors the `conversations` table from the original Supabase schema.';
CREATE TABLE IF NOT EXISTS "messages" (
    "id" UUID NOT NULL PRIMARY KEY,
    "parent_id" UUID,
    "role" VARCHAR(20) NOT NULL,
    "content" TEXT NOT NULL,
    "agent_steps" JSONB NOT NULL,
    "sources" JSONB NOT NULL,
    "rating" VARCHAR(10),
    "feedback_text" TEXT,
    "response_time" INT,
    "category" VARCHAR(50),
    "agency_ids" JSONB,
    "errors" JSONB,
    "embedding" VARCHAR(50000),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "conversation_id" UUID NOT NULL REFERENCES "conversations" ("id") ON DELETE CASCADE,
    "user_id" UUID REFERENCES "users" ("id") ON DELETE SET NULL
);
COMMENT ON TABLE "messages" IS 'Individual chat message within a conversation.';
CREATE TABLE IF NOT EXISTS "user_api_keys" (
    "id" UUID NOT NULL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "key" VARCHAR(255) NOT NULL UNIQUE,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "user_api_keys" IS 'API keys for users to access the AI Chatbot API.';
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
    "qh9/A/PGnVs="
)
