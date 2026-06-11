# Admin User Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an admin-only capability to list/search, create (password or email invite), edit role/profile, and activate/deactivate (soft-delete) user accounts — backend API plus a frontend Users admin page.

**Architecture:** A dedicated `users` admin module on the backend (`routers/users.py`, `schemas/user.py`, `services/user.py`), all endpoints behind the existing `require_admin` dependency and mounted at `/api/v1/users`. Self-service auth (`auth.py`) is untouched. Guardrail logic (no self-mutation, protect the last active admin) and the create/invite flow live in the service layer for testability. Frontend adds a `features/users/` folder mirroring `features/agencies/`.

**Tech Stack:** FastAPI · Tortoise ORM · pytest / pytest-asyncio · React · TanStack Query · Axios · shadcn/ui · Vitest.

---

## File Structure

**Backend**
- Create `backend/tests/conftest.py` — in-memory SQLite Tortoise fixture for DB-backed tests.
- Create `backend/app/schemas/user.py` — request/response Pydantic models.
- Create `backend/app/services/user.py` — guardrails + create/invite flow.
- Create `backend/app/routers/users.py` — REST endpoints (admin-gated).
- Create `backend/tests/test_users_service.py` — service + guardrail tests.
- Create `backend/tests/test_users_router.py` — endpoint tests.
- Modify `backend/app/main.py` — register the router.

**Frontend**
- Create `frontend/src/features/users/userApi.ts` — typed API wrappers + types.
- Create `frontend/src/features/users/useUsers.ts` — TanStack Query hooks.
- Create `frontend/src/features/users/userForm.ts` — create-mode validation helper (pure, unit-tested).
- Create `frontend/src/features/users/userForm.test.ts` — validation unit tests.
- Create `frontend/src/features/users/UserFormDialog.tsx` — create/edit dialog.
- Create `frontend/src/features/users/DeactivateUserDialog.tsx` — confirm activate/deactivate.
- Create `frontend/src/features/users/UsersPage.tsx` — table + filters + actions.
- Modify `frontend/src/App.tsx` — add `/users` route.
- Modify `frontend/src/shared/components/layout/AppSidebar.tsx` — add admin nav entry.

---

## Task 1: Test DB fixture (conftest)

The existing reset-token test mocks the DB. Guardrails need to *count* admins, so service/router tests use a real in-memory SQLite DB via this shared fixture.

**Files:**
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Write the fixture**

```python
"""
Shared pytest fixtures.

`db` spins up an in-memory SQLite database with the app's Tortoise models so
tests that exercise real queries (e.g. admin-count guardrails) run without a
live PostgreSQL instance. SQLite is sufficient: the User model uses only
portable field types (UUID/Char/Boolean/Datetime).
"""

import pytest_asyncio
from tortoise import Tortoise


@pytest_asyncio.fixture(scope="function")
async def db():
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["app.models"]},
    )
    await Tortoise.generate_schemas()
    try:
        yield
    finally:
        await Tortoise.close_connections()
```

- [ ] **Step 2: Sanity-check the fixture compiles**

Run: `cd backend && uv run python -c "import tests.conftest"`
Expected: no output, exit 0.

- [ ] **Step 3: Commit**

```bash
rtk git add backend/tests/conftest.py
rtk git commit -m "test: add in-memory sqlite db fixture for user-management tests"
```

---

## Task 2: Schemas

**Files:**
- Create: `backend/app/schemas/user.py`

- [ ] **Step 1: Write the schemas**

```python
"""Pydantic schemas for admin user-management endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr

from app.models.user import User

Role = Literal["user", "admin"]


class UserCreate(BaseModel):
    email: EmailStr
    role: Role = "user"
    display_name: str | None = None
    password: str | None = None
    send_invite: bool = False


class UserUpdate(BaseModel):
    display_name: str | None = None
    role: Role | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    displayName: str
    role: str
    avatarUrl: str | None = None
    isActive: bool
    createdAt: datetime

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(
            id=str(user.id),
            email=user.email,
            displayName=user.display_name or user.email.split("@")[0],
            role=user.role,
            avatarUrl=user.avatar_url,
            isActive=user.is_active,
            createdAt=user.created_at,
        )


class UserListResponse(BaseModel):
    data: list[UserResponse]
    total: int
```

- [ ] **Step 2: Verify it imports**

Run: `cd backend && uv run python -c "from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserListResponse"`
Expected: no output, exit 0.

- [ ] **Step 3: Commit**

```bash
rtk git add backend/app/schemas/user.py
rtk git commit -m "feat(users): add admin user-management schemas"
```

---

## Task 3: Service — guardrails + create flow

