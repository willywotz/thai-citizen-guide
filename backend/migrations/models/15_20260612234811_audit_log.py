from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "audit_logs" (
    "id" UUID NOT NULL PRIMARY KEY,
    "actor_id" UUID,
    "actor_email" VARCHAR(255),
    "action" VARCHAR(50) NOT NULL,
    "object_type" VARCHAR(30),
    "object_id" VARCHAR(64),
    "detail" JSONB,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "audit_logs";"""


MODELS_STATE = (
    "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"
    "wGVgrRyjtUxGKWJM+O4jotrcVW5vF1xiA4Z3o4LCmmRnx69dGuXaLW7thQelC1/e045N8j"
    "pWdOaoo0zXTIipGWHanBjJzBex7ZMRG0oD8JH5Amdr0sAdeIO70U+wZXlna82RmiKlwOe5"
    "oKzc82mme6mCB/RuZPDWwnMpPKcGxdydyQar7MlkbRVOUM0LPHlDYE05xECBAYIAW4j3v8"
    "h5YwBj7k71bO4PNRANDPzmGT4kLhKHfgeiTuiBXVKcxjpGdb15a3nxdu5tqsVyYh+Iyf1x"
    "OjSmMRuxQbfrYL44q0DjxVkhi7wqT6JP4DN616VxgWrHYVJ1H3zkAJFldCWzQMZ2pvuOTf"
    "fIjbJCV2aRXUfuuCMJfMUvK32TWWTXkbvuSK7LOchF1CS+m+/M4tw2OeChJrfp3JH74LVS"
    "uCN3tWe8WZHOq28a3+425wZ5bI4q7nPe8cnIA0iQNe0p/D5RzVGZzwcs2jTmYJzC2Ur5TS"
    "pmqKj3dhr7tJH5qWTbBiSB5jbPFKRzlKS80lrbC6Lm7SSwlvODCpMJF2dUK04mvLWkq7VN"
    "tBvLnrbTQOqv/wfDUIKF"
)
