"""
User management endpoints — mirrors manage-users edge function.
Calls Supabase Admin API for auth.users data via httpx.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.database import get_db
from app.dependencies import require_permission, AuthContext
from app.models import Profile, UserRole
from app.schemas.auth import UserRoleUpdate, UserOut
from app.config import settings

router = APIRouter(prefix="/users", tags=["users"])

PRIVILEGED_ROLES = {"super_admin", "admin"}


async def _supabase_admin_get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{settings.SUPABASE_URL}/auth/v1/admin/{path}",
            headers={"Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}"},
        )
    resp.raise_for_status()
    return resp.json()


async def _supabase_admin_delete_user(user_id: str) -> None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.delete(
            f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user_id}",
            headers={"Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}"},
        )
    resp.raise_for_status()


@router.get("", response_model=list[UserOut])
async def list_users(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("users.read")),
):
    # Fetch from Supabase auth admin API
    try:
        data = await _supabase_admin_get(f"users?page={page}&per_page={per_page}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase admin API error: {e}")

    auth_users = data.get("users", [])
    user_ids = [u["id"] for u in auth_users]

    profiles_result = await db.execute(select(Profile).where(Profile.id.in_([uuid.UUID(uid) for uid in user_ids])))
    profiles = {str(p.id): p for p in profiles_result.scalars().all()}

    roles_result = await db.execute(select(UserRole).where(UserRole.user_id.in_([uuid.UUID(uid) for uid in user_ids])))
    roles_map: dict[str, list[str]] = {}
    for r in roles_result.scalars().all():
        uid = str(r.user_id)
        if uid not in roles_map:
            roles_map[uid] = []
        roles_map[uid].append(r.role)

    users = []
    for u in auth_users:
        uid = u["id"]
        profile = profiles.get(uid)
        user_out = UserOut(
            id=uid,
            email=u.get("email"),
            profile={
                "display_name": profile.display_name if profile else None,
                "avatar_url": profile.avatar_url if profile else None,
                "is_active": profile.is_active if profile else True,
                "email_verified": profile.email_verified if profile else False,
                "auth_provider": profile.auth_provider if profile else "email",
            } if profile else None,
            roles=roles_map.get(uid, []),
            last_sign_in_at=u.get("last_sign_in_at"),
            created_at=u.get("created_at"),
        )
        users.append(user_out)

    # Search filter
    if search:
        q = search.lower()
        users = [
            u for u in users
            if q in (u.email or "").lower()
            or q in ((u.profile or {}).get("display_name") or "").lower()
        ]

    return users


@router.put("/actions")
async def user_action(
    body: UserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("users.write")),
):
    if body.action in ("assign_role", "remove_role"):
        # Also need users.roles.assign
        from app.models import RolePermission
        perm = await db.execute(
            select(RolePermission.permission)
            .where(
                RolePermission.role.in_(auth.roles),
                RolePermission.permission == "users.roles.assign",
            ).limit(1)
        )
        if not perm.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="users.roles.assign permission required")

        if not body.role:
            raise HTTPException(status_code=400, detail="role required")

        # Only super_admin can assign privileged roles
        if body.role in PRIVILEGED_ROLES and not auth.is_super_admin:
            raise HTTPException(status_code=403, detail="Only super_admin can assign admin/super_admin roles")

        if body.action == "assign_role":
            # Upsert
            existing = await db.execute(
                select(UserRole).where(
                    UserRole.user_id == uuid.UUID(body.user_id),
                    UserRole.role == body.role,
                )
            )
            if not existing.scalar_one_or_none():
                db.add(UserRole(user_id=uuid.UUID(body.user_id), role=body.role))
                await db.commit()
        else:
            await db.execute(
                delete(UserRole).where(
                    UserRole.user_id == uuid.UUID(body.user_id),
                    UserRole.role == body.role,
                )
            )
            await db.commit()

    elif body.action in ("deactivate", "activate"):
        active = body.action == "activate"
        await db.execute(
            update(Profile)
            .where(Profile.id == uuid.UUID(body.user_id))
            .values(is_active=active)
        )
        await db.commit()

    elif body.action == "update_profile":
        updates = {}
        if body.display_name is not None:
            updates["display_name"] = body.display_name
        if updates:
            await db.execute(
                update(Profile).where(Profile.id == uuid.UUID(body.user_id)).values(**updates)
            )
            await db.commit()

    else:
        raise HTTPException(status_code=400, detail="Unknown action")

    return {"success": True}


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("users.delete")),
):
    if user_id == auth.user_id:
        raise HTTPException(status_code=400, detail="Cannot delete own account")

    try:
        await _supabase_admin_delete_user(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"success": True}
