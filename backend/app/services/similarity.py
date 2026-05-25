import json
import logging
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.models.conversation import Message, Conversation
from app.services.embedding import encode_embedding

logger = logging.getLogger(__name__)


async def find_similar_question(
    query: str,
    embedding: list[float] | None = None,
    threshold: float = 0.95,
    window_days: int = 3,
) -> tuple[Message, Message] | None:
    """Find a similar question from the last `window_days` days.

    Uses pgvector cosine similarity if embedding is provided,
    falls back to pg_trgm text similarity if embedding is None.

    Returns (user_message, assistant_message) if a match is found above threshold,
    None otherwise.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    if embedding is not None:
        match = await _vector_search(query, embedding, threshold, cutoff)
    else:
        match = await _trigram_search(query, threshold, cutoff)

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

    return (match, assistant_msg)


async def _vector_search(
    query: str,
    embedding: list[float],
    threshold: float,
    cutoff,
) -> Message | None:
    """Search for similar questions using pgvector cosine distance."""
    threshold_distance = 1 - threshold  # cosine distance = 1 - cosine similarity
    embedding_json = encode_embedding(embedding)

    # Use raw SQL with pgvector for cosine distance search
    # Tortoise ORM doesn't natively support vector operators, so we use raw SQL
    results = await Message.raw(
        """
        SELECT id, content, conversation_id, embedding
        FROM messages
        WHERE role = 'user'
          AND created_at >= %s
          AND embedding IS NOT NULL
          AND (embedding::vector <=> %s::vector) < %s
        ORDER BY (embedding::vector <=> %s::vector)
        LIMIT 1
        """,
        [cutoff, embedding_json, threshold_distance, embedding_json],
    )

    if not results:
        return None

    row = results[0]
    # Fetch the full ORM object
    return await Message.get(id=row["id"])


async def _trigram_search(
    query: str,
    threshold: float,
    cutoff,
) -> Message | None:
    """Search for similar questions using pg_trgm text similarity."""
    results = await Message.raw(
        """
        SELECT id, content, conversation_id, similarity(content, %s) AS sim_score
        FROM messages
        WHERE role = 'user'
          AND created_at >= %s
          AND similarity(content, %s) >= %s
        ORDER BY similarity(content, %s) DESC
        LIMIT 1
        """,
        [query, cutoff, query, threshold, query],
    )

    if not results:
        return None

    row = results[0]
    return await Message.get(id=row["id"])