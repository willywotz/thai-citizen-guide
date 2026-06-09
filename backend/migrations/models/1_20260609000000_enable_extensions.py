from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = False


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE EXTENSION IF NOT EXISTS pg_trgm;
        CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP EXTENSION IF EXISTS pg_trgm;
        DROP EXTENSION IF EXISTS fuzzystrmatch;
    """
