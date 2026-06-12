"""Token/cost quota checks — raise QuotaExceeded before dispatching new LLM work."""
from tortoise.functions import Sum

from app.config import settings
from app.models import LlmUsage
from app.utils import now


class QuotaExceeded(Exception):
    pass


async def check_user_quota(user_id) -> None:
    limit = settings.USER_MONTHLY_TOKEN_QUOTA
    if not limit:
        return
    start = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    row = (
        await LlmUsage.filter(user_id=user_id, created_at__gte=start)
        .annotate(p=Sum("prompt_tokens"), c=Sum("completion_tokens"))
        .values("p", "c")
    )
    used = (row[0]["p"] or 0) + (row[0]["c"] or 0) if row else 0
    if used >= limit:
        raise QuotaExceeded(f"monthly token quota exceeded ({used}/{limit})")


async def check_global_budget() -> None:
    limit = settings.GLOBAL_DAILY_COST_LIMIT_USD
    if not limit:
        return
    start = now().replace(hour=0, minute=0, second=0, microsecond=0)
    row = await LlmUsage.filter(created_at__gte=start).annotate(s=Sum("cost_usd")).values("s")
    spent = (row[0]["s"] or 0.0) if row else 0.0
    if spent >= limit:
        raise QuotaExceeded(f"global daily budget exceeded (${spent:.4f}/${limit})")
