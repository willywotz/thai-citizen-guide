from app.services.rate_limit import RedisHealth


def test_first_failure_is_a_transition_then_not():
    h = RedisHealth()
    assert h.record_failure() is True   # healthy -> failing
    assert h.record_failure() is False  # already failing
    assert h.record_failure() is False


def test_success_while_healthy_returns_none():
    h = RedisHealth()
    assert h.record_success() is None


def test_recovery_returns_failed_open_count():
    h = RedisHealth()
    h.record_failure()
    h.record_failure()
    h.record_failure()
    assert h.record_success() == 3      # 3 requests failed open during outage
    assert h.record_success() is None   # already healthy again


def test_counter_accumulates_across_outages():
    h = RedisHealth()
    h.record_failure()
    h.record_success()
    h.record_failure()
    h.record_success()
    assert h.fail_open_total == 2
