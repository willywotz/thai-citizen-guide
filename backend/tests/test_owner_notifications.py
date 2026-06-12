from app.auth.authz import grant
from app.models import Agency, User
from app.services import owner_notify


async def test_notifies_each_owner_once(db, monkeypatch):
    sent: list[tuple[str, str]] = []

    async def fake_send(to: str, subject: str, body: str) -> None:
        sent.append((to, subject))

    monkeypatch.setattr(owner_notify, "_send_email", fake_send)
    ag = await Agency.create(name="A", status="maintenance", auto_maintenance=True)
    owner = await User.create(email="o@x.com", hashed_password="h", role="agency_owner")
    await grant(owner.id, "owner", "agency", ag.id)

    await owner_notify.notify_owners_maintenance(ag)

    assert sent == [("o@x.com", f"[Thai Citizen Guide] {ag.name} ถูกปรับเป็นสถานะ maintenance")]
