"""Email agency owners when their agency is auto-tripped into maintenance."""
import logging

from app.models import Agency, Relationship, User
from app.services.email import send_email as _real_send_email

logger = logging.getLogger(__name__)


async def _send_email(to: str, subject: str, body: str) -> None:
    await _real_send_email(to, subject, body)


async def notify_owners_maintenance(agency: Agency) -> None:
    owner_ids = await Relationship.filter(
        relation="owner", object_type="agency", object_id=agency.id
    ).values_list("subject_id", flat=True)
    owners = await User.filter(id__in=list(owner_ids), is_active=True)
    subject = f"[Thai Citizen Guide] {agency.name} ถูกปรับเป็นสถานะ maintenance"
    body = (
        f"ระบบตรวจพบความผิดพลาดต่อเนื่องจาก endpoint ของ {agency.name} "
        f"และปรับสถานะเป็น maintenance อัตโนมัติ\n"
        f"กรุณาตรวจสอบ endpoint และดูประวัติได้ที่หน้า My Agencies"
    )
    for o in owners:
        try:
            await _send_email(o.email, subject, body)
        except Exception:
            logger.exception("failed to notify owner %s", o.email)
