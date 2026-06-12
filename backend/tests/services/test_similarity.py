from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_FIXED_CUTOFF = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _patch_cutoff(similarity):
    return patch.object(
        similarity,
        "effective_cutoff",
        new=AsyncMock(return_value=_FIXED_CUTOFF),
    )


@pytest.mark.asyncio
async def test_find_similar_uses_vector_search_when_embedding_present():
    from app.services import similarity

    match_msg = MagicMock(id="m1", conversation_id="c1")
    assistant = MagicMock(id="a1")
    conv = MagicMock(id="c1", status="success")
    conn_log = MagicMock()

    with _patch_cutoff(similarity), \
         patch.object(similarity, "_vector_search", new=AsyncMock(return_value=match_msg)) as mvec, \
         patch.object(similarity, "_text_fallback_search", new=AsyncMock()) as mtext, \
         patch.object(similarity, "Message") as MockMessage, \
         patch.object(similarity, "Conversation") as MockConv, \
         patch.object(similarity, "ConnectionLog") as MockCL:
        MockMessage.get = AsyncMock(return_value=assistant)
        MockConv.get = AsyncMock(return_value=conv)
        MockCL.get = AsyncMock(return_value=conn_log)
        result = await similarity.find_similar_question("q", embedding=[0.1, 0.2])

    mvec.assert_awaited_once()
    mtext.assert_not_awaited()
    assert result == (match_msg, assistant, conn_log)


@pytest.mark.asyncio
async def test_find_similar_uses_text_fallback_when_no_embedding():
    from app.services import similarity

    with _patch_cutoff(similarity), \
         patch.object(similarity, "_vector_search", new=AsyncMock()) as mvec, \
         patch.object(similarity, "_text_fallback_search", new=AsyncMock(return_value=None)) as mtext, \
         patch.object(similarity, "Message"), \
         patch.object(similarity, "Conversation"), \
         patch.object(similarity, "ConnectionLog"):
        result = await similarity.find_similar_question("q", embedding=None)

    mtext.assert_awaited_once()
    mvec.assert_not_awaited()
    assert result is None


@pytest.mark.asyncio
async def test_find_similar_returns_none_when_no_assistant():
    from app.services import similarity

    match_msg = MagicMock(id="m1", conversation_id="c1")
    with _patch_cutoff(similarity), \
         patch.object(similarity, "_vector_search", new=AsyncMock(return_value=match_msg)), \
         patch.object(similarity, "Message") as MockMessage, \
         patch.object(similarity, "Conversation"), \
         patch.object(similarity, "ConnectionLog"):
        MockMessage.get = AsyncMock(side_effect=Exception("not found"))
        result = await similarity.find_similar_question("q", embedding=[0.1])

    assert result is None


@pytest.mark.asyncio
async def test_find_similar_returns_none_when_conversation_not_success():
    from app.services import similarity

    match_msg = MagicMock(id="m1", conversation_id="c1")
    assistant = MagicMock(id="a1")
    conv = MagicMock(id="c1", status="error")
    with _patch_cutoff(similarity), \
         patch.object(similarity, "_vector_search", new=AsyncMock(return_value=match_msg)), \
         patch.object(similarity, "Message") as MockMessage, \
         patch.object(similarity, "Conversation") as MockConv, \
         patch.object(similarity, "ConnectionLog"):
        MockMessage.get = AsyncMock(return_value=assistant)
        MockConv.get = AsyncMock(return_value=conv)
        result = await similarity.find_similar_question("q", embedding=[0.1])

    assert result is None


@pytest.mark.asyncio
async def test_find_similar_returns_none_when_conn_log_missing():
    from app.services import similarity

    match_msg = MagicMock(id="m1", conversation_id="c1")
    assistant = MagicMock(id="a1")
    conv = MagicMock(id="c1", status="success")
    with _patch_cutoff(similarity), \
         patch.object(similarity, "_vector_search", new=AsyncMock(return_value=match_msg)), \
         patch.object(similarity, "Message") as MockMessage, \
         patch.object(similarity, "Conversation") as MockConv, \
         patch.object(similarity, "ConnectionLog") as MockCL:
        MockMessage.get = AsyncMock(return_value=assistant)
        MockConv.get = AsyncMock(return_value=conv)
        MockCL.get = AsyncMock(side_effect=Exception("not found"))
        result = await similarity.find_similar_question("q", embedding=[0.1])

    assert result is None