**Files:**
- Create: `backend/app/services/user.py`
- Test: `backend/tests/test_users_service.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for app.services.user — create flow and guardrails."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.models.user import User
from app.schemas.user import UserCreate
from app.services import user as user_service


async def _make_admin(email="admin@example.com", active=True):
    return await User.create(
        email=email, hashed_password="x", role="admin", is_active=active
    )


@pytest.mark.asyncio
async def test_create_with_password_hashes_and_persists(db):
    created, extra = await user_service.create_user(
        UserCreate(email="new@example.com", role="user", password="secret123")
    )
    assert created.id is not None
    assert created.hashed_password != "secret123"
    assert extra == {}


@pytest.mark.asyncio
async def test_create_with_invite_issues_token_and_emails(db):
    with patch.object(user_service, "send_password_reset_email", AsyncMock(return_value=True)):
        created, extra = await user_service.create_user(
            UserCreate(email="inv@example.com", role="user", send_invite=True)
        )
    assert created.reset_token is not None
    assert extra["email_sent"] is True
    assert "reset_token" not in extra


@pytest.mark.asyncio
async def test_create_invite_email_fails_exposes_token_when_flag_on(db):
    from app.config import settings

    with patch.object(settings, "EXPOSE_PASSWORD_RESET_TOKEN", True), \
         patch.object(user_service, "send_password_reset_email", AsyncMock(return_value=False)):
        _created, extra = await user_service.create_user(
            UserCreate(email="inv2@example.com", send_invite=True)
        )
    assert extra["email_sent"] is False
    assert extra["reset_token"]


@pytest.mark.asyncio
async def test_create_rejects_both_password_and_invite(db):
    with pytest.raises(HTTPException) as exc:
        await user_service.create_user(
            UserCreate(email="x@example.com", password="secret123", send_invite=True)
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_create_rejects_neither_password_nor_invite(db):
    with pytest.raises(HTTPException) as exc:
        await user_service.create_user(UserCreate(email="x@example.com"))
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_create_rejects_short_password(db):
    with pytest.raises(HTTPException) as exc:
        await user_service.create_user(
            UserCreate(email="x@example.com", password="123")
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_create_rejects_duplicate_email(db):
    await _make_admin(email="dup@example.com")
    with pytest.raises(HTTPException) as exc:
        await user_service.create_user(
            UserCreate(email="dup@example.com", password="secret123")
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_ensure_not_self_blocks_same_id(db):
    admin = await _make_admin()
    with pytest.raises(HTTPException) as exc:
        user_service.ensure_not_self(admin.id, admin.id)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_ensure_not_self_allows_different_id(db):
    admin = await _make_admin()
    other = await _make_admin(email="other@example.com")
    user_service.ensure_not_self(admin.id, other.id)  # no raise


@pytest.mark.asyncio
async def test_ensure_not_last_admin_blocks_demoting_only_admin(db):
    admin = await _make_admin()
    with pytest.raises(HTTPException) as exc:
        await user_service.ensure_not_last_admin(admin)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_ensure_not_last_admin_allows_when_another_admin_exists(db):
    admin = await _make_admin()
    await _make_admin(email="admin2@example.com")
    await user_service.ensure_not_last_admin(admin)  # no raise


@pytest.mark.asyncio
async def test_ensure_not_last_admin_ignores_non_admin_target(db):
    await _make_admin()
    plain = await User.create(email="u@example.com", hashed_password="x", role="user")
    await user_service.ensure_not_last_admin(plain)  # no raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_users_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.user'`.

- [ ] **Step 3: Write the service**

```python
"""
Business logic for admin user management.

Kept separate from the router so guardrails (no self-mutation, protect the last
active admin) and the dual create/invite flow can be unit-tested directly.
"""

from __future__ import annotations

import secrets
import uuid

from fastapi import HTTPException, status

from app.auth.security import (
    generate_reset_token,
    hash_password,
    reset_token_expiry,
)
from app.config import settings
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.email import send_password_reset_email


def ensure_not_self(acting_user_id: uuid.UUID, target_id: uuid.UUID) -> None:
    """An admin may not change their own role, deactivate, or delete themselves."""
    if str(acting_user_id) == str(target_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ไม่สามารถดำเนินการกับบัญชีของตนเองได้",
        )


async def ensure_not_last_admin(target: User) -> None:
    """Reject an action that would leave the system with zero active admins."""
    if target.role != "admin" or not target.is_active:
        return
    others = await User.filter(role="admin", is_active=True).exclude(id=target.id).count()
    if others == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ต้องมีผู้ดูแลระบบที่ใช้งานได้อย่างน้อยหนึ่งคน",
        )


async def create_user(data: UserCreate) -> tuple[User, dict]:
    """
    Create a user via one of two mutually-exclusive modes:
      * password — admin sets an initial password; user can log in immediately.
      * send_invite — generate a reset token and email it; account starts with
        an unusable random password.
    Returns the created user plus any extra response fields (invite metadata).
    """
    has_password = bool(data.password)
    if has_password == data.send_invite:  # both set or neither set
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ต้องระบุรหัสผ่าน หรือเลือกส่งคำเชิญทางอีเมล อย่างใดอย่างหนึ่ง",
        )

    if has_password and len(data.password) < settings.MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร",
        )

    if await User.filter(email=data.email).exists():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="อีเมลนี้ถูกใช้งานแล้ว")

    hashed = hash_password(data.password if has_password else secrets.token_urlsafe(32))
    user = await User.create(
        email=data.email,
        display_name=data.display_name,
        hashed_password=hashed,
        role=data.role,
    )

    extra: dict = {}
    if data.send_invite:
        token = generate_reset_token()
        user.reset_token = token
        user.reset_token_expires = reset_token_expiry()
        await user.save(update_fields=["reset_token", "reset_token_expires"])
        emailed = await send_password_reset_email(user.email, token)
        extra["email_sent"] = emailed
        if not emailed and settings.EXPOSE_PASSWORD_RESET_TOKEN:
            extra["reset_token"] = token

    return user, extra
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_users_service.py -v`
Expected: PASS (all 12 tests).

