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
