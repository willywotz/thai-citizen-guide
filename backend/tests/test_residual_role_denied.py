"""Residual pre-migration roles (`viewer`, `auditor`, `agency_owner`) must be
denied by default at the `enforce_role_allowlist` chokepoint, not fail open.

The DB migration that rewrites these rows to `user` hasn't run yet, so a row
with one of these roles can still exist while this code is deployed. The ORM
bypasses the `Role` literal, so `User.create(role="viewer")` is how such a row
is reproduced here.
"""
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

from app.auth.dependencies import enforce_role_allowlist
from app.auth.security import create_access_token
from app.models.user import User


def _request(method: str, path: str) -> Request:
    return Request(
        {"type": "http", "method": method, "path": path,
         "headers": [], "query_string": b""}
    )


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


async def _token_for_viewer() -> str:
    user = await User.create(email="residual-viewer@x.com", hashed_password="h", role="viewer")
    return create_access_token({"sub": str(user.id)})


async def test_residual_viewer_denied_on_api_keys(db):
    token = await _token_for_viewer()
    with pytest.raises(HTTPException) as e:
        await enforce_role_allowlist(
            _request("POST", "/api/v1/api-keys/"), _creds(token)
        )
    assert e.value.status_code == 403


async def test_residual_viewer_denied_on_connection_logs(db):
    token = await _token_for_viewer()
    with pytest.raises(HTTPException) as e:
        await enforce_role_allowlist(
            _request("GET", "/api/v1/connection-logs"), _creds(token)
        )
    assert e.value.status_code == 403


async def test_residual_viewer_allowed_on_chat(db):
    token = await _token_for_viewer()
    assert await enforce_role_allowlist(
        _request("POST", "/api/v1/chat"), _creds(token)
    ) is None
