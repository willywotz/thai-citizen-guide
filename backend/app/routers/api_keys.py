import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth, require_permission, AuthContext
from app.models import ApiKey as ApiKeyModel
from app.schemas.auth import ApiKeyCreate, ApiKeyOut, ApiKeyCreated
from app.auth.api_key import generate_api_key

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.get("", response_model=list[ApiKeyOut])
async def list_api_keys(
    all_keys: bool = Query(False, alias="all"),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    if all_keys:
        # Requires api_keys.read.all
        from app.models import RolePermission
        perm = await db.execute(
            select(RolePermission.permission)
            .where(
                RolePermission.role.in_(auth.roles),
                RolePermission.permission == "api_keys.read.all",
            ).limit(1)
        )
        if not perm.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        result = await db.execute(
            select(ApiKeyModel).order_by(ApiKeyModel.created_at.desc())
        )
    else:
        result = await db.execute(
            select(ApiKeyModel)
            .where(ApiKeyModel.user_id == uuid.UUID(auth.user_id))
            .order_by(ApiKeyModel.created_at.desc())
        )
    return result.scalars().all()


@router.post("", response_model=ApiKeyCreated, status_code=201)
async def create_api_key(
    body: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("api_keys.write.own")),
):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="name is required")

    raw_key, key_hash, key_prefix = generate_api_key("tcg_live_")
    expires_at = None
    if body.expires_at:
        try:
            expires_at = datetime.fromisoformat(body.expires_at.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid expires_at format")

    key_row = ApiKeyModel(
        user_id=uuid.UUID(auth.user_id),
        name=body.name.strip(),
        key_prefix=key_prefix,
        key_hash=key_hash,
        scopes=body.scopes,
        expires_at=expires_at,
    )
    db.add(key_row)
    await db.commit()
    await db.refresh(key_row)

    return ApiKeyCreated(
        id=key_row.id,
        name=key_row.name,
        key_prefix=key_row.key_prefix,
        scopes=key_row.scopes,
        expires_at=key_row.expires_at,
        last_used_at=key_row.last_used_at,
        revoked_at=key_row.revoked_at,
        created_at=key_row.created_at,
        raw_key=raw_key,
    )


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    reason: Optional[str] = Query("user_request"),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    result = await db.execute(select(ApiKeyModel).where(ApiKeyModel.id == uuid.UUID(key_id)))
    key_row = result.scalar_one_or_none()
    if not key_row:
        raise HTTPException(status_code=404, detail="Key not found")

    # Check ownership or revoke.all permission
    is_owner = str(key_row.user_id) == auth.user_id
    if not is_owner:
        from app.models import RolePermission
        perm = await db.execute(
            select(RolePermission.permission)
            .where(
                RolePermission.role.in_(auth.roles),
                RolePermission.permission == "api_keys.revoke.all",
            ).limit(1)
        )
        if not perm.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Forbidden")

    if key_row.revoked_at:
        raise HTTPException(status_code=400, detail="Key already revoked")

    now = datetime.now(timezone.utc)
    await db.execute(
        update(ApiKeyModel)
        .where(ApiKeyModel.id == key_row.id)
        .values(revoked_at=now, revoked_reason=reason, updated_at=now)
    )
    await db.commit()
    return {"success": True}
