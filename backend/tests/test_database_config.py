"""Tests for _build_tortoise_orm credential parsing in config.py."""

import pytest

from app.config import Settings, _build_tortoise_orm


def _build(database_url: str) -> dict:
    s = Settings(DATABASE_URL=database_url)
    return _build_tortoise_orm(s)["connections"]["default"]["credentials"]


def test_plain_url_parses_host_port_user_db():
    creds = _build("postgres://alice:secret@db.example.com:5433/mydb")
    assert creds["host"] == "db.example.com"
    assert creds["port"] == 5433
    assert creds["user"] == "alice"
    assert creds["password"] == "secret"
    assert creds["database"] == "mydb"


def test_default_url_parses_correctly():
    creds = _build("postgres://postgres:postgres@localhost:5432/chatbot")
    assert creds["host"] == "localhost"
    assert creds["port"] == 5432
    assert creds["user"] == "postgres"
    assert creds["database"] == "chatbot"


def test_sslmode_require_mapped_to_ssl():
    creds = _build("postgres://user:pass@host:5432/db?sslmode=require")
    assert "ssl" in creds, "ssl key must be present when sslmode=require is in URL"
    assert creds["ssl"] == "require"
    assert "sslmode" not in creds, "raw sslmode key must not appear in credentials"


def test_sslmode_verify_full_mapped_to_ssl():
    creds = _build("postgres://user:pass@host:5432/db?sslmode=verify-full")
    assert creds["ssl"] == "verify-full"


def test_percent_encoded_password_decoded():
    # pa%40ss should decode to pa@ss
    creds = _build("postgres://user:pa%40ss@host:5432/db")
    assert creds["password"] == "pa@ss", f"Expected 'pa@ss', got {creds['password']!r}"


def test_percent_encoded_username_decoded():
    creds = _build("postgres://us%40er:pass@host:5432/db")
    assert creds["user"] == "us@er", f"Expected 'us@er', got {creds['user']!r}"


def test_ssl_and_encoded_password_together():
    # Both regressions together: encoded password + sslmode
    creds = _build("postgres://user:pa%40ss@host:5432/db?sslmode=require")
    assert creds["password"] == "pa@ss"
    assert creds["ssl"] == "require"
    assert "sslmode" not in creds


def test_pool_sizing_still_applied():
    s = Settings(DATABASE_URL="postgres://user:pass@host:5432/db", DB_POOL_MIN=2, DB_POOL_MAX=20)
    creds = _build_tortoise_orm(s)["connections"]["default"]["credentials"]
    assert creds["minsize"] == 2
    assert creds["maxsize"] == 20


def test_malformed_url_raises_value_error():
    with pytest.raises(ValueError, match="malformed"):
        _build("postgres:///no-host")


def test_no_query_params_has_no_ssl_key():
    creds = _build("postgres://user:pass@host:5432/db")
    assert "ssl" not in creds
    assert "sslmode" not in creds
