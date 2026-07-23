"""The Role literal accepts only the two surviving roles."""
import pytest
from pydantic import ValidationError

from app.schemas.user import UserCreate


@pytest.mark.parametrize("role", ["user", "admin"])
def test_supported_roles_accepted(role):
    assert UserCreate(email="a@x.com", role=role).role == role


@pytest.mark.parametrize("role", ["viewer", "auditor", "agency_owner"])
def test_removed_roles_rejected(role):
    with pytest.raises(ValidationError):
        UserCreate(email="a@x.com", role=role)


def test_role_defaults_to_user():
    assert UserCreate(email="a@x.com").role == "user"
