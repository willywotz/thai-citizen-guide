import pytest

from app.auth.authz import grant, has_relation
from app.models import Agency, User
from app.routers.agencies import add_agency_owner, list_my_agencies


@pytest.mark.asyncio
async def test_add_owner_creates_tuple(db):
    admin = await User.create(email="a@x.com", hashed_password="h", role="admin")
    owner = await User.create(email="o@x.com", hashed_password="h", role="agency_owner")
    ag = await Agency.create(name="A", status="draft")

    await add_agency_owner(str(ag.id), body=type("B", (), {"user_id": str(owner.id)})(), user=admin)

    assert await has_relation(owner.id, "owner", "agency", ag.id)


@pytest.mark.asyncio
async def test_list_my_agencies_scoped(db):
    owner = await User.create(email="o2@x.com", hashed_password="h", role="agency_owner")
    mine = await Agency.create(name="Mine", status="draft")
    await Agency.create(name="NotMine", status="draft")
    await grant(owner.id, "owner", "agency", mine.id)

    result = await list_my_agencies(user=owner)

    assert [a.name for a in result] == ["Mine"]
