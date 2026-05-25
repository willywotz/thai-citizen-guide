import json
import logging
from backend.app.config import settings

import httpx

logger = logging.getLogger(__name__)


async def generate_embedding(text: str) -> list[float] | None:
    """Generate embedding vector for text via external API. Returns None on failure."""
    if not settings.EMBEDDING_API_KEY:
        logger.warning("EMBEDDING_API_KEY not configured, skipping embedding generation")
        return None

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
                    return data["data"][0]["embedding"]
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