- [ ] **Step 5: Format, lint, commit**

```bash
cd backend && uv run ruff format app/services/user.py app/schemas/user.py tests/test_users_service.py && uv run ruff check app/services/user.py
rtk git add backend/app/services/user.py backend/tests/test_users_service.py
rtk git commit -m "feat(users): add user-management service with create flow and guardrails"
```

(If the project uses a different linter than ruff, run the one configured in `pyproject.toml`. Skip silently if none.)

---

## Task 4: Router endpoints

**Files:**
- Create: `backend/app/routers/users.py`
- Test: `backend/tests/test_users_router.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for app.routers.users — endpoints called directly with an injected admin."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.models.user import User
from app.routers import users as users_router
from app.schemas.user import UserCreate, UserUpdate


async def _admin(email="admin@example.com"):
    return await User.create(email=email, hashed_password="x", role="admin", is_active=True)


async def _user(email="u@example.com", role="user", active=True):
    return await User.create(email=email, hashed_password="x", role=role, is_active=active)


@pytest.mark.asyncio
async def test_list_returns_all(db):
    admin = await _admin()
    await _user(email="a@example.com")
    await _user(email="b@example.com")
    res = await users_router.list_users(search=None, role=None, status_filter="all", admin=admin)
    assert res.total == 3
    assert len(res.data) == 3


@pytest.mark.asyncio
async def test_list_search_filters_by_email(db):
    admin = await _admin()
    await _user(email="needle@example.com")
    res = await users_router.list_users(search="needle", role=None, status_filter="all", admin=admin)
    assert res.total == 1
    assert res.data[0].email == "needle@example.com"


@pytest.mark.asyncio
async def test_list_role_and_status_filters(db):
    admin = await _admin()
    await _user(email="active@example.com", active=True)
    await _user(email="inactive@example.com", active=False)
    active_only = await users_router.list_users(search=None, role="user", status_filter="active", admin=admin)
    assert {u.email for u in active_only.data} == {"active@example.com"}


@pytest.mark.asyncio
async def test_create_with_password_returns_201_shape(db):
    admin = await _admin()
    res = await users_router.create_user(
        UserCreate(email="new@example.com", password="secret123"), admin=admin
    )
    assert res["user"]["email"] == "new@example.com"
    assert "email_sent" not in res  # password mode adds no invite metadata


@pytest.mark.asyncio
async def test_get_single_404(db):
    admin = await _admin()
    import uuid
    with pytest.raises(HTTPException) as exc:
        await users_router.get_user(uuid.uuid4(), admin=admin)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_patch_updates_display_name_and_role(db):
    admin = await _admin()
    target = await _user(email="t@example.com")
    res = await users_router.update_user(
        target.id, UserUpdate(display_name="New Name", role="admin"), admin=admin
    )
    assert res.displayName == "New Name"
    assert res.role == "admin"


@pytest.mark.asyncio
async def test_patch_self_role_change_blocked(db):
    admin = await _admin()
    with pytest.raises(HTTPException) as exc:
        await users_router.update_user(admin.id, UserUpdate(role="user"), admin=admin)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_patch_demote_other_admin_allowed(db):
    # Demoting a *different* admin always leaves the acting admin active, so it
    # is allowed. (The zero-active-admins case is unreachable at the router
    # level once self-action is blocked — it is unit-tested directly against
    # ensure_not_last_admin in test_users_service.py.)
    admin = await _admin()
    target = await _user(email="admin2@example.com", role="admin")
    res = await users_router.update_user(target.id, UserUpdate(role="user"), admin=admin)
    assert res.role == "user"


@pytest.mark.asyncio
async def test_deactivate_sets_inactive(db):
    admin = await _admin()
    target = await _user(email="t@example.com")
    res = await users_router.deactivate_user(target.id, admin=admin)
    assert res.isActive is False


@pytest.mark.asyncio
async def test_deactivate_self_blocked(db):
    admin = await _admin()
    with pytest.raises(HTTPException) as exc:
        await users_router.deactivate_user(admin.id, admin=admin)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_deactivate_other_admin_allowed(db):
    # Deactivating a different admin leaves the acting admin active → allowed.
    admin = await _admin()
    target = await _user(email="admin2@example.com", role="admin")
    res = await users_router.deactivate_user(target.id, admin=admin)
    assert res.isActive is False


@pytest.mark.asyncio
async def test_activate_sets_active(db):
    admin = await _admin()
    target = await _user(email="t@example.com", active=False)
    res = await users_router.activate_user(target.id, admin=admin)
    assert res.isActive is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_users_router.py -v`
Expected: FAIL — `cannot import name ... from 'app.routers.users'` (module not created yet).

- [ ] **Step 3: Write the router**

```python
"""
Admin user-management routes. Every endpoint requires an authenticated admin.

Endpoints
---------
  GET    /users                 List/search users (filters: search, role, status)
  POST   /users                 Create a user (password OR email invite)
  GET    /users/{id}            Get a single user
  PATCH  /users/{id}            Update display_name and/or role
  POST   /users/{id}/deactivate Soft-delete: set is_active=False
  POST   /users/{id}/activate   Set is_active=True
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from tortoise.exceptions import DoesNotExist

from app.auth.dependencies import require_admin
from app.models.user import User
from app.schemas.user import UserCreate, UserListResponse, UserResponse, UserUpdate
from app.services import user as user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=UserListResponse, summary="List users")
async def list_users(
    search: str | None = Query(None, description="Search email or display name"),
    role: str | None = Query(None, description="Filter by role: user | admin"),
    status_filter: Literal["active", "inactive", "all"] = Query(
        "all", alias="status", description="Filter by active status"
    ),
    admin: User = Depends(require_admin),
) -> UserListResponse:
    qs = User.all()
    if search:
        qs = qs.filter(email__icontains=search) | User.filter(display_name__icontains=search)
    if role:
        qs = qs.filter(role=role)
    if status_filter == "active":
        qs = qs.filter(is_active=True)
    elif status_filter == "inactive":
        qs = qs.filter(is_active=False)

    rows = await qs.order_by("-created_at")
    return UserListResponse(
        data=[UserResponse.from_user(u) for u in rows],
        total=len(rows),
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create a user")
async def create_user(body: UserCreate, admin: User = Depends(require_admin)) -> dict:
    user, extra = await user_service.create_user(body)
    return {"user": UserResponse.from_user(user).model_dump(), **extra}


@router.get("/{user_id}", response_model=UserResponse, summary="Get user by ID")
async def get_user(user_id: uuid.UUID, admin: User = Depends(require_admin)) -> UserResponse:
    try:
        user = await User.get(id=user_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.from_user(user)


@router.patch("/{user_id}", response_model=UserResponse, summary="Update a user")
async def update_user(
    user_id: uuid.UUID, body: UserUpdate, admin: User = Depends(require_admin)
) -> UserResponse:
    try:
        user = await User.get(id=user_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.role is not None and body.role != user.role:
        user_service.ensure_not_self(admin.id, user.id)
        if user.role == "admin" and body.role == "user":
            await user_service.ensure_not_last_admin(user)
        user.role = body.role

    if body.display_name is not None:
        user.display_name = body.display_name

    await user.save()
    return UserResponse.from_user(user)


@router.post("/{user_id}/deactivate", response_model=UserResponse, summary="Deactivate (soft-delete) a user")
async def deactivate_user(user_id: uuid.UUID, admin: User = Depends(require_admin)) -> UserResponse:
    try:
        user = await User.get(id=user_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user_service.ensure_not_self(admin.id, user.id)
    await user_service.ensure_not_last_admin(user)
    user.is_active = False
    await user.save(update_fields=["is_active"])
    return UserResponse.from_user(user)


@router.post("/{user_id}/activate", response_model=UserResponse, summary="Reactivate a user")
async def activate_user(user_id: uuid.UUID, admin: User = Depends(require_admin)) -> UserResponse:
    try:
        user = await User.get(id=user_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = True
    await user.save(update_fields=["is_active"])
    return UserResponse.from_user(user)
```

> Note on the `search` filter: Tortoise supports `|` to OR two querysets. If the
> combined-queryset OR causes issues with later `.filter()` chaining in your
> Tortoise version, fall back to `Q` objects:
> `from tortoise.expressions import Q` then
> `qs = qs.filter(Q(email__icontains=search) | Q(display_name__icontains=search))`.
> Prefer the `Q` form — apply it from the start to keep filter composition clean.

- [ ] **Step 4: Adjust the search filter to use Q objects (cleaner composition)**

Replace the `if search:` block in `list_users` with:

```python
    from tortoise.expressions import Q
    if search:
        qs = qs.filter(Q(email__icontains=search) | Q(display_name__icontains=search))
```

(Move the `from tortoise.expressions import Q` import to the top of the file with the other imports.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_users_router.py -v`
Expected: PASS (all tests).

- [ ] **Step 6: Format, lint, commit**

```bash
cd backend && uv run ruff format app/routers/users.py tests/test_users_router.py && uv run ruff check app/routers/users.py
rtk git add backend/app/routers/users.py backend/tests/test_users_router.py
rtk git commit -m "feat(users): add admin user-management router"
```

---

## Task 5: Register the router

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add `users` to the routers import**

Find this line:

```python
from app.routers import agencies, conversations, messages, dashboard, feedback, auth, seed, chat, connection_logs, api_key, executive_summary, insight, settings as settings_router
```

Replace it with (adds `users`):

```python
from app.routers import agencies, conversations, messages, dashboard, feedback, auth, seed, chat, connection_logs, api_key, executive_summary, insight, users, settings as settings_router
```

- [ ] **Step 2: Include the router**

Find:

```python
app.include_router(auth.router, prefix="/api/v1")
```

Add immediately after it:

```python
app.include_router(users.router, prefix="/api/v1")
```

- [ ] **Step 3: Verify the app imports**

Run: `cd backend && uv run python -c "from app.main import app; print([r.path for r in app.routes if '/users' in getattr(r, 'path', '')])"`
Expected: prints a list including `/api/v1/users` paths.

- [ ] **Step 4: Run the full backend test suite**

Run: `cd backend && uv run pytest -q`
Expected: PASS (all tests, including pre-existing ones).

- [ ] **Step 5: Commit**

```bash
rtk git add backend/app/main.py
rtk git commit -m "feat(users): register user-management router under /api/v1"
```

---

## Task 6: Frontend API client

**Files:**
- Create: `frontend/src/features/users/userApi.ts`

- [ ] **Step 1: Write the API module**

```typescript
import { api } from '@/shared/lib/apiClient';

export type UserRole = 'user' | 'admin';

export interface ManagedUser {
  id: string;
  email: string;
  displayName: string;
  role: UserRole;
  avatarUrl: string | null;
  isActive: boolean;
  createdAt: string;
}

export interface UserListParams {
  search?: string;
  role?: UserRole;
  status?: 'active' | 'inactive' | 'all';
}

export interface CreateUserPayload {
  email: string;
  role: UserRole;
  display_name?: string | null;
  password?: string;
  send_invite?: boolean;
}

export interface UpdateUserPayload {
  display_name?: string | null;
  role?: UserRole;
}

export async function listUsers(params: UserListParams): Promise<ManagedUser[]> {
  const res = await api.get<{ data: ManagedUser[]; total: number }>('/api/v1/users', params);
  return res.data;
}

export async function createUser(payload: CreateUserPayload): Promise<{ user: ManagedUser; email_sent?: boolean; reset_token?: string }> {
  return api.post('/api/v1/users', payload);
}

export async function updateUser(id: string, payload: UpdateUserPayload): Promise<ManagedUser> {
  return api.patch(`/api/v1/users/${id}`, payload);
}

export async function deactivateUser(id: string): Promise<ManagedUser> {
  return api.post(`/api/v1/users/${id}/deactivate`);
}

export async function activateUser(id: string): Promise<ManagedUser> {
  return api.post(`/api/v1/users/${id}/activate`);
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && rtk npx tsc --noEmit`
Expected: no errors referencing `userApi.ts`.

- [ ] **Step 3: Commit**

```bash
rtk git add frontend/src/features/users/userApi.ts
rtk git commit -m "feat(users): add frontend user-management API client"
```

---

## Task 7: Create-mode validation helper (pure, unit-tested)

The dialog must enforce "set password OR send invite, not both, not neither". Extract this as a pure function so it is unit-testable without rendering.

**Files:**
- Create: `frontend/src/features/users/userForm.ts`
- Test: `frontend/src/features/users/userForm.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
import { describe, it, expect } from 'vitest';
import { validateCreateMode, MIN_PASSWORD_LENGTH } from './userForm';

describe('validateCreateMode', () => {
  it('accepts a valid password when not inviting', () => {
    expect(validateCreateMode({ sendInvite: false, password: 'secret123' })).toBeNull();
  });

  it('accepts invite with no password', () => {
    expect(validateCreateMode({ sendInvite: true, password: '' })).toBeNull();
  });

  it('rejects a too-short password', () => {
    expect(validateCreateMode({ sendInvite: false, password: '123' })).toMatch(/อย่างน้อย/);
  });

  it('rejects empty password when not inviting', () => {
    expect(validateCreateMode({ sendInvite: false, password: '' })).toMatch(/รหัสผ่าน/);
  });

  it('exposes the shared minimum length', () => {
    expect(MIN_PASSWORD_LENGTH).toBe(6);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && rtk npx vitest run src/features/users/userForm.test.ts`
Expected: FAIL — cannot resolve `./userForm`.

- [ ] **Step 3: Write the helper**

```typescript
export const MIN_PASSWORD_LENGTH = 6;

export interface CreateModeInput {
  sendInvite: boolean;
  password: string;
}

/** Returns an error message (Thai) or null when the create-mode input is valid. */
export function validateCreateMode({ sendInvite, password }: CreateModeInput): string | null {
  if (sendInvite) return null;
  if (!password) return 'กรุณากรอกรหัสผ่าน';
  if (password.length < MIN_PASSWORD_LENGTH) return 'รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร';
  return null;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && rtk npx vitest run src/features/users/userForm.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
rtk git add frontend/src/features/users/userForm.ts frontend/src/features/users/userForm.test.ts
rtk git commit -m "feat(users): add create-mode validation helper with tests"
```

---

## Task 8: TanStack Query hooks

**Files:**
- Create: `frontend/src/features/users/useUsers.ts`

- [ ] **Step 1: Write the hooks**

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listUsers,
  createUser,
  updateUser,
  deactivateUser,
  activateUser,
  type UserListParams,
  type CreateUserPayload,
  type UpdateUserPayload,
} from './userApi';

const KEY = 'users';

export function useUsers(params: UserListParams) {
  return useQuery({
    queryKey: [KEY, params],
    queryFn: () => listUsers(params),
    staleTime: 30_000,
  });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateUserPayload) => createUser(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY] }),
  });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateUserPayload }) => updateUser(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY] }),
  });
}

export function useSetUserActive() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      active ? activateUser(id) : deactivateUser(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY] }),
  });
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && rtk npx tsc --noEmit`
Expected: no errors referencing `useUsers.ts`.

- [ ] **Step 3: Commit**

```bash
rtk git add frontend/src/features/users/useUsers.ts
rtk git commit -m "feat(users): add TanStack Query hooks for user management"
```

---

## Task 9: Create/Edit dialog

**Files:**
- Create: `frontend/src/features/users/UserFormDialog.tsx`

- [ ] **Step 1: Write the dialog**

```tsx
import { useEffect, useState } from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Switch } from '@/shared/components/ui/switch';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/shared/components/ui/select';
import { toast } from 'sonner';
import type { ManagedUser, UserRole } from './userApi';
import { useCreateUser, useUpdateUser } from './useUsers';
import { validateCreateMode } from './userForm';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** When provided, the dialog is in edit mode. */
  user?: ManagedUser | null;
}

export function UserFormDialog({ open, onOpenChange, user }: Props) {
  const isEdit = Boolean(user);
  const createMut = useCreateUser();
  const updateMut = useUpdateUser();

  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [role, setRole] = useState<UserRole>('user');
  const [sendInvite, setSendInvite] = useState(false);
  const [password, setPassword] = useState('');

  useEffect(() => {
    if (open) {
      setEmail(user?.email ?? '');
      setDisplayName(user?.displayName ?? '');
      setRole(user?.role ?? 'user');
      setSendInvite(false);
      setPassword('');
    }
  }, [open, user]);

  async function handleSubmit() {
    try {
      if (isEdit && user) {
        await updateMut.mutateAsync({ id: user.id, payload: { display_name: displayName, role } });
        toast.success('อัปเดตผู้ใช้เรียบร้อยแล้ว');
      } else {
        const err = validateCreateMode({ sendInvite, password });
        if (err) { toast.error(err); return; }
        const res = await createMut.mutateAsync({
          email,
          role,
          display_name: displayName || null,
          ...(sendInvite ? { send_invite: true } : { password }),
        });
        if (res.reset_token) {
          toast.message('สร้างผู้ใช้แล้ว — ส่งอีเมลไม่สำเร็จ', { description: `Reset token: ${res.reset_token}` });
        } else {
          toast.success(sendInvite ? 'สร้างผู้ใช้และส่งคำเชิญแล้ว' : 'สร้างผู้ใช้เรียบร้อยแล้ว');
        }
      }
      onOpenChange(false);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'เกิดข้อผิดพลาด');
    }
  }

  const pending = createMut.isPending || updateMut.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? 'แก้ไขผู้ใช้' : 'เพิ่มผู้ใช้ใหม่'}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">อีเมล</Label>
            <Input id="email" type="email" value={email} disabled={isEdit}
              onChange={(e) => setEmail(e.target.value)} />
          </div>

          <div className="space-y-2">
            <Label htmlFor="displayName">ชื่อที่แสดง</Label>
            <Input id="displayName" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
          </div>

          <div className="space-y-2">
            <Label>บทบาท</Label>
            <Select value={role} onValueChange={(v) => setRole(v as UserRole)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="user">ผู้ใช้</SelectItem>
                <SelectItem value="admin">ผู้ดูแลระบบ</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {!isEdit && (
            <>
              <div className="flex items-center justify-between">
                <Label htmlFor="sendInvite">ส่งคำเชิญทางอีเมล</Label>
                <Switch id="sendInvite" checked={sendInvite} onCheckedChange={setSendInvite} />
              </div>
              {!sendInvite && (
                <div className="space-y-2">
                  <Label htmlFor="password">รหัสผ่านเริ่มต้น</Label>
                  <Input id="password" type="password" value={password}
                    onChange={(e) => setPassword(e.target.value)} />
                </div>
              )}
            </>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>ยกเลิก</Button>
          <Button onClick={handleSubmit} disabled={pending}>
            {isEdit ? 'บันทึก' : 'สร้าง'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && rtk npx tsc --noEmit`
Expected: no errors referencing `UserFormDialog.tsx`.

- [ ] **Step 3: Commit**

```bash
rtk git add frontend/src/features/users/UserFormDialog.tsx
rtk git commit -m "feat(users): add create/edit user dialog"
```

---

## Task 10: Activate/Deactivate confirm dialog

**Files:**
- Create: `frontend/src/features/users/DeactivateUserDialog.tsx`

- [ ] **Step 1: Write the dialog**

```tsx
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import { toast } from 'sonner';
import type { ManagedUser } from './userApi';
import { useSetUserActive } from './useUsers';

interface Props {
  user: ManagedUser | null;
  onOpenChange: (open: boolean) => void;
}

export function DeactivateUserDialog({ user, onOpenChange }: Props) {
  const mut = useSetUserActive();
  const deactivating = user?.isActive ?? true;

  async function handleConfirm() {
    if (!user) return;
    try {
      await mut.mutateAsync({ id: user.id, active: !user.isActive });
      toast.success(deactivating ? 'ปิดการใช้งานผู้ใช้แล้ว' : 'เปิดการใช้งานผู้ใช้แล้ว');
      onOpenChange(false);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'เกิดข้อผิดพลาด');
    }
  }

  return (
    <AlertDialog open={Boolean(user)} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            {deactivating ? 'ปิดการใช้งานผู้ใช้?' : 'เปิดการใช้งานผู้ใช้?'}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {user?.email}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>ยกเลิก</AlertDialogCancel>
          <AlertDialogAction onClick={handleConfirm} disabled={mut.isPending}>
            ยืนยัน
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && rtk npx tsc --noEmit`
Expected: no errors referencing `DeactivateUserDialog.tsx`.

- [ ] **Step 3: Commit**

```bash
rtk git add frontend/src/features/users/DeactivateUserDialog.tsx
rtk git commit -m "feat(users): add activate/deactivate confirm dialog"
```

---

## Task 11: Users page

**Files:**
- Create: `frontend/src/features/users/UsersPage.tsx`

- [ ] **Step 1: Write the page**

```tsx
import { useState } from 'react';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/shared/components/ui/table';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Badge } from '@/shared/components/ui/badge';
import { UserPlus } from 'lucide-react';
import { useUsers } from './useUsers';
import type { ManagedUser } from './userApi';
import { UserFormDialog } from './UserFormDialog';
import { DeactivateUserDialog } from './DeactivateUserDialog';

export default function UsersPage() {
  const [search, setSearch] = useState('');
  const { data: users = [], isLoading } = useUsers({ search: search || undefined, status: 'all' });
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ManagedUser | null>(null);
  const [toggling, setToggling] = useState<ManagedUser | null>(null);

  function openCreate() { setEditing(null); setFormOpen(true); }
  function openEdit(u: ManagedUser) { setEditing(u); setFormOpen(true); }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">จัดการผู้ใช้</h1>
        <Button onClick={openCreate}><UserPlus className="h-4 w-4 mr-2" />เพิ่มผู้ใช้</Button>
      </div>

      <Input
        placeholder="ค้นหาอีเมลหรือชื่อ..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-sm"
      />

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>อีเมล</TableHead>
            <TableHead>ชื่อที่แสดง</TableHead>
            <TableHead>บทบาท</TableHead>
            <TableHead>สถานะ</TableHead>
            <TableHead className="text-right">การจัดการ</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading && (
            <TableRow><TableCell colSpan={5}>กำลังโหลด...</TableCell></TableRow>
          )}
          {!isLoading && users.length === 0 && (
            <TableRow><TableCell colSpan={5}>ไม่พบผู้ใช้</TableCell></TableRow>
          )}
          {users.map((u) => (
            <TableRow key={u.id}>
              <TableCell>{u.email}</TableCell>
              <TableCell>{u.displayName}</TableCell>
              <TableCell>
                <Badge variant={u.role === 'admin' ? 'default' : 'secondary'}>
                  {u.role === 'admin' ? 'ผู้ดูแลระบบ' : 'ผู้ใช้'}
                </Badge>
              </TableCell>
              <TableCell>
                <Badge variant={u.isActive ? 'default' : 'outline'}>
                  {u.isActive ? 'ใช้งาน' : 'ปิดใช้งาน'}
                </Badge>
              </TableCell>
              <TableCell className="text-right space-x-2">
                <Button variant="ghost" size="sm" onClick={() => openEdit(u)}>แก้ไข</Button>
                <Button variant="ghost" size="sm" onClick={() => setToggling(u)}>
                  {u.isActive ? 'ปิดใช้งาน' : 'เปิดใช้งาน'}
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <UserFormDialog open={formOpen} onOpenChange={setFormOpen} user={editing} />
      <DeactivateUserDialog user={toggling} onOpenChange={(open) => { if (!open) setToggling(null); }} />
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && rtk npx tsc --noEmit`
Expected: no errors referencing `UsersPage.tsx`.

- [ ] **Step 3: Commit**

```bash
rtk git add frontend/src/features/users/UsersPage.tsx
rtk git commit -m "feat(users): add Users admin page"
```

---

## Task 12: Wire route + sidebar nav

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/shared/components/layout/AppSidebar.tsx`

- [ ] **Step 1: Import the page in `App.tsx`**

Find:

```tsx
import SettingsPage from "@/features/settings/SettingsPage";
```

Add immediately after:

```tsx
import UsersPage from "@/features/users/UsersPage";
```

- [ ] **Step 2: Add the route in `App.tsx`**

Find:

```tsx
                <Route path="/settings" element={<SettingsPage />} />
```

Add immediately after:

```tsx
                <Route path="/users" element={<UsersPage />} />
```

- [ ] **Step 3: Add the admin nav entry in `AppSidebar.tsx`**

Find the `adminItems` array:

```tsx
const adminItems = [
  { title: "ตั้งค่าระบบ", url: "/settings", icon: Settings },
];
```

Replace with (adds Users; uses the `Users` lucide icon):

```tsx
const adminItems = [
  { title: "จัดการผู้ใช้", url: "/users", icon: Users },
  { title: "ตั้งค่าระบบ", url: "/settings", icon: Settings },
];
```

- [ ] **Step 4: Ensure the `Users` icon is imported in `AppSidebar.tsx`**

Find the `lucide-react` import line near the top of the file (it imports icons like `Settings`, `Building2`, etc.). Add `Users` to that import list. Example:

```tsx
import { ..., Settings, Users } from "lucide-react";
```

(Keep the existing icons; only add `Users`.)

- [ ] **Step 5: Type-check the whole frontend**

Run: `cd frontend && rtk npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Lint**

Run: `cd frontend && rtk lint`
Expected: no new violations in `features/users/` or the modified files.

- [ ] **Step 7: Commit**

```bash
rtk git add frontend/src/App.tsx frontend/src/shared/components/layout/AppSidebar.tsx
rtk git commit -m "feat(users): wire /users route and admin sidebar nav"
```

---

## Task 13: Full verification

- [ ] **Step 1: Backend tests**

Run: `cd backend && uv run pytest -q`
Expected: all pass.

- [ ] **Step 2: Frontend unit tests**

Run: `cd frontend && rtk npx vitest run src/features/users`
Expected: all pass.

- [ ] **Step 3: Frontend type + lint**

Run: `cd frontend && rtk npx tsc --noEmit && rtk lint`
Expected: clean.

- [ ] **Step 4: Manual smoke (optional, requires running stack)**

Bring up the stack (`docker compose up` or the project's run command), log in as an admin, open the **จัดการผู้ใช้** nav item, and verify: list loads, create-with-password works, create-with-invite shows the invite toast, edit role works, deactivate/activate toggles status, and self-demote/last-admin actions are rejected with a toast.

- [ ] **Step 5: Finish the branch**

Use the `superpowers:finishing-a-development-branch` skill to decide how to integrate (PR vs merge), then open a PR describing the feature and how it was tested.

---

## Notes for the implementer

- **RTK:** Prefix shell commands with `rtk` per project convention (e.g. `rtk git`, `rtk npx`, `rtk lint`).
- **Linter:** The CLAUDE.md mentions `golangci-lint`/`gofmt`, but this is a Python + TypeScript codebase — there is no Go here. Use the Python linter configured in `backend/pyproject.toml` (ruff if present) and the frontend `lint` script. Invoke `/use-modern-go` only if Go code is ever added (it won't be in this plan).
- **Bilingual messages:** User-facing strings follow the existing Thai convention seen in `auth.py`.
- **No migration:** The `users` table already has `role`, `is_active`, `reset_token`, `reset_token_expires` — do not generate an aerich migration.
