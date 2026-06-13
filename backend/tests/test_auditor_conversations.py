"""Auditor reads all conversations (full audit) but cannot delete them."""
import pytest

from app.auth.authz import authorize
from app.models.user import User
from app.models import Conversation


async def _conv_for(owner_id):
    return await Conversation.create(user_id=owner_id, title="t", status="active")


async def test_auditor_can_read_other_users_conversation(db):
    owner = await User.create(email="owner-c@x.com", hashed_password="h", role="user")
    auditor = await User.create(email="aud-c@x.com", hashed_password="h", role="auditor")
    conv = await _conv_for(owner.id)
    d = await authorize(auditor, "conversation:read", conv)
    assert d.allowed is True


async def test_auditor_cannot_delete_conversation(db):
    owner = await User.create(email="owner-d@x.com", hashed_password="h", role="user")
    auditor = await User.create(email="aud-d@x.com", hashed_password="h", role="auditor")
    conv = await _conv_for(owner.id)
    d = await authorize(auditor, "conversation:delete", conv)
    assert d.allowed is False


async def test_normal_user_cannot_read_others_conversation(db):
    owner = await User.create(email="owner-n@x.com", hashed_password="h", role="user")
    other = await User.create(email="other-n@x.com", hashed_password="h", role="user")
    conv = await _conv_for(owner.id)
    d = await authorize(other, "conversation:read", conv)
    assert d.allowed is False


async def test_list_conversations_auditor_sees_all(db):
    from app.routers.conversations import list_conversations
    owner = await User.create(email="owner-l@x.com", hashed_password="h", role="user")
    auditor = await User.create(email="aud-l@x.com", hashed_password="h", role="auditor")
    await _conv_for(owner.id)
    await _conv_for(owner.id)
    resp = await list_conversations(search="", filter_agency="", user=auditor)
    assert resp.total >= 2


async def test_list_conversations_user_sees_only_own(db):
    from app.routers.conversations import list_conversations
    owner = await User.create(email="owner-o@x.com", hashed_password="h", role="user")
    other = await User.create(email="other-o@x.com", hashed_password="h", role="user")
    await _conv_for(owner.id)
    resp = await list_conversations(search="", filter_agency="", user=other)
    assert resp.total == 0
