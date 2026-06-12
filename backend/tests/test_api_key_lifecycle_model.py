from app.models.user import User, UserAPIKey


async def test_lifecycle_fields_default_to_none(db):
    user = await User.create(email="ak@x.com", hashed_password="h")
    key = await UserAPIKey.create(user_id=user.id, name="n", key_hash="abc", key_prefix="tcg_x")
    assert key.expires_at is None
    assert key.revoked_at is None
    assert key.rate_limit_rpm is None
