import json
import logging
from datetime import datetime, timedelta, timezone

from tortoise import Tortoise

from app.config import settings
from app.models.conversation import Message, Conversation
from app.models.connection_log import ConnectionLog
from app.services.cache_flush import effective_cutoff
from app.services.embedding import encode_embedding
from app.utils import now

logger = logging.getLogger(__name__)


async def find_similar_question(
    query: str,
    embedding: list[float] | None = None,
) -> tuple[Message, Message, ConnectionLog] | None:
    """Find a similar question within SIMILARITY_WINDOW_SECONDS.

    Uses pgvector cosine similarity if embedding is provided.
    Falls back to text similarity if embedding is None.
    Controlled by SIMILARITY_FALLBACK setting: "similarity", "levenshtein", or "both".

    Returns (user_message, assistant_message, connection_log) if a match is found above threshold,
    None otherwise.
    """
    threshold = settings.SIMILARITY_THRESHOLD
    cutoff = await effective_cutoff(now() - timedelta(seconds=settings.SIMILARITY_WINDOW_SECONDS))

    if embedding is not None:
        match = await _vector_search(query, embedding, threshold, cutoff)
    else:
        match = await _text_fallback_search(query, threshold, cutoff)

    if match is None:
        return None

    # Find the assistant answer for the matched question
    try:
        assistant_msg = await Message.get(
            parent_id=match.id,
            role="assistant",
        )
    except Exception:
        logger.info(f"No assistant answer found for message {match.id}")
        return None

    # Only return answers from successful conversations
    try:
        conv = await Conversation.get(id=match.conversation_id)
        if conv.status != "success":
            logger.info(f"Skipping cached answer from non-success conversation {conv.id}")
            return None
    except Exception:
        logger.warning(f"Conversation {match.conversation_id} not found")
        return None

    try:
        conn_log = await ConnectionLog.get(assistant_message_id=assistant_msg.id)
    except Exception:
        logger.warning(f"ConnectionLog for message {assistant_msg.id} not found")
        return None

    return (match, assistant_msg, conn_log)


async def _text_fallback_search(
    query: str,
    threshold: float,
    cutoff,
) -> Message | None:
    """Try text similarity methods based on SIMILARITY_FALLBACK config."""
    fallback = settings.SIMILARITY_FALLBACK

    if fallback in ("similarity", "both"):
        match = await _similarity_search(query, threshold, cutoff)
        if match is not None:
            return match

    if fallback in ("levenshtein", "both"):
        match = await _levenshtein_search(query, threshold, cutoff)
        if match is not None:
            return match

    return None


async def _vector_search(
    query: str,
    embedding: list[float],
    threshold: float,
    cutoff,
) -> Message | None:
    """Search for similar questions using pgvector cosine distance."""
    threshold_distance = 1 - threshold  # cosine distance = 1 - cosine similarity
    embedding_json = encode_embedding(embedding)
    # Dimension must match idx_messages_embedding_cosine index expression ((embedding)::vector(384)).
    # Postgres treats ::vector and ::vector(384) as different expressions; a mismatch causes a seq scan.
    dim = settings.EMBEDDING_DIMENSIONS

    conn = Tortoise.get_connection("default")
    rows = await conn.execute_query_dict(
        f"""
        SELECT id, content, conversation_id, embedding
        FROM messages
        WHERE role = 'user'
          AND created_at >= $1
          AND embedding IS NOT NULL
          AND (embedding::vector({dim}) <=> $2::vector({dim})) < $3
        ORDER BY (embedding::vector({dim}) <=> $4::vector({dim}))
        LIMIT 1
        """,
        [cutoff, embedding_json, threshold_distance, embedding_json],
    )

    if not rows:
        return None

    row = rows[0]
    return await Message.get(id=row["id"])

async def _similarity_search(
    query: str,
    threshold: float,
    cutoff,
) -> Message | None:
    """Search for similar questions using pg_trgm text similarity."""
    conn = Tortoise.get_connection("default")
    try:
        rows = await conn.execute_query_dict(
            """
            SELECT id, content, conversation_id, similarity(content, $1) AS sim_score
            FROM messages
            WHERE role = 'user'
              AND created_at >= $2
              AND similarity(content, $3) >= $4
            ORDER BY similarity(content, $5) DESC
            LIMIT 1
            """,
            [query, cutoff, query, threshold, query],
        )
    except Exception:
        logger.warning("pg_trgm similarity search unavailable — extension not installed?")
        return None

    if not rows:
        return None

    row = rows[0]
    return await Message.get(id=row["id"])

async def _levenshtein_search(
    query: str,
    threshold: float,
    cutoff,
) -> Message | None:
    """Search for similar questions using Levenshtein distance.

    threshold=0.95 means max_distance = floor(len(query) * (1 - 0.95)).
    E.g. a 50-char query allows max 2 edits.
    """
    max_distance = max(1, int(len(query) * (1 - threshold)))

    conn = Tortoise.get_connection("default")
    try:
        rows = await conn.execute_query_dict(
            """
            SELECT id, content, conversation_id, levenshtein(content, $1) AS dist
            FROM messages
            WHERE role = 'user'
              AND created_at >= $2
              AND levenshtein(content, $3) <= $4
            ORDER BY levenshtein(content, $5) ASC
            LIMIT 1
            """,
            [query, cutoff, query, max_distance, query],
        )
    except Exception:
        logger.warning("fuzzystrmatch levenshtein search unavailable — extension not installed?")
        return None

    if not rows:
        return None

    row = rows[0]
    return await Message.get(id=row["id"])
