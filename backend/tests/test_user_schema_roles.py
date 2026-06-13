"""The user-management schema accepts the five supported roles."""
import pytest
from pydantic import ValidationError

from app.schemas.user import UserCreate


@pytest.mark.parametrize("role", ["user", "viewer", "auditor", "agency_owner", "admin"])
def test_usercreate_accepts_supported_roles(role):
    model = UserCreate(email="x@example.com", role=role)
    assert model.role == role


def test_usercreate_rejects_unknown_role():
    with pytest.raises(ValidationError):
        UserCreate(email="x@example.com", role="superuser")
