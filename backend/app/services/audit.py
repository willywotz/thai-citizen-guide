"""Record audit-trail entries. Best-effort: a failed audit write must never break
the action being audited."""
import logging

from app.models import AuditLog

logger = logging.getLogger(__name__)


async def record_audit(actor, action: str, *, object_type=None, object_id=None, detail=None) -> None:
    try:
        await AuditLog.create(
            actor_id=getattr(actor, "id", None),
            actor_email=getattr(actor, "email", None),
            action=action,
            object_type=object_type,
            object_id=str(object_id) if object_id is not None else None,
            detail=detail,
        )
    except Exception:
        logger.exception("failed to record audit entry: %s", action)
