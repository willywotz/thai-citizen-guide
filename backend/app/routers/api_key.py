from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.auth.security import generate_api_key, hash_api_key
from app.models.user import User, UserAPIKey
from app.utils import now

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


class APIKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    last_used_at: str | None
    created_at: str
    expires_at: str | None
    revoked_at: str | None
    rate_limit_rpm: int | None
    status: str


class CreatedAPIKeyResponse(APIKeyResponse):
    key: str  # full key — shown only in the create response


class CreateAPIKeyRequest(BaseModel):
    name: str
    expires_in_days: int | None = None
    rate_limit_rpm: int | None = None


class UpdateAPIKeyRequest(BaseModel):
    name: str


def _status(k: UserAPIKey) -> str:
    if k.revoked_at is not None:
        return "revoked"
    if k.expires_at is not None and k.expires_at <= now():
        return "expired"
    return "active"


def _resp(k: UserAPIKey) -> APIKeyResponse:
    return APIKeyResponse(
        id=str(k.id),
        name=k.name,
        key_prefix=k.key_prefix,
        last_used_at=str(k.last_used_at) if k.last_used_at else None,
        created_at=str(k.created_at),
        expires_at=str(k.expires_at) if k.expires_at else None,
        revoked_at=str(k.revoked_at) if k.revoked_at else None,
        rate_limit_rpm=k.rate_limit_rpm,
        status=_status(k),
    )


@router.get("/", summary="List API keys for the current user")
async def list_api_keys(user: User = Depends(get_current_user)) -> list[APIKeyResponse]:
    result = await UserAPIKey.filter(user_id=user.id).order_by("-created_at").all()
    return [_resp(k) for k in result]


@router.post("/", summary="Create a new API key")
async def create_api_key(body: CreateAPIKeyRequest, user: User = Depends(get_current_user)) -> CreatedAPIKeyResponse:
    if body.expires_in_days is not None and body.expires_in_days <= 0:
        raise HTTPException(status_code=400, detail="expires_in_days must be positive")
    if body.rate_limit_rpm is not None and body.rate_limit_rpm <= 0:
        raise HTTPException(status_code=400, detail="rate_limit_rpm must be positive")
    expires_at = now() + timedelta(days=body.expires_in_days) if body.expires_in_days else None
    raw = generate_api_key()
    new_key = await UserAPIKey.create(
        user_id=user.id, name=body.name,
        key_hash=hash_api_key(raw), key_prefix=raw[:12],
        expires_at=expires_at, rate_limit_rpm=body.rate_limit_rpm,
    )
    return CreatedAPIKeyResponse(**_resp(new_key).model_dump(), key=raw)


@router.patch("/{key_id}", summary="Rename an API key")
async def update_api_key(key_id: str, body: UpdateAPIKeyRequest, user: User = Depends(get_current_user)) -> APIKeyResponse:
    key = await UserAPIKey.filter(id=key_id, user_id=user.id).first()
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    key.name = body.name
    await key.save()
    return _resp(key)


@router.delete("/{key_id}", summary="Delete an API key")
async def delete_api_key(key_id: str, user: User = Depends(get_current_user)) -> dict:
    key = await UserAPIKey.filter(id=key_id, user_id=user.id).first()
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    await key.delete()
    return {"detail": "API key deleted"}


@router.post("/{key_id}/revoke", summary="Revoke an API key (keeps it for audit; stops it working)")
async def revoke_api_key(key_id: str, user: User = Depends(get_current_user)) -> APIKeyResponse:
    key = await UserAPIKey.filter(id=key_id, user_id=user.id).first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    if key.revoked_at is None:
        key.revoked_at = now()
        await key.save(update_fields=["revoked_at"])
    return _resp(key)
