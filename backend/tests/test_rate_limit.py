from app.services.rate_limit import SlidingWindowLimiter


def test_allows_up_to_limit_then_blocks():
    t = [0.0]
    lim = SlidingWindowLimiter(now_fn=lambda: t[0])
    assert all(lim.allow("a", limit=3) for _ in range(3))
    assert lim.allow("a", limit=3) is False


def test_window_expiry_frees_slots():
    t = [0.0]
    lim = SlidingWindowLimiter(now_fn=lambda: t[0])
    for _ in range(3):
        lim.allow("a", limit=3)
    t[0] = 61.0
    assert lim.allow("a", limit=3) is True


def test_keys_are_independent():
    t = [0.0]
    lim = SlidingWindowLimiter(now_fn=lambda: t[0])
    for _ in range(3):
        lim.allow("a", limit=3)
    assert lim.allow("b", limit=3) is True
