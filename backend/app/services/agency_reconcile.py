"""Auto-transition agency status from 24h health.

active + error_rate > 50% (>=5 checks)            -> maintenance (auto-set)
rule-set maintenance + error_rate < 50% (>=5)     -> active
"""
import logging

from app.models import Agency
from app.services import agency_directory
from app.services.agency_health import error_window
from app.services.owner_notify import notify_owners_maintenance

logger = logging.getLogger(__name__)

_MIN_CHECKS = 5
_THRESHOLD = 50.0


async def reconcile_statuses() -> None:
    agencies = await Agency.filter(status__in=["active", "maintenance"])
    for ag in agencies:
        checks, failures = await error_window(ag.id)
        if checks < _MIN_CHECKS:
            continue
        error_rate = failures / checks * 100
        if ag.status == "active" and error_rate > _THRESHOLD:
            ag.status = "maintenance"
            ag.auto_maintenance = True
            await ag.save(update_fields=["status", "auto_maintenance", "updated_at"])
            agency_directory.invalidate()
            print(f"Auto-maintenance: {ag.name} error_rate={error_rate:.0f}%")
            try:
                await notify_owners_maintenance(ag)
            except Exception:
                logger.exception("failed to notify owners for agency %s", ag.id)
        elif ag.status == "maintenance" and ag.auto_maintenance and error_rate < _THRESHOLD:
            ag.status = "active"
            ag.auto_maintenance = False
            await ag.save(update_fields=["status", "auto_maintenance", "updated_at"])
            agency_directory.invalidate()
            print(f"Auto-reactivate: {ag.name} error_rate={error_rate:.0f}%")
