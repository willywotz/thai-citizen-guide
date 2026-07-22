"""Drop the ReBAC relationships table and collapse roles to user/admin.

IRREVERSIBLE. The former viewer/auditor/agency_owner assignments and the
agency-ownership tuples are not recoverable, so downgrade() is deliberately
empty rather than pretending to restore them. Accounts already marked admin
keep admin; every other account becomes a plain user and must be re-promoted
deliberately.
"""

from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "relationships";
        UPDATE users SET role = 'user' WHERE role NOT IN ('user', 'admin');"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
)
