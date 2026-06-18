"""Guard test: read-only roles (viewer, auditor) are NOT rejected by MCP auth.

The MCP transport (/mcp) is mounted outside FastAPI's dependency injection, so
the role chokepoint (enforce_role_allowlist) never runs for it. The only auth
gate is AuthMiddleware in app/mcp/server.py,
which checks that the API key is usable and the user is active — no role
check at all.

These tests reproduce the exact DB lookups performed by AuthMiddleware to
confirm that viewer and auditor keys resolve to a live User object and are
not filtered out by any role condition.
"""

import pytest

from app.auth.security import generate_api_key, hash_api_key
from app.models.user import User, UserAPIKey


async def _resolve_user_via_mcp_auth(raw_key: str) -> User | None:
    """Mirror the AuthMiddleware lookup in app/mcp/server.py lines 52-56."""
    api_key = await UserAPIKey.filter(key_hash=hash_api_key(raw_key)).first()
    if api_key and api_key.is_usable():
        return await User.filter(id=api_key.user_id, is_active=True).first()
    return None


async def _make_user_with_key(email: str, role: str) -> tuple[User, str]:
    user = await User.create(email=email, hashed_password="h", role=role)
    raw = generate_api_key()
    await UserAPIKey.create(
        user_id=user.id, name="test", key_hash=hash_api_key(raw), key_prefix=raw[:12]
    )
    return user, raw


@pytest.mark.asyncio
async def test_viewer_api_key_resolves_via_mcp_auth(db):
    """A viewer with a valid API key is admitted by MCP auth (no role gate)."""
    user, raw = await _make_user_with_key("viewer@x.com", "viewer")
    resolved = await _resolve_user_via_mcp_auth(raw)
    assert resolved is not None
    assert resolved.id == user.id


@pytest.mark.asyncio
async def test_auditor_api_key_resolves_via_mcp_auth(db):
    """An auditor with a valid API key is admitted by MCP auth (no role gate)."""
    user, raw = await _make_user_with_key("auditor@x.com", "auditor")
    resolved = await _resolve_user_via_mcp_auth(raw)
    assert resolved is not None
    assert resolved.id == user.id


@pytest.mark.asyncio
async def test_invalid_key_returns_none(db):
    """A bogus key yields None — the MCP tool will respond unauthenticated."""
    resolved = await _resolve_user_via_mcp_auth("tcg_totallybogus")
    assert resolved is None


@pytest.mark.asyncio
async def test_inactive_user_returns_none(db):
    """An inactive user's key does not resolve — is_active=True is required."""
    user = await User.create(
        email="inactive@x.com", hashed_password="h", role="viewer", is_active=False
    )
    raw = generate_api_key()
    await UserAPIKey.create(
        user_id=user.id, name="test", key_hash=hash_api_key(raw), key_prefix=raw[:12]
    )
    resolved = await _resolve_user_via_mcp_auth(raw)
    assert resolved is None


def test_mcp_server_module_has_no_role_check():
    """Structural guard: AuthMiddleware source must not contain role gating.

    If someone adds a role check to the MCP middleware this test will fail,
    prompting a deliberate decision rather than a silent behaviour change.
    """
    import inspect

    from app.mcp.server import AuthMiddleware

    src = inspect.getsource(AuthMiddleware.on_request)
    role_gate_indicators = [".role", "enforce_role", "require_role", "viewer", "auditor"]
    for indicator in role_gate_indicators:
        assert indicator not in src, (
            f"AuthMiddleware.on_request appears to contain a role check ({indicator!r}). "
            "Read-only roles (viewer, auditor) are intentionally allowed to use MCP. "
            "Update the guard test and this comment if the intent has changed."
        )
