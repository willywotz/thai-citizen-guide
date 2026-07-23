from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE EXTENSION IF NOT EXISTS pg_trgm;
        DROP INDEX IF EXISTS idx_messages_embedding_cosine;
        ALTER TABLE "messages" DROP COLUMN "embedding";
        """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "messages" ADD "embedding" VARCHAR(50000);
        CREATE INDEX IF NOT EXISTS idx_messages_embedding_cosine
        ON messages USING hnsw (((embedding)::vector(384)) vector_cosine_ops)
        WHERE role = 'user' AND embedding IS NOT NULL;
        DROP EXTENSION IF EXISTS pg_trgm;
        """


MODELS_STATE = (
    "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"
)
