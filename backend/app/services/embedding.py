import json
import logging
import time
from app.config import settings

import httpx

logger = logging.getLogger(__name__)

# TTL-based LRU cache for embedding results.
# Key: (model, dimensions, text) — fully qualified so different models/dims never collide.
# Value: (vector, inserted_at_monotonic).
# Max size caps memory; oldest entries are evicted on overflow.
_CACHE_TTL_SECONDS: float = 300.0  # 5 minutes
_CACHE_MAX_SIZE: int = 512
_embedding_cache: dict[tuple[str, int, str], tuple[list[float], float]] = {}

# NOTE: A module-level shared httpx.AsyncClient would avoid per-call TLS handshakes
# but is skipped here because it would require lifecycle management (aclose on shutdown)
# and makes test monkeypatching of httpx.AsyncClient more complex. The TTL cache already
# eliminates redundant network calls for repeated queries, which is the dominant win.


def _cache_clear() -> None:
    """Test hook: discard all cached entries."""
    _embedding_cache.clear()


def _cache_get(key: tuple[str, int, str]) -> list[float] | None:
    entry = _embedding_cache.get(key)
    if entry is None:
        return None
    vector, inserted_at = entry
    if time.monotonic() - inserted_at > _CACHE_TTL_SECONDS:
        del _embedding_cache[key]
        return None
    return vector


def _cache_set(key: tuple[str, int, str], vector: list[float]) -> None:
    if len(_embedding_cache) >= _CACHE_MAX_SIZE:
        # Evict the oldest entry to stay within the size bound.
        oldest_key = min(_embedding_cache, key=lambda k: _embedding_cache[k][1])
        del _embedding_cache[oldest_key]
    _embedding_cache[key] = (vector, time.monotonic())


async def generate_embedding(text: str) -> list[float] | None:
    """Generate embedding vector for text via external API. Returns None on failure."""
    if not settings.EMBEDDING_API_KEY:
        logger.warning("EMBEDDING_API_KEY not configured, skipping embedding generation")
        return None

    cache_key = (settings.EMBEDDING_MODEL, settings.EMBEDDING_DIMENSIONS, text)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    url = settings.EMBEDDING_API_URL
    headers = {
        "Authorization": f"Bearer {settings.EMBEDDING_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.EMBEDDING_MODEL,
        "input": text,
        "dimensions": settings.EMBEDDING_DIMENSIONS,
    }

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=settings.EMBEDDING_TIMEOUT) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    vector = data["data"][0]["embedding"]
                    _cache_set(cache_key, vector)
                    return vector
                logger.warning(f"Embedding API returned status {resp.status_code}: {resp.text[:200]}")
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            logger.warning(f"Embedding API attempt {attempt + 1} failed: {e}")

    logger.error("Embedding API failed after 3 attempts")
    return None


def encode_embedding(vector: list[float]) -> str:
    """Encode embedding vector to JSON string for storage."""
    return json.dumps(vector)


def decode_embedding(stored: str) -> list[float]:
    """Decode embedding vector from JSON string stored in DB."""
    return json.loads(stored)