@pytest.mark.asyncio
async def test_text_fallback_similarity_only():
    from app.config import settings
    from app.services import similarity

    sentinel = MagicMock()
    with patch.object(settings, "SIMILARITY_FALLBACK", "similarity"), \
         patch.object(similarity, "_similarity_search", new=AsyncMock(return_value=sentinel)) as msim, \
         patch.object(similarity, "_levenshtein_search", new=AsyncMock()) as mlev:
        result = await similarity._text_fallback_search("q", 0.9, None)

    assert result is sentinel
    msim.assert_awaited_once()
    mlev.assert_not_awaited()


@pytest.mark.asyncio
async def test_text_fallback_both_falls_through_to_levenshtein():
    from app.config import settings
    from app.services import similarity

    sentinel = MagicMock()
    with patch.object(settings, "SIMILARITY_FALLBACK", "both"), \
         patch.object(similarity, "_similarity_search", new=AsyncMock(return_value=None)) as msim, \
         patch.object(similarity, "_levenshtein_search", new=AsyncMock(return_value=sentinel)) as mlev:
        result = await similarity._text_fallback_search("q", 0.9, None)

    assert result is sentinel
    msim.assert_awaited_once()
    mlev.assert_awaited_once()


@pytest.mark.asyncio
async def test_levenshtein_search_computes_max_distance():
    from app.services import similarity

    mock_conn = MagicMock()
    mock_conn.execute_query_dict = AsyncMock(return_value=[])
    query = "x" * 100  # max(1, int(100 * (1 - 0.95))) == 5

    with patch.object(similarity.Tortoise, "get_connection", return_value=mock_conn):
        result = await similarity._levenshtein_search(query, 0.95, None)

    assert result is None
    params = mock_conn.execute_query_dict.call_args[0][1]
    # params = [query, cutoff, query, max_distance, query]; index 3 is max_distance
    assert params[3] == 5


@pytest.mark.asyncio
async def test_levenshtein_search_returns_none_on_extension_error():
    from app.services import similarity

    mock_conn = MagicMock()
    mock_conn.execute_query_dict = AsyncMock(side_effect=Exception("function levenshtein does not exist"))

    with patch.object(similarity.Tortoise, "get_connection", return_value=mock_conn):
        result = await similarity._levenshtein_search("hello world", 0.95, None)

    assert result is None


@pytest.mark.asyncio
async def test_text_fallback_levenshtein_only():
    from app.config import settings
    from app.services import similarity

    sentinel = MagicMock()
    with patch.object(settings, "SIMILARITY_FALLBACK", "levenshtein"), \
         patch.object(similarity, "_similarity_search", new=AsyncMock()) as msim, \
         patch.object(similarity, "_levenshtein_search", new=AsyncMock(return_value=sentinel)) as mlev:
        result = await similarity._text_fallback_search("q", 0.9, None)

    assert result is sentinel
    mlev.assert_awaited_once()
    msim.assert_not_awaited()


@pytest.mark.asyncio
async def test_text_fallback_both_short_circuits_on_similarity_hit():
    from app.config import settings
    from app.services import similarity

    sentinel = MagicMock()
    with patch.object(settings, "SIMILARITY_FALLBACK", "both"), \
         patch.object(similarity, "_similarity_search", new=AsyncMock(return_value=sentinel)) as msim, \
         patch.object(similarity, "_levenshtein_search", new=AsyncMock()) as mlev:
        result = await similarity._text_fallback_search("q", 0.9, None)

    assert result is sentinel
    msim.assert_awaited_once()
    mlev.assert_not_awaited()
