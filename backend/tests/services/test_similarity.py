from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_FIXED_CUTOFF = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _patch_cutoff(similarity):
    return patch.object(
        similarity, "effective_cutoff", new=AsyncMock(return_value=_FIXED_CUTOFF)
    )


@pytest.mark.asyncio
async def test_find_similar_returns_none_when_cache_disabled():
    from app.config import settings
    from app.services import similarity

    with patch.object(settings, "SIMILARITY_CACHE_ENABLED", False), \
         patch.object(similarity, "_similarity_search", new=AsyncMock()) as msearch:
        result = await similarity.find_similar_question("q")

    assert result is None
    msearch.assert_not_awaited()


@pytest.mark.asyncio
async def test_find_similar_uses_pg_trgm_similarity_search():
    from app.services import similarity

    match_msg = MagicMock(id="m1", conversation_id="c1")
    assistant = MagicMock(id="a1")
    conn_log = MagicMock()

    with _patch_cutoff(similarity), \
         patch.object(similarity, "_similarity_search", new=AsyncMock(return_value=match_msg)) as msearch, \
         patch.object(similarity, "_fetch_answer_by_match",
                      new=AsyncMock(return_value=(assistant, conn_log))):
        result = await similarity.find_similar_question("q")

    msearch.assert_awaited_once()
    assert result == (match_msg, assistant, conn_log)


@pytest.mark.asyncio
async def test_find_similar_returns_none_when_no_match():
    from app.services import similarity

    with _patch_cutoff(similarity), \
         patch.object(similarity, "_similarity_search", new=AsyncMock(return_value=None)):
        result = await similarity.find_similar_question("q")

    assert result is None


@pytest.mark.asyncio
async def test_find_similar_returns_none_when_answer_unresolvable():
    from app.services import similarity

    match_msg = MagicMock(id="m1", conversation_id="c1")
    with _patch_cutoff(similarity), \
         patch.object(similarity, "_similarity_search", new=AsyncMock(return_value=match_msg)), \
         patch.object(similarity, "_fetch_answer_by_match", new=AsyncMock(return_value=None)):
        result = await similarity.find_similar_question("q")

    assert result is None


@pytest.mark.asyncio
async def test_similarity_search_returns_none_on_extension_error():
    from app.services import similarity

    mock_conn = MagicMock()
    mock_conn.execute_query_dict = AsyncMock(side_effect=Exception("function similarity does not exist"))

    with patch.object(similarity.Tortoise, "get_connection", return_value=mock_conn):
        result = await similarity._similarity_search("hello world", 0.95, None)

    assert result is None
