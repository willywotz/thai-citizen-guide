import pytest

from app.config import Settings, assert_production_secrets, DEFAULT_JWT_SECRET


def test_production_with_default_secret_raises():
    s = Settings(ENV="production", JWT_SECRET=DEFAULT_JWT_SECRET)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        assert_production_secrets(s)


def test_production_with_real_secret_passes():
    assert_production_secrets(Settings(ENV="production", JWT_SECRET="x" * 64))


def test_development_with_default_secret_passes():
    assert_production_secrets(Settings(ENV="development", JWT_SECRET=DEFAULT_JWT_SECRET))
