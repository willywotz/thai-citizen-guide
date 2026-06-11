from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.mark.asyncio
async def test_test_rest_missing_url():
    from app.services.agency import _test_rest

    agency = MagicMock()
    agency.endpoint_url = ""

    result = await _test_rest(agency)

    assert result["success"] is False
    assert "required" in result["error"].lower()


@pytest.mark.asyncio
async def test_test_connection_dispatches_by_type():
    from app.services.agency import test_connection

    agency = MagicMock()
    agency.endpoint_url = ""

    with patch("app.services.agency._test_rest", new_callable=AsyncMock) as mock_rest:
        mock_rest.return_value = {"success": True, "protocol": "REST API", "version": "v1", "steps": [], "latency": "5ms"}
        result = await test_connection("API", agency)

    mock_rest.assert_awaited_once_with(agency)
    assert result["protocol"] == "REST API"


@pytest.mark.asyncio
async def test_test_connection_unknown_type():
    from app.services.agency import test_connection

    agency = MagicMock()
    result = await test_connection("UNKNOWN", agency)

    assert result["success"] is False
    assert result["protocol"] == "UNKNOWN"


@pytest.mark.asyncio
async def test_parse_spec_raises_on_http_error():
    from app.services.agency import parse_spec
    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.headers = {"content-type": "application/json"}
    mock_response.text = "Rate limit exceeded"
    mock_response.is_error = True
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429", request=MagicMock(), response=mock_response
    )

    with patch("app.services.agency.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        with pytest.raises(httpx.HTTPStatusError):
            await parse_spec("some spec text")
