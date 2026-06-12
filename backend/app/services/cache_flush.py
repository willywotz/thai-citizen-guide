"""Similarity-cache invalidation via a stored flush timestamp.

find_similar_question ignores any cached Q/A created before the last flush.
"""
from datetime import datetime

from app.models.setting import Setting
from app.utils import now

_KEY = "SIMILARITY_CACHE_FLUSHED_AT"


async def flush_similarity_cache() -> None:
    await Setting.update_or_create(
        defaults={"value": now().isoformat(), "field_type": "str", "group": "Cache"},
        key=_KEY,
    )


async def effective_cutoff(window_cutoff: datetime) -> datetime:
    row = await Setting.filter(key=_KEY).first()
    if row is None:
        return window_cutoff
    flushed_at = datetime.fromisoformat(row.value)
    return max(window_cutoff, flushed_at)
