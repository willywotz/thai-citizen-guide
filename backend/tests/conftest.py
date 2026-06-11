"""
Shared pytest fixtures.

`db` spins up an in-memory SQLite database with the app's Tortoise models so
tests that exercise real queries (e.g. admin-count guardrails) run without a
live PostgreSQL instance. SQLite is sufficient: the User model uses only
portable field types (UUID/Char/Boolean/Datetime).
"""

import pytest_asyncio
from tortoise import Tortoise


@pytest_asyncio.fixture(scope="function")
async def db():
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["app.models"]},
    )
    await Tortoise.generate_schemas()
    try:
        yield
    finally:
        await Tortoise.close_connections()
