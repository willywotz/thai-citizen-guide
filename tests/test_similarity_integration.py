import pytest
from unittest.mock import AsyncMock, patch
from backend.app.services.similarity import find_similar_question
from backend.app.services.embedding import generate_embedding


@pytest.mark.asyncio
async def test_full_cache_flow_no_hit():
    """New query with no similar questions in DB returns None."""
    from backend.app.models.conversation import Message

    with patch("backend.app.services.similarity._vector_search", new_callable=AsyncMock) as mock_vector:
        mock_vector.return_value = None

        result = await find_similar_question(
            query="คำถามที่ไม่มีในระบบเลย",
            embedding=[0.1] * 384,
        )
        assert result is None


@pytest.mark.asyncio
async def test_embedding_generation_and_encoding():
    """Verify embedding is generated and can be encoded/decoded."""
    from backend.app.services.embedding import encode_embedding, decode_embedding

    vector = [0.1, 0.2, 0.3, -0.4]
    encoded = encode_embedding(vector)
    decoded = decode_embedding(encoded)
    assert decoded == vector
    assert len(decoded) == 4


@pytest.mark.asyncio
async def test_trigram_fallback_called_when_embedding_none():
    """When embedding is None, trigram search is used."""
    from backend.app.models.conversation import Message

    with patch("backend.app.services.similarity._trigram_search", new_callable=AsyncMock) as mock_trigram:
        with patch("backend.app.services.similarity._vector_search", new_callable=AsyncMock) as mock_vector:
            mock_trigram.return_value = None

            await find_similar_question(query="test", embedding=None)

            mock_trigram.assert_called_once()
            mock_vector.assert_not_called()