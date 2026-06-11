from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


@pytest.mark.asyncio
async def test_generate_embedding_no_key_returns_none():
    from app.config import settings
    from app.services.embedding import generate_embedding

    with patch.object(settings, "EMBEDDING_API_KEY", ""):
        result = await generate_embedding("hello")
    assert result is None


@pytest.mark.asyncio
async def test_generate_embedding_success():
    from app.config import settings
    from app.services.embedding import generate_embedding

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    with patch.object(settings, "EMBEDDING_API_KEY", "key"), \
         patch("app.services.embedding.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await generate_embedding("hello")

    assert result == [0.1, 0.2, 0.3]
    call = mock_client.post.call_args
    assert call.kwargs["headers"]["Authorization"] == "Bearer key"
    assert call.kwargs["json"]["input"] == "hello"


@pytest.mark.asyncio
async def test_generate_embedding_non_200_retries_three_times():
    from app.config import settings
    from app.services.embedding import generate_embedding

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "err"  # consumed only by the logger on non-200

    with patch.object(settings, "EMBEDDING_API_KEY", "key"), \
         patch("app.services.embedding.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await generate_embedding("hello")

    assert result is None
    assert mock_client.post.await_count == 3
    assert MockClient.call_count == 3


@pytest.mark.asyncio
async def test_generate_embedding_timeout_retries_three_times():
    from app.config import settings
    from app.services.embedding import generate_embedding

    with patch.object(settings, "EMBEDDING_API_KEY", "key"), \
         patch("app.services.embedding.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await generate_embedding("hello")

    assert result is None
    assert mock_client.post.await_count == 3
    assert MockClient.call_count == 3


@pytest.mark.asyncio
async def test_generate_embedding_connect_error_retries_three_times():
    from app.config import settings
    from app.services.embedding import generate_embedding

    with patch.object(settings, "EMBEDDING_API_KEY", "key"), \
         patch("app.services.embedding.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await generate_embedding("hello")

    assert result is None
    assert mock_client.post.await_count == 3
    assert MockClient.call_count == 3


def test_encode_embedding_returns_json_string():
    from app.services.embedding import encode_embedding

    assert encode_embedding([1.0, 2.0]) == "[1.0, 2.0]"


def test_encode_decode_roundtrip():
    from app.services.embedding import decode_embedding, encode_embedding

    vec = [0.1, 0.2, 0.3]
    assert decode_embedding(encode_embedding(vec)) == vec
