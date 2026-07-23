import logging

from app.config import Settings


def test_apply_overrides_reports_unknown_and_invalid(caplog):
    s = Settings()
    with caplog.at_level(logging.WARNING, logger="app.config"):
        report = s.apply_overrides({
            "A2A_DISPATCH_TIMEOUT": "42",   # valid
            "NOPE_KEY": "x",               # unknown
            "JWT_EXPIRE_MINUTES": "abc",   # invalid int
        })
    assert s.A2A_DISPATCH_TIMEOUT == 42
    assert report.applied == ["A2A_DISPATCH_TIMEOUT"]
    assert report.unknown == ["NOPE_KEY"]
    assert report.invalid == ["JWT_EXPIRE_MINUTES"]
    assert any("NOPE_KEY" in r.getMessage() for r in caplog.records)
