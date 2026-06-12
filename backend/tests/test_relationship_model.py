import pytest
from tortoise.exceptions import IntegrityError

from app.models import Relationship


async def test_create_and_unique(db):
    args = dict(subject_type="user", subject_id="0" * 32, relation="owner",
                object_type="agency", object_id="1" * 32)
    await Relationship.create(**args)
    with pytest.raises(IntegrityError):
        await Relationship.create(**args)
