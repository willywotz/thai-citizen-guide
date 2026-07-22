"""The socket loop: connection cap, auth resolution, duration cap."""

import pytest

from app.config import settings
from app.routers.responses import _ConnectionRegistry, _ws_user


@pytest.fixture
def restore_cap():
    original = settings.RESPONSES_WS_MAX_CONNECTIONS
    yield
    settings.RESPONSES_WS_MAX_CONNECTIONS = original


class _FakeSocket:
    def __init__(self, headers: dict[str, str] | None = None):
        self.headers = headers or {}


def test_registry_admits_up_to_the_cap(restore_cap):
    settings.RESPONSES_WS_MAX_CONNECTIONS = 2
    registry = _ConnectionRegistry()
    assert registry.acquire() is True
    assert registry.acquire() is True
    assert registry.acquire() is False


def test_registry_frees_a_slot_on_release(restore_cap):
    settings.RESPONSES_WS_MAX_CONNECTIONS = 1
    registry = _ConnectionRegistry()
    assert registry.acquire() is True
    assert registry.acquire() is False
    registry.release()
    assert registry.acquire() is True


def test_release_never_goes_negative(restore_cap):
    settings.RESPONSES_WS_MAX_CONNECTIONS = 1
    registry = _ConnectionRegistry()
    registry.release()
    registry.release()
    assert registry.acquire() is True
    assert registry.acquire() is False


@pytest.mark.asyncio
async def test_missing_authorization_is_anonymous(db):
    assert await _ws_user(_FakeSocket()) is None


@pytest.mark.asyncio
async def test_non_bearer_authorization_is_anonymous(db):
    assert await _ws_user(_FakeSocket({"authorization": "Basic abc"})) is None


@pytest.mark.asyncio
async def test_invalid_token_is_anonymous_not_an_exception(db):
    assert await _ws_user(_FakeSocket({"authorization": "Bearer tcg_bogus"})) is None
