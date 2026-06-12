"""Trip agencies into auto-maintenance after N consecutive live-dispatch failures.

Recovery reuses the existing health-probe reconcile loop
(app/services/agency_reconcile.py): once an agency's error rate drops below 50%
over >= 5 health checks and its auto_maintenance flag is True, reconcile_statuses
re-activates the agency and clears auto_maintenance.
"""
import logging
from collections import defaultdict

from app.config import settings
from app.models import Agency
from app.services.owner_notify import notify_owners_maintenance

logger = logging.getLogger(__name__)
_consecutive_failures: dict[str, int] = defaultdict(int)


async def record_dispatch_result(agency_id: str, *, success: bool) -> None:
    if success:
        _consecutive_failures.pop(agency_id, None)
        return
    _consecutive_failures[agency_id] += 1
    if _consecutive_failures[agency_id] < settings.BREAKER_FAILURE_THRESHOLD:
        return
    updated = await Agency.filter(id=agency_id, status="active").update(
        status="maintenance", auto_maintenance=True
    )
    if updated:
        logger.warning("circuit breaker tripped agency %s into maintenance", agency_id)
        try:
            agency = await Agency.get(id=agency_id)
            await notify_owners_maintenance(agency)
        except Exception:
            logger.exception("failed to notify owners for agency %s", agency_id)
    _consecutive_failures.pop(agency_id, None)
