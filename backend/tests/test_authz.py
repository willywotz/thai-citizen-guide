from app.auth.authz import authorize, grant
from app.models import Agency, User
from app.models.conversation import Conversation


async def _user(role="user", email="u@x.com"):
    return await User.create(email=email, hashed_password="h", role=role)


async def test_admin_allows_everything(db):
    admin = await _user("admin", "a@x.com")
    ag = await Agency.create(name="A", status="active")
    for action in ("agency:edit", "agency:change_status", "settings:edit", "user:manage"):
        assert (await authorize(admin, action, ag)).allowed


async def test_plain_user_cannot_edit_agency(db):
    u = await _user()
    ag = await Agency.create(name="A", status="draft")
    d = await authorize(u, "agency:edit", ag)
    assert not d.allowed and d.layer == "rebac"


async def test_owner_edits_draft_agency(db):
    u = await _user("agency_owner", "o@x.com")
    ag = await Agency.create(name="A", status="draft")
    await grant(u.id, "owner", "agency", ag.id)
    assert (await authorize(u, "agency:edit", ag)).allowed


async def test_abac_blocks_owner_editing_active_agency(db):
    u = await _user("agency_owner", "o2@x.com")
    ag = await Agency.create(name="A", status="active")
    await grant(u.id, "owner", "agency", ag.id)
    d = await authorize(u, "agency:edit", ag)
    assert not d.allowed and d.layer == "abac"


async def test_owner_cannot_change_status(db):
    u = await _user("agency_owner", "o3@x.com")
    ag = await Agency.create(name="A", status="draft")
    await grant(u.id, "owner", "agency", ag.id)
    assert not (await authorize(u, "agency:change_status", ag)).allowed


async def test_conversation_owner_reads_own_only(db):
    u1, u2 = await _user(email="c1@x.com"), await _user(email="c2@x.com")
    conv = await Conversation.create(title="t", user_id=u1.id)
    assert (await authorize(u1, "conversation:read", conv)).allowed
    assert not (await authorize(u2, "conversation:read", conv)).allowed


async def test_inactive_user_denied_everywhere(db):
    u = await _user(email="i@x.com")
    u.is_active = False
    conv = await Conversation.create(title="t", user_id=u.id)
    d = await authorize(u, "conversation:read", conv)
    assert not d.allowed and d.layer == "abac"
