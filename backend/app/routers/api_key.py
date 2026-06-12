from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.auth.security import generate_api_key, hash_api_key
from app.models.user import User, UserAPIKey

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


class APIKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    last_used_at: str | None
    created_at: str


class CreatedAPIKeyResponse(APIKeyResponse):
    key: str  # full key — shown only in the create response


class CreateAPIKeyRequest(BaseModel):
    name: str


class UpdateAPIKeyRequest(BaseModel):
    name: str


def _resp(k: UserAPIKey) -> APIKeyResponse:
    return APIKeyResponse(
        id=str(k.id),
        name=k.name,
        key_prefix=k.key_prefix,
        last_used_at=str(k.last_used_at) if k.last_used_at else None,
        created_at=str(k.created_at),
    )


@router.get("/", summary="List API keys for the current user")
async def list_api_keys(user: User = Depends(get_current_user)) -> list[APIKeyResponse]:
    result = await UserAPIKey.filter(user_id=user.id).order_by("-created_at").all()
    return [_resp(k) for k in result]


@router.post("/", summary="Create a new API key")
async def create_api_key(body: CreateAPIKeyRequest, user: User = Depends(get_current_user)) -> CreatedAPIKeyResponse:
    raw = generate_api_key()
    new_key = await UserAPIKey.create(
        user_id=user.id, name=body.name,
        key_hash=hash_api_key(raw), key_prefix=raw[:12],
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
