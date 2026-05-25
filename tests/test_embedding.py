import pytest
from unittest.mock import AsyncMock, patch
from backend.app.services.embedding import generate_embedding


@pytest.mark.asyncio
async def test_generate_embedding_returns_vector():
    mock_response = {
        "data": [{"embedding": [0.1] * 384}],
        "model": "text-embedding-3-small",
        "usage": {"prompt_tokens": 5, "total_tokens": 5},
    }
    with patch("backend.app.services.embedding.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_client.post.return_value = mock_resp

        result = await generate_embedding("วิธีต่อทะเบียนบ้าน")
        assert result is not None
        assert len(result) == 384
        assert result[0] == 0.1


@pytest.mark.asyncio
async def test_generate_embedding_returns_none_on_failure():
    with patch("backend.app.services.embedding.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_resp = AsyncMock()
        mock_resp.status_code = 500
        mock_client.post.return_value = mock_resp

        result = await generate_embedding("test query")
        assert result is None