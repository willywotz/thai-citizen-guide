import pytest
from tortoise import Tortoise
from backend.app.config import TORTOISE_ORM


@pytest.fixture(autouse=True)
async def init_db():
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()