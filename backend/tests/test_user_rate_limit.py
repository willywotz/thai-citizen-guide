import pytest
from fastapi import HTTPException

from app.routers.chat import enforce_user_rate_limit
from app.services.rate_limit import SlidingWindowLimiter


def test_blocks_after_limit(monkeypatch):
    import app.routers.chat as chat_mod
    t = [0.0]
    monkeypatch.setattr(chat_mod, "user_limiter", SlidingWindowLimiter(now_fn=lambda: t[0]))
    monkeypatch.setattr(chat_mod.settings, "USER_RATE_LIMIT_RPM", 2)

    class U: id = "u1"

    enforce_user_rate_limit(U())
    enforce_user_rate_limit(U())
    with pytest.raises(HTTPException) as e:
        enforce_user_rate_limit(U())
    assert e.value.status_code == 429
    assert "Retry-After" in e.value.headers
