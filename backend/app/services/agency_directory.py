"""In-process cached snapshot of active agencies for the chat router prompt.

Invalidated on any agency create/update/delete/status-change (same hooks that
flush the similarity cache). Falls back to a fresh query when the cache is cold
or its TTL has elapsed.
"""
import time

from app.models.agency import Agency

_CACHE_TTL_S = 60.0
_cache: list[dict] | None = None
_loaded_at = 0.0


def invalidate() -> None:
    global _cache, _loaded_at
    _cache = None
    _loaded_at = 0.0


async def snapshot() -> list[dict]:
    global _cache, _loaded_at
    if _cache is not None and (time.monotonic() - _loaded_at) < _CACHE_TTL_S:
        return _cache
    _cache = await Agency.filter(status="active").all().values()
    _loaded_at = time.monotonic()
    return _cache


def prefilter(agencies: list[dict], query: str, *, max_n: int = 25) -> list[dict]:
    """Cheap keyword pre-filter on name/data_scope before prompt construction.

    Keeps agencies whose name/scope shares a token with the query; if that
    yields fewer than 3 (or nothing matches), fall back to the full list so the
    LLM still makes the final call. Caps the prompt at max_n agencies.
    """
    tokens = {t for t in query.lower().split() if len(t) >= 2}
    if not tokens:
        return agencies[:max_n]
    scored = []
    for ag in agencies:
        hay = (ag.get("name", "") + " " + " ".join(ag.get("data_scope") or [])).lower()
        if any(t in hay for t in tokens):
            scored.append(ag)
    if len(scored) < 3:
        return agencies[:max_n]
    return scored[:max_n]
