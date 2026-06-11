from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.models.user import User
from app.routers import agencies as r
from app.schemas.agency import McpDiscoverRequest


async def _admin():
    return await User.create(email="a@e.com", hashed_password="x", role="admin", is_active=True)


@pytest.mark.asyncio
async def test_mcp_discover_requires_endpoint_url(db):
    admin = await _admin()
    with pytest.raises(HTTPException) as exc:
        await r.mcp_discover(McpDiscoverRequest(endpoint_url=""), _=admin)
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_mcp_discover_returns_tools(db):
    admin = await _admin()
    fake = [{"name": "chat", "description": "d", "input_schema": {}}]
    with patch("app.routers.agencies.discover_tools", AsyncMock(return_value=fake)):
        res = await r.mcp_discover(McpDiscoverRequest(endpoint_url="https://mcp.example/sse"), _=admin)
    assert res.tools[0].name == "chat"


@pytest.mark.asyncio
async def test_mcp_discover_connection_error_502(db):
    admin = await _admin()
    with patch("app.routers.agencies.discover_tools", AsyncMock(side_effect=RuntimeError("boom"))):
        with pytest.raises(HTTPException) as exc:
            await r.mcp_discover(McpDiscoverRequest(endpoint_url="https://x"), _=admin)
    assert exc.value.status_code == 502
