from aerich.models import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE EXTENSION IF NOT EXISTS pg_trgm;
        ALTER TABLE "messages" ADD COLUMN "embedding" TEXT;
        CREATE INDEX IF NOT EXISTS idx_messages_embedding_cosine ON "messages" USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
        CREATE INDEX IF NOT EXISTS idx_messages_content_trgm ON "messages" USING gin (content gin_trgm_ops);
        CREATE INDEX IF NOT EXISTS idx_messages_role_created ON "messages" (role, created_at) WHERE role = 'user';
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS idx_messages_role_created;
        DROP INDEX IF EXISTS idx_messages_content_trgm;
        DROP INDEX IF EXISTS idx_messages_embedding_cosine;
        ALTER TABLE "messages" DROP COLUMN "embedding";
    """