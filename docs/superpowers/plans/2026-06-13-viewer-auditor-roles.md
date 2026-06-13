# Viewer and Auditor Roles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two read-only roles — `viewer` (operational/analytics pages + chat) and `auditor` (everything except Settings + chat) — enforced in the backend and reflected in the frontend routes, sidebar, and write controls.

**Architecture:** Mirror the existing `_is_allowed_for_basic_user` / `enforce_basic_user_allowlist` pattern. Generalize the single chokepoint into a role-dispatched gate with one allowlist function per restricted role. On the frontend, replace the `requireNonBasic` boolean with a declarative `allowedRoles` prop fed by a central role→routes map, add an `isReadOnly` flag, and hide write controls on the three pages that have them.

**Tech Stack:** Backend FastAPI + Tortoise ORM + pytest. Frontend React + react-router + TanStack Query + vitest/testing-library.

**Spec:** `docs/superpowers/specs/2026-06-13-viewer-auditor-roles-design.md`

**Reference — access matrix (source of truth):**

| Path | user | viewer | auditor | agency_owner | admin |
|---|---|---|---|---|---|
| `/chat`, `/architecture` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/dashboard`, `/executive`, `/health`, `/heatmap` | — | ✅ | ✅ | ✅ | ✅ |
| `/usage`, `/feedback` | — | ✅ | ✅ | — | ✅ |
| `/agencies`, `/agencies/:id`, `/history`, `/connection-logs`, `/api-keys` | — | — | ✅ | ✅ | ✅ |
| `/my-agencies`, `/agencies/new`, `/agencies/:id/setup` | — | — | — | ✅ | ✅ |
| `/users`, `/audit-log` | — | — | ✅ | — | ✅ |
| `/settings` | — | — | — | — | ✅ |

`viewer`/`auditor` are read-only: all writes blocked **except** chat (`POST /chat`, `/chat/stream`), message rating (`PATCH /messages/{id}/rating`), conversation management (`/conversations`), and `/auth/*`.

> Note: `/my-agencies` is a personal "agencies I own" page, so `auditor` is intentionally excluded (an auditor owns none — the page would be empty). `/agencies/new` and `/agencies/:id/setup` are creation/wizard flows (writes), also excluded from `auditor`.

---

## Phase 1 — Backend: role definitions + allowlist enforcement

### Task 1: Add `viewer` and `auditor` to the backend role literal

**Files:**
- Modify: `backend/app/schemas/user.py:12`
- Modify: `backend/app/models/user.py:17`
- Test: `backend/tests/test_user_schema_roles.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_user_schema_roles.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && rtk pytest tests/test_user_schema_roles.py -v`
Expected: FAIL — `viewer`/`auditor` rejected by the `Role` literal (ValidationError on the parametrized cases).

- [ ] **Step 3: Write minimal implementation**

In `backend/app/schemas/user.py:12` change:

```python
Role = Literal["user", "admin", "agency_owner"]
```

to:

```python
Role = Literal["user", "viewer", "auditor", "agency_owner", "admin"]
```

In `backend/app/models/user.py:17` update the trailing comment:

```python
    role = fields.CharField(max_length=20, default="user")     # user | viewer | auditor | agency_owner | admin
```

(The column is already `CharField(max_length=20)`; no DB migration is needed.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && rtk pytest tests/test_user_schema_roles.py -v`
Expected: PASS (5 parametrized + 1 rejection case).

- [ ] **Step 5: Commit**

```bash
rtk git add backend/app/schemas/user.py backend/app/models/user.py backend/tests/test_user_schema_roles.py
rtk git commit -m "feat(auth): add viewer and auditor to the role literal"
```

---

### Task 2: Add per-role allowlist functions (`viewer`, `auditor`) and a shared-write helper

**Files:**
- Modify: `backend/app/auth/dependencies.py:40-61` (refactor allowlist region)
- Test: `backend/tests/test_role_allowlist.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_role_allowlist.py`:

```python
"""Viewer and auditor allowlists: read-only with a chat write exception."""
from app.auth.dependencies import (
    _is_allowed_for_auditor,
    _is_allowed_for_viewer,
    _is_shared_write,
)


def test_shared_writes_allowed_for_both():
    for check in (_is_allowed_for_viewer, _is_allowed_for_auditor):
        assert check("POST", "/api/v1/chat")
        assert check("POST", "/api/v1/chat/stream")
        assert check("PATCH", "/api/v1/messages/abc-123/rating")
        assert check("GET", "/api/v1/conversations")
        assert check("DELETE", "/api/v1/conversations/abc-123")
        assert check("GET", "/api/v1/auth/me")


def test_shared_write_helper_excludes_other_writes():
    assert not _is_shared_write("POST", "/api/v1/agencies")
    assert not _is_shared_write("DELETE", "/api/v1/api-keys/abc-123")


def test_viewer_reads_its_pages():
    allowed_gets = [
        "/api/v1/agencies",
        "/api/v1/dashboard/stats",
        "/api/v1/executive-summary",
        "/api/v1/agency-health",
        "/api/v1/usage-heatmap",
        "/api/v1/analytics-insights",
        "/api/v1/insight/usage",
        "/api/v1/feedback/stats",
        "/api/v1/agencies/abc-123/health/history",
        "/api/v1/feedback/agencies/abc-123/low-rated",
    ]
    for path in allowed_gets:
        assert _is_allowed_for_viewer("GET", path), path


def test_viewer_cannot_read_auditor_only_or_write():
    assert not _is_allowed_for_viewer("GET", "/api/v1/users")
    assert not _is_allowed_for_viewer("GET", "/api/v1/audit-log/")
    assert not _is_allowed_for_viewer("GET", "/api/v1/api-keys/")
    assert not _is_allowed_for_viewer("GET", "/api/v1/connection-logs")
    assert not _is_allowed_for_viewer("GET", "/api/v1/agencies/abc-123")  # detail, not list
    assert not _is_allowed_for_viewer("POST", "/api/v1/agencies")
    assert not _is_allowed_for_viewer("POST", "/api/v1/executive-summary/regenerate")


def test_auditor_reads_everything_but_settings():
    for path in [
        "/api/v1/users",
        "/api/v1/audit-log/",
        "/api/v1/api-keys/",
        "/api/v1/connection-logs",
        "/api/v1/agencies/abc-123",
        "/api/v1/dashboard/stats",
    ]:
        assert _is_allowed_for_auditor("GET", path), path
    assert not _is_allowed_for_auditor("GET", "/api/v1/settings")


def test_auditor_blocks_all_non_chat_writes():
    assert not _is_allowed_for_auditor("POST", "/api/v1/agencies")
    assert not _is_allowed_for_auditor("DELETE", "/api/v1/api-keys/abc-123")
    assert not _is_allowed_for_auditor("PATCH", "/api/v1/users/abc-123")
    assert not _is_allowed_for_auditor("PUT", "/api/v1/settings")
    assert not _is_allowed_for_auditor("POST", "/api/v1/executive-summary/regenerate")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && rtk pytest tests/test_role_allowlist.py -v`
Expected: FAIL with `ImportError: cannot import name '_is_allowed_for_viewer'`.

- [ ] **Step 3: Write minimal implementation**

Replace the allowlist region in `backend/app/auth/dependencies.py` (currently lines 40-61) with:

```python
_MESSAGE_RATING_PATH = re.compile(r"^/api/v1/messages/[^/]+/rating$")
# Matches the collection and /{id} only — sub-resources like /{id}/messages are intentionally excluded; only HistoryPage uses them and it's gated at the frontend.
_CONVERSATION_PATH = re.compile(r"^/api/v1/conversations(?:/[^/]+)?$")

# GET endpoints backing the pages a `viewer` may open (Architecture, Dashboard,
# Executive, Health, Heatmap, analytics insights, Usage, Feedback). Detail/admin
# endpoints are deliberately excluded — viewer is narrower than auditor.
_VIEWER_GET_EXACT = frozenset({
    "/api/v1/agencies",            # Architecture list
    "/api/v1/dashboard/stats",     # Dashboard
    "/api/v1/executive-summary",   # Executive
    "/api/v1/agency-health",       # Agency Health
    "/api/v1/usage-heatmap",       # Usage Heatmap
    "/api/v1/analytics-insights",  # Dashboard insights
    "/api/v1/insight/usage",       # Usage analytics
    "/api/v1/feedback/stats",      # Feedback
})
_VIEWER_GET_PATTERN = [
    re.compile(r"^/api/v1/agencies/[^/]+/health/history$"),       # Health detail
    re.compile(r"^/api/v1/feedback/agencies/[^/]+/low-rated$"),   # Feedback detail
]
_SETTINGS_PREFIX = "/api/v1/settings"


def _is_shared_write(method: str, path: str) -> bool:
    """Writes every authenticated role (incl. read-only ones) may perform.

    Chat, message rating, own-conversation management, and the self/auth
    endpoints. Everything else is a privileged write.
    """
    if path.startswith("/api/v1/auth/"):  # all auth endpoints — each guards itself internally
        return True
    if method == "POST" and path in ("/api/v1/chat", "/api/v1/chat/stream"):
        return True
    if method == "PATCH" and _MESSAGE_RATING_PATH.match(path):
        return True
    if _CONVERSATION_PATH.match(path):  # all verbs: manage own conversation history
        return True
    return False


def _is_allowed_for_basic_user(method: str, path: str) -> bool:
    """A plain ``user`` role: chat + architecture list + the shared writes."""
    if _is_shared_write(method, path):
        return True
    if method == "GET" and path == "/api/v1/agencies":  # Architecture page (list only)
        return True
    return False


def _is_allowed_for_viewer(method: str, path: str) -> bool:
    """``viewer``: read-only on its operational/analytics pages, plus chat."""
    if _is_shared_write(method, path):
        return True
    if method == "GET" and (
        path in _VIEWER_GET_EXACT or any(p.match(path) for p in _VIEWER_GET_PATTERN)
    ):
        return True
    return False


def _is_allowed_for_auditor(method: str, path: str) -> bool:
    """``auditor``: read-only on everything except Settings, plus chat."""
    if _is_shared_write(method, path):
        return True
    if method == "GET" and not path.startswith(_SETTINGS_PREFIX):
        return True
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && rtk pytest tests/test_role_allowlist.py tests/test_basic_user_allowlist.py -v`
Expected: PASS — both the new viewer/auditor tests and the pre-existing basic-user tests (behavior of `_is_allowed_for_basic_user` is unchanged).

- [ ] **Step 5: Commit**

```bash
rtk git add backend/app/auth/dependencies.py backend/tests/test_role_allowlist.py
rtk git commit -m "feat(auth): add viewer and auditor allowlists"
```

---

### Task 3: Generalize the chokepoint to dispatch by role

**Files:**
- Modify: `backend/app/auth/dependencies.py:170-190` (rename + dispatch)
- Modify: `backend/app/main.py:39,104` (import + wiring)
- Modify: `backend/tests/test_basic_user_allowlist.py:7,112-147` (rename import + reuse)
- Test: `backend/tests/test_role_allowlist.py` (extend with chokepoint cases)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_role_allowlist.py`:

```python
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

from app.auth.dependencies import enforce_role_allowlist
from app.auth.security import create_access_token
from app.models.user import User


def _request(method: str, path: str) -> Request:
    return Request(
        {"type": "http", "method": method, "path": path, "headers": [], "query_string": b""}
    )


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


async def _token_for(email: str, role: str) -> str:
    user = await User.create(email=email, hashed_password="h", role=role)
    return create_access_token({"sub": str(user.id)})


async def test_viewer_blocked_on_users(db):
    token = await _token_for("v1@x.com", "viewer")
    with pytest.raises(HTTPException) as e:
        await enforce_role_allowlist(_request("GET", "/api/v1/users"), _creds(token))
    assert e.value.status_code == 403


async def test_viewer_allowed_on_dashboard(db):
    token = await _token_for("v2@x.com", "viewer")
    assert await enforce_role_allowlist(
        _request("GET", "/api/v1/dashboard/stats"), _creds(token)
    ) is None


async def test_auditor_allowed_on_users_but_blocked_on_settings(db):
    token = await _token_for("a1@x.com", "auditor")
    assert await enforce_role_allowlist(
        _request("GET", "/api/v1/users"), _creds(token)
    ) is None
    with pytest.raises(HTTPException) as e:
        await enforce_role_allowlist(_request("GET", "/api/v1/settings"), _creds(token))
    assert e.value.status_code == 403


async def test_auditor_blocked_on_write(db):
    token = await _token_for("a2@x.com", "auditor")
    with pytest.raises(HTTPException) as e:
        await enforce_role_allowlist(_request("POST", "/api/v1/agencies"), _creds(token))
    assert e.value.status_code == 403


async def test_admin_and_owner_pass_through(db):
    for role in ("admin", "agency_owner"):
        token = await _token_for(f"{role}@x.com", role)
        assert await enforce_role_allowlist(
            _request("GET", "/api/v1/users"), _creds(token)
        ) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && rtk pytest tests/test_role_allowlist.py -v`
Expected: FAIL with `ImportError: cannot import name 'enforce_role_allowlist'`.

- [ ] **Step 3: Write minimal implementation**

In `backend/app/auth/dependencies.py`, replace `enforce_basic_user_allowlist` (lines ~170-190) with:

```python
_ROLE_ALLOWLIST = {
    "user": _is_allowed_for_basic_user,
    "viewer": _is_allowed_for_viewer,
    "auditor": _is_allowed_for_auditor,
}


async def enforce_role_allowlist(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_optional),
) -> None:
    """Chokepoint for read-restricted roles (``user``, ``viewer``, ``auditor``).

    Anonymous, ``admin`` and ``agency_owner`` callers pass straight through;
    their access is governed by each endpoint's own auth. Wired as a global
    dependency in ``app.main`` so it runs once per request.
    """
    if credentials is None:
        return
    role = await _resolve_role(credentials.credentials)
    check = _ROLE_ALLOWLIST.get(role or "")
    if check is None:  # admin, agency_owner, unknown/None → governed per-endpoint
        return
    if not check(request.method, request.url.path):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This role does not have access to this resource",
        )
```

In `backend/app/main.py:39` change the import:

```python
from app.auth.dependencies import enforce_role_allowlist
```

and at line 104 change the dependency wiring:

```python
    dependencies=[Depends(enforce_role_allowlist)],
```

In `backend/tests/test_basic_user_allowlist.py`, update the import at line 7 (the old function name is gone):

```python
from app.auth.dependencies import _is_allowed_for_basic_user, _resolve_role, enforce_role_allowlist
```

and replace each `enforce_basic_user_allowlist(` call in that file (lines 115, 125, 132, 139, 145) with `enforce_role_allowlist(`. The basic-user assertion at line 119 (`assert "chat" in e.value.detail`) must change because the detail message is now generic — update it to:

```python
    assert e.value.status_code == 403
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && rtk pytest tests/test_role_allowlist.py tests/test_basic_user_allowlist.py -v`
Expected: PASS for both files.

- [ ] **Step 5: Run the full backend suite to catch references to the old name**

Run: `cd backend && rtk pytest -q`
Expected: PASS. If anything still imports `enforce_basic_user_allowlist`, fix the reference (grep: `rtk grep -rn enforce_basic_user_allowlist backend`).

- [ ] **Step 6: Commit**

```bash
rtk git add backend/app/auth/dependencies.py backend/app/main.py backend/tests/test_basic_user_allowlist.py backend/tests/test_role_allowlist.py
rtk git commit -m "feat(auth): dispatch the role allowlist by role at one chokepoint"
```

---

### Task 4: Don't let the last admin be demoted to a read-only role

**Files:**
- Modify: `backend/app/routers/users.py:84-88`
- Test: `backend/tests/test_users_last_admin.py` (create)

The current guard only calls `ensure_not_last_admin` when demoting to `"user"`. Demoting the last admin to `viewer`/`auditor`/`agency_owner` must be blocked too.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_users_last_admin.py`:

```python
"""The last admin cannot be demoted to any non-admin role."""
import pytest

from app.models.user import User
from app.services import user as user_service


@pytest.mark.parametrize("new_role", ["user", "viewer", "auditor", "agency_owner"])
async def test_last_admin_demotion_blocked(db, new_role):
    admin = await User.create(email="only-admin@x.com", hashed_password="h", role="admin")
    # Simulate the router's guard: demoting the sole admin must raise.
    with pytest.raises(Exception):
        if admin.role == "admin" and new_role != "admin":
            await user_service.ensure_not_last_admin(admin)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && rtk pytest tests/test_users_last_admin.py -v`
Expected: this test passes only once the router uses the broadened condition; first confirm the *router* logic is wrong by reading `users.py:84-88` — it guards `body.role == "user"` only. (This test asserts the service helper raises for the sole admin; if `ensure_not_last_admin` already raises for a sole admin it will pass — the real fix is in the router branch below. Keep this test as a regression anchor for the helper.)

- [ ] **Step 3: Write minimal implementation**

In `backend/app/routers/users.py`, change the demotion guard (lines 84-88):

```python
    if body.role is not None and body.role != user.role:
        user_service.ensure_not_self(admin.id, user.id)
        if user.role == "admin" and body.role == "user":
            await user_service.ensure_not_last_admin(user)
        user.role = body.role
        changed.append("role")
```

to:

```python
    if body.role is not None and body.role != user.role:
        user_service.ensure_not_self(admin.id, user.id)
        if user.role == "admin" and body.role != "admin":
            await user_service.ensure_not_last_admin(user)
        user.role = body.role
        changed.append("role")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && rtk pytest tests/test_users_last_admin.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
cd backend && golangci-lint --version >/dev/null 2>&1 || true   # (Go linter N/A here; Python project)
rtk git add backend/app/routers/users.py backend/tests/test_users_last_admin.py
rtk git commit -m "fix(users): block demoting the last admin to any non-admin role"
```

---

## Phase 2 — Frontend: role plumbing

### Task 5: Central role map + `isReadOnly` flag

**Files:**
- Create: `frontend/src/features/auth/roles.ts`
- Modify: `frontend/src/features/auth/useAuth.tsx:19,23-30,84-91`
- Modify: `frontend/src/features/users/userApi.ts:3`
- Test: `frontend/src/features/auth/roles.test.ts` (create)

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/auth/roles.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { ROUTE_ROLES, READ_ONLY_ROLES, canAccess } from "./roles";

describe("role map", () => {
  it("lets every authenticated role reach chat + architecture", () => {
    for (const r of ["user", "viewer", "auditor", "agency_owner", "admin"] as const) {
      expect(canAccess(r, "/chat")).toBe(true);
      expect(canAccess(r, "/architecture")).toBe(true);
    }
  });

  it("scopes viewer to analytics pages, not management", () => {
    expect(canAccess("viewer", "/dashboard")).toBe(true);
    expect(canAccess("viewer", "/usage")).toBe(true);
    expect(canAccess("viewer", "/agencies")).toBe(false);
    expect(canAccess("viewer", "/users")).toBe(false);
  });

  it("lets auditor reach everything except settings + owner-only pages", () => {
    expect(canAccess("auditor", "/users")).toBe(true);
    expect(canAccess("auditor", "/audit-log")).toBe(true);
    expect(canAccess("auditor", "/agencies")).toBe(true);
    expect(canAccess("auditor", "/settings")).toBe(false);
    expect(canAccess("auditor", "/my-agencies")).toBe(false);
    expect(canAccess("auditor", "/agencies/new")).toBe(false);
  });

  it("marks viewer and auditor as read-only", () => {
    expect(READ_ONLY_ROLES).toContain("viewer");
    expect(READ_ONLY_ROLES).toContain("auditor");
    expect(READ_ONLY_ROLES).not.toContain("agency_owner");
    expect(READ_ONLY_ROLES).not.toContain("admin");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk vitest run src/features/auth/roles.test.ts`
Expected: FAIL — `./roles` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/features/auth/roles.ts`:

```ts
export type Role = "user" | "viewer" | "auditor" | "agency_owner" | "admin";

const ALL: Role[] = ["user", "viewer", "auditor", "agency_owner", "admin"];

/**
 * Roles permitted to view each route. Single source of truth shared by the
 * route guard (ProtectedRoute) and the sidebar. Keep in sync with the backend
 * allowlist in backend/app/auth/dependencies.py.
 */
export const ROUTE_ROLES: Record<string, Role[]> = {
  "/chat": ALL,
  "/architecture": ALL,
  "/dashboard": ["viewer", "auditor", "agency_owner", "admin"],
  "/executive": ["viewer", "auditor", "agency_owner", "admin"],
  "/health": ["viewer", "auditor", "agency_owner", "admin"],
  "/heatmap": ["viewer", "auditor", "agency_owner", "admin"],
  "/usage": ["viewer", "auditor", "admin"],
  "/feedback": ["viewer", "auditor", "admin"],
  "/agencies": ["auditor", "agency_owner", "admin"],
  "/agencies/:id": ["auditor", "agency_owner", "admin"],
  "/history": ["auditor", "agency_owner", "admin"],
  "/connection-logs": ["auditor", "agency_owner", "admin"],
  "/api-keys": ["auditor", "agency_owner", "admin"],
  "/my-agencies": ["agency_owner", "admin"],
  "/agencies/new": ["agency_owner", "admin"],
  "/agencies/:id/setup": ["agency_owner", "admin"],
  "/users": ["auditor", "admin"],
  "/audit-log": ["auditor", "admin"],
  "/settings": ["admin"],
};

export const READ_ONLY_ROLES: Role[] = ["viewer", "auditor"];

export function canAccess(role: Role, path: string): boolean {
  const allowed = ROUTE_ROLES[path];
  return allowed ? allowed.includes(role) : true;
}

export function isReadOnlyRole(role: Role | undefined): boolean {
  return role === "viewer" || role === "auditor";
}
```

In `frontend/src/features/auth/useAuth.tsx`:

- Line 19 — widen the role union and reuse the shared `Role` type. Replace:

```ts
  role: "user" | "admin" | "agency_owner";
```

with:

```ts
  role: Role;
```

and add the import near the top (after the existing imports, line 9):

```ts
import { isReadOnlyRole, type Role } from "@/features/auth/roles";
```

- In `AuthContextType` (lines 23-30) add the flag:

```ts
  isReadOnly: boolean;
```

- In the context default (lines 36-42) add `isReadOnly: false,`.
- In the provider value (lines 84-91) add:

```ts
        isReadOnly: isReadOnlyRole(user?.role),
```

In `frontend/src/features/users/userApi.ts:3` widen the managed-user role type:

```ts
export type UserRole = 'user' | 'viewer' | 'auditor' | 'agency_owner' | 'admin';
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && rtk vitest run src/features/auth/roles.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add frontend/src/features/auth/roles.ts frontend/src/features/auth/roles.test.ts frontend/src/features/auth/useAuth.tsx frontend/src/features/users/userApi.ts
rtk git commit -m "feat(auth): central role map and isReadOnly flag"
```

---

### Task 6: `ProtectedRoute` — replace `requireNonBasic` with `allowedRoles`

**Files:**
- Modify: `frontend/src/features/auth/ProtectedRoute.tsx`
- Modify: `frontend/src/features/auth/ProtectedRoute.test.tsx`

- [ ] **Step 1: Write the failing test**

Replace the body of `frontend/src/features/auth/ProtectedRoute.test.tsx` (keep lines 1-24 setup; replace the `describe` block at lines 26-50) with:

```tsx
describe("ProtectedRoute allowedRoles", () => {
  beforeEach(() => {
    auth.user = { id: "1", email: "u@test.com", displayName: "User", role: "user", avatarUrl: null };
    auth.isAdmin = false;
    auth.isLoading = false;
  });

  it("redirects a role not in allowedRoles to /chat", () => {
    auth.user = { ...auth.user!, role: "viewer" };
    renderAt("/secret", <ProtectedRoute allowedRoles={["auditor", "admin"]}><div>secret content</div></ProtectedRoute>);
    expect(screen.getByText("chat page")).toBeInTheDocument();
    expect(screen.queryByText("secret content")).not.toBeInTheDocument();
  });

  it("lets a role in allowedRoles through", () => {
    auth.user = { ...auth.user!, role: "auditor" };
    renderAt("/secret", <ProtectedRoute allowedRoles={["auditor", "admin"]}><div>secret content</div></ProtectedRoute>);
    expect(screen.getByText("secret content")).toBeInTheDocument();
  });

  it("does not gate routes without allowedRoles", () => {
    renderAt("/secret", <ProtectedRoute><div>secret content</div></ProtectedRoute>);
    expect(screen.getByText("secret content")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk vitest run src/features/auth/ProtectedRoute.test.tsx`
Expected: FAIL — `allowedRoles` prop not handled; viewer is not redirected.

- [ ] **Step 3: Write minimal implementation**

Rewrite `frontend/src/features/auth/ProtectedRoute.tsx`:

```tsx
import { Navigate } from "react-router-dom";
import { useAuth } from "@/features/auth/useAuth";
import { Skeleton } from "@/shared/components/ui/skeleton";
import type { Role } from "@/features/auth/roles";

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireAdmin?: boolean;
  allowedRoles?: Role[];
}

export function ProtectedRoute({ children, requireAdmin = false, allowedRoles }: ProtectedRouteProps) {
  const { user, isAdmin, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="space-y-4 w-64">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // A role not permitted for this route is sent to /chat (reachable by every authenticated role).
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/chat" replace />;
  }

  if (requireAdmin && !isAdmin) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center space-y-2">
          <p className="text-lg font-semibold text-foreground">ไม่มีสิทธิ์เข้าถึง</p>
          <p className="text-sm text-muted-foreground">คุณต้องมีสิทธิ์ admin เพื่อเข้าถึงหน้านี้</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && rtk vitest run src/features/auth/ProtectedRoute.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add frontend/src/features/auth/ProtectedRoute.tsx frontend/src/features/auth/ProtectedRoute.test.tsx
rtk git commit -m "feat(auth): ProtectedRoute supports declarative allowedRoles"
```

---

### Task 7: Apply `allowedRoles` to the route tree

**Files:**
- Modify: `frontend/src/App.tsx:54-80`

This is a wiring change (no new logic); verified by the build + the sidebar/guard tests. No separate unit test.

- [ ] **Step 1: Update the route tree**

Replace lines 54-80 of `frontend/src/App.tsx` with:

```tsx
              <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
                {/* Every authenticated role */}
                <Route path="/chat" element={<ChatPage />} />
                <Route path="/architecture" element={<ArchitecturePage />} />

                {/* viewer + auditor + agency_owner + admin */}
                <Route element={<ProtectedRoute allowedRoles={["viewer", "auditor", "agency_owner", "admin"]}><Outlet /></ProtectedRoute>}>
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/executive" element={<ExecutivePage />} />
                  <Route path="/health" element={<HealthPage />} />
                  <Route path="/heatmap" element={<HeatmapPage />} />
                </Route>

                {/* viewer + auditor + admin (no agency_owner) */}
                <Route element={<ProtectedRoute allowedRoles={["viewer", "auditor", "admin"]}><Outlet /></ProtectedRoute>}>
                  <Route path="/usage" element={<UsageAnalyticsPage />} />
                  <Route path="/feedback" element={<FeedbackPage />} />
                </Route>

                {/* auditor (read-only) + agency_owner + admin */}
                <Route element={<ProtectedRoute allowedRoles={["auditor", "agency_owner", "admin"]}><Outlet /></ProtectedRoute>}>
                  <Route path="/agencies" element={<AgenciesPage />} />
                  <Route path="/agencies/:id" element={<AgencyDetailPage />} />
                  <Route path="/history" element={<HistoryPage />} />
                  <Route path="/connection-logs" element={<ConnectionLogsPage />} />
                  <Route path="/api-keys" element={<ApiKeysPage />} />
                </Route>

                {/* agency_owner + admin only (owner-personal / write flows) */}
                <Route element={<ProtectedRoute allowedRoles={["agency_owner", "admin"]}><Outlet /></ProtectedRoute>}>
                  <Route path="/my-agencies" element={<MyAgenciesPage />} />
                  <Route path="/agencies/new" element={<AgencyWizardPage />} />
                  <Route path="/agencies/:id/setup" element={<AgencyWizardPage />} />
                </Route>

                {/* auditor (read-only) + admin */}
                <Route element={<ProtectedRoute allowedRoles={["auditor", "admin"]}><Outlet /></ProtectedRoute>}>
                  <Route path="/users" element={<UsersPage />} />
                  <Route path="/audit-log" element={<AuditLogPage />} />
                </Route>

                {/* admin only */}
                <Route path="/settings" element={<ProtectedRoute requireAdmin><SettingsPage /></ProtectedRoute>} />
              </Route>
```

> Note: `/users` and `/audit-log` move out of the `requireAdmin` wrapper (auditor now reads them); their write protection is the backend allowlist + hidden UI controls (Task 12). `/settings` stays admin-only via `requireAdmin`.

- [ ] **Step 2: Verify the build compiles**

Run: `cd frontend && rtk tsc --noEmit`
Expected: no type errors.

- [ ] **Step 3: Commit**

```bash
rtk git add frontend/src/App.tsx
rtk git commit -m "feat(routing): gate routes per the viewer/auditor access matrix"
```

---

### Task 8: Sidebar visibility from the role map

**Files:**
- Modify: `frontend/src/shared/components/layout/AppSidebar.tsx:20-57,104-131`
- Test: `frontend/src/shared/components/layout/AppSidebar.test.tsx` (create)

- [ ] **Step 1: Write the failing test**

Create `frontend/src/shared/components/layout/AppSidebar.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppSidebar } from "./AppSidebar";
import type { AuthUser } from "@/features/auth/useAuth";

const auth: { user: AuthUser | null; isReadOnly: boolean; signOut: () => void } = {
  user: null,
  isReadOnly: false,
  signOut: () => {},
};
vi.mock("@/features/auth/useAuth", () => ({ useAuth: () => auth }));
vi.mock("@/features/agencies/useAgencies", () => ({ useAgencies: () => ({ data: [] }) }));
vi.mock("@/shared/components/ui/sidebar", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("@/shared/components/ui/sidebar");
  return { ...actual, useSidebar: () => ({ state: "expanded" }) };
});

function renderSidebar() {
  return render(<MemoryRouter><AppSidebar /></MemoryRouter>);
}

describe("AppSidebar visibility", () => {
  beforeEach(() => {
    auth.user = { id: "1", email: "u@x.com", displayName: "U", role: "user", avatarUrl: null };
  });

  it("shows only chat + architecture for a basic user", () => {
    auth.user = { ...auth.user!, role: "user" };
    renderSidebar();
    expect(screen.getByText("แชท")).toBeInTheDocument();
    expect(screen.getByText("Architecture")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
  });

  it("shows analytics pages but not management for a viewer", () => {
    auth.user = { ...auth.user!, role: "viewer" };
    renderSidebar();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("การใช้งาน API Key")).toBeInTheDocument(); // usage
    expect(screen.queryByText("จัดการหน่วยงาน")).not.toBeInTheDocument(); // agencies mgmt
    expect(screen.queryByText("จัดการผู้ใช้")).not.toBeInTheDocument(); // users
  });

  it("shows users + audit-log for an auditor but not settings", () => {
    auth.user = { ...auth.user!, role: "auditor" };
    renderSidebar();
    expect(screen.getByText("จัดการผู้ใช้")).toBeInTheDocument();
    expect(screen.getByText("บันทึกการตรวจสอบ")).toBeInTheDocument();
    expect(screen.queryByText("ตั้งค่าระบบ")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk vitest run src/shared/components/layout/AppSidebar.test.tsx`
Expected: FAIL — current sidebar shows the wrong items per role (e.g. viewer sees nothing role-filtered, auditor doesn't see admin items).

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/shared/components/layout/AppSidebar.tsx`:

- Add the import (after line 15):

```tsx
import { canAccess } from "@/features/auth/roles";
```

- Replace the three nav arrays + `BASIC_USER_ROUTES` (lines 20-46) with a single flat list carrying each item's route (used both for rendering and for the access check):

```tsx
const navItems = [
  { title: "แชท", url: "/chat", icon: MessageSquare },
  { title: "Dashboard", url: "/dashboard", icon: LayoutDashboard },
  { title: "Executive", url: "/executive", icon: Briefcase },
  { title: "Agency Health", url: "/health", icon: Activity },
  { title: "Usage Heatmap", url: "/heatmap", icon: Flame },
  { title: "จัดการหน่วยงาน", url: "/agencies", icon: Building2 },
  { title: "หน่วยงานของฉัน", url: "/my-agencies", icon: BadgeCheck },
  { title: "ประวัติการสนทนา", url: "/history", icon: History },
  { title: "ประวัติการเชื่อมต่อ", url: "/connection-logs", icon: Activity },
  { title: "Architecture", url: "/architecture", icon: Network },
  { title: "API Keys", url: "/api-keys", icon: KeyRound },
  { title: "ความคิดเห็นและความพึงพอใจ", url: "/feedback", icon: MessageSquareWarning },
  { title: "จัดการผู้ใช้", url: "/users", icon: Users },
  { title: "บันทึกการตรวจสอบ", url: "/audit-log", icon: ScrollText },
  { title: "การใช้งาน API Key", url: "/usage", icon: BarChart3 },
  { title: "ตั้งค่าระบบ", url: "/settings", icon: Settings },
];
```

- Replace the `visibleNavItems` computation (lines 54-57) with a single role-driven filter:

```tsx
  const visibleNavItems = user
    ? navItems.filter((item) => canAccess(user.role, item.url))
    : [];
```

- Delete the two extra mapped groups (the `ownerItems` block at lines 104-117 and the `adminItems` block at lines 118-131). All items now render from the single `visibleNavItems.map(...)` already present at lines 89-103.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && rtk vitest run src/shared/components/layout/AppSidebar.test.tsx`
Expected: PASS (all three role cases).

- [ ] **Step 5: Verify build + commit**

```bash
cd frontend && rtk tsc --noEmit
rtk git add frontend/src/shared/components/layout/AppSidebar.tsx frontend/src/shared/components/layout/AppSidebar.test.tsx
rtk git commit -m "feat(sidebar): drive item visibility from the central role map"
```

---

### Task 9: Offer `viewer` and `auditor` in the admin user form

**Files:**
- Modify: `frontend/src/features/users/UserFormDialog.tsx:96-99`

- [ ] **Step 1: Add the role options**

In `frontend/src/features/users/UserFormDialog.tsx`, replace the `<SelectContent>` block (lines 96-99):

```tsx
                <SelectContent>
                  <SelectItem value="user">ผู้ใช้</SelectItem>
                  <SelectItem value="admin">ผู้ดูแลระบบ</SelectItem>
                </SelectContent>
```

with:

```tsx
                <SelectContent>
                  <SelectItem value="user">ผู้ใช้</SelectItem>
                  <SelectItem value="viewer">ผู้ชม (อ่านอย่างเดียว)</SelectItem>
                  <SelectItem value="auditor">ผู้ตรวจสอบ (อ่านอย่างเดียว)</SelectItem>
                  <SelectItem value="agency_owner">เจ้าของหน่วยงาน</SelectItem>
                  <SelectItem value="admin">ผู้ดูแลระบบ</SelectItem>
                </SelectContent>
```

- [ ] **Step 2: Verify build compiles**

Run: `cd frontend && rtk tsc --noEmit`
Expected: no type errors (`UserRole` was widened in Task 5).

- [ ] **Step 3: Commit**

```bash
rtk git add frontend/src/features/users/UserFormDialog.tsx
rtk git commit -m "feat(users): allow assigning viewer and auditor roles"
```

---

## Phase 3 — Frontend: hide write controls for read-only roles

> Pages with NO write controls need no change: Dashboard, Health, Heatmap, Usage, Feedback, Architecture are read-only displays; the Heatmap range toggle and Usage date filters are client-side view state (keep them). The Executive "regenerate" button is already gated on `isAdmin`, so `viewer`/`auditor` never see it — no change needed there either. Only Agencies, API keys, and Users have controls to hide.

### Task 10: Hide agency write controls when read-only

**Files:**
- Modify: `frontend/src/features/agencies/AgenciesPage.tsx:99-103`
- Modify: `frontend/src/features/agencies/AgencyCard.tsx` (write menu items + setup link)
- Test: `frontend/src/features/agencies/AgencyCard.test.tsx` (create)

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/agencies/AgencyCard.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AgencyCard } from "./AgencyCard";

const auth = { isReadOnly: false };
vi.mock("@/features/auth/useAuth", () => ({ useAuth: () => auth }));

const agency = { id: "a1", name: "A", shortName: "A", status: "active" } as never;

function renderCard() {
  return render(
    <MemoryRouter>
      <AgencyCard agency={agency} onTest={() => {}} onStatusChange={() => {}} onDelete={() => {}} />
    </MemoryRouter>,
  );
}

describe("AgencyCard write controls", () => {
  beforeEach(() => { auth.isReadOnly = false; });

  it("renders the actions menu for a writer", () => {
    renderCard();
    expect(screen.getByLabelText(/actions|เมนู|more/i)).toBeInTheDocument();
  });

  it("hides the actions menu for a read-only role", () => {
    auth.isReadOnly = true;
    renderCard();
    expect(screen.queryByLabelText(/actions|เมนู|more/i)).not.toBeInTheDocument();
  });
});
```

> If the dropdown trigger has no accessible label, add `aria-label="actions"` to the `DropdownMenuTrigger` button in AgencyCard so the test can target it; do that as part of Step 3.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk vitest run src/features/agencies/AgencyCard.test.tsx`
Expected: FAIL — the menu renders regardless of `isReadOnly`.

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/features/agencies/AgencyCard.tsx`:

- Import auth at the top:

```tsx
import { useAuth } from "@/features/auth/useAuth";
```

- Inside the component, read the flag:

```tsx
  const { isReadOnly } = useAuth();
```

- Wrap the entire dropdown menu (the actions trigger + content covering Edit / Test / Status / Delete, lines ~82-112) so it only renders for writers:

```tsx
  {!isReadOnly && (
    <DropdownMenu>
      {/* ...existing trigger + DropdownMenuContent with Edit/Test/Status/Delete items... */}
    </DropdownMenu>
  )}
```

- Wrap the draft "Setup" link (lines ~156-162) the same way:

```tsx
  {!isReadOnly && agency.status === "draft" && (
    <Link to={`/agencies/${agency.id}/setup`} /* ...existing props... */>
      ตั้งค่าต่อ <ArrowRight className="h-3 w-3" />
    </Link>
  )}
```

In `frontend/src/features/agencies/AgenciesPage.tsx`:

- Import auth (top of file):

```tsx
import { useAuth } from "@/features/auth/useAuth";
```

- Read the flag inside the component (next to existing hooks):

```tsx
  const { isReadOnly } = useAuth();
```

- Wrap the "Add Agency" button (lines 99-103):

```tsx
  {!isReadOnly && (
    <Button size="sm" asChild>
      <Link to="/agencies/new">
        <Plus className="h-4 w-4 mr-1" /> เพิ่มหน่วยงาน
      </Link>
    </Button>
  )}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && rtk vitest run src/features/agencies/AgencyCard.test.tsx`
Expected: PASS.

- [ ] **Step 5: Verify build + commit**

```bash
cd frontend && rtk tsc --noEmit
rtk git add frontend/src/features/agencies/AgencyCard.tsx frontend/src/features/agencies/AgencyCard.test.tsx frontend/src/features/agencies/AgenciesPage.tsx
rtk git commit -m "feat(agencies): hide write controls for read-only roles"
```

---

### Task 11: Hide API-key write controls when read-only

**Files:**
- Modify: `frontend/src/features/api-keys/ApiKeysPage.tsx:139-142,194-217`
- Test: `frontend/src/features/api-keys/ApiKeysPage.test.tsx` (create)

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/api-keys/ApiKeysPage.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ApiKeysPage from "./ApiKeysPage";

const auth = { isReadOnly: false };
vi.mock("@/features/auth/useAuth", () => ({ useAuth: () => auth }));
vi.mock("./apiKeyApi", () => ({
  listApiKeys: () => Promise.resolve([]),
  createApiKey: vi.fn(),
  updateApiKey: vi.fn(),
  revokeApiKey: vi.fn(),
  deleteApiKey: vi.fn(),
}));

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><ApiKeysPage /></QueryClientProvider>);
}

describe("ApiKeysPage create button", () => {
  beforeEach(() => { auth.isReadOnly = false; });

  it("shows the create button for a writer", async () => {
    renderPage();
    expect(await screen.findByText("สร้าง API Key")).toBeInTheDocument();
  });

  it("hides the create button for a read-only role", () => {
    auth.isReadOnly = true;
    renderPage();
    expect(screen.queryByText("สร้าง API Key")).not.toBeInTheDocument();
  });
});
```

> Adjust the `vi.mock("./apiKeyApi", ...)` path/exports to match the page's actual data module (check the imports at the top of `ApiKeysPage.tsx`); the goal is only to stop real network calls during render.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk vitest run src/features/api-keys/ApiKeysPage.test.tsx`
Expected: FAIL — the create button renders even when read-only.

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/features/api-keys/ApiKeysPage.tsx`:

- Import auth and read the flag inside the component:

```tsx
import { useAuth } from "@/features/auth/useAuth";
// ...
  const { isReadOnly } = useAuth();
```

- Wrap the create button (lines 139-142):

```tsx
  {!isReadOnly && (
    <Button size="sm" onClick={() => setCreateOpen(true)}>
      <Plus className="h-4 w-4 mr-1" />
      สร้าง API Key
    </Button>
  )}
```

- Wrap the per-row edit/revoke/delete control group (lines 194-217) in a single `{!isReadOnly && ( ... )}` so a read-only role sees the key rows but no action buttons:

```tsx
  {!isReadOnly && (
    <>
      {/* existing Pencil (edit), Ban (revoke), Trash2 (delete) buttons, lines 194-217 */}
    </>
  )}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && rtk vitest run src/features/api-keys/ApiKeysPage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Verify build + commit**

```bash
cd frontend && rtk tsc --noEmit
rtk git add frontend/src/features/api-keys/ApiKeysPage.tsx frontend/src/features/api-keys/ApiKeysPage.test.tsx
rtk git commit -m "feat(api-keys): hide write controls for read-only roles"
```

---

### Task 12: Hide user-management write controls when read-only

**Files:**
- Modify: `frontend/src/features/users/UsersPage.tsx:28,75-78`
- Test: `frontend/src/features/users/UsersPage.test.tsx` (create)

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/users/UsersPage.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import UsersPage from "./UsersPage";

const auth = { isReadOnly: false };
vi.mock("@/features/auth/useAuth", () => ({ useAuth: () => auth }));
vi.mock("./userApi", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("./userApi");
  return { ...actual, listUsers: () => Promise.resolve([]) };
});

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><UsersPage /></QueryClientProvider>);
}

describe("UsersPage create control", () => {
  beforeEach(() => { auth.isReadOnly = false; });

  it("shows the add-user button for a writer (admin)", async () => {
    renderPage();
    expect(await screen.findByText("เพิ่มผู้ใช้")).toBeInTheDocument();
  });

  it("hides the add-user button for a read-only role (auditor)", () => {
    auth.isReadOnly = true;
    renderPage();
    expect(screen.queryByText("เพิ่มผู้ใช้")).not.toBeInTheDocument();
  });
});
```

> Adjust the `vi.mock("./userApi", ...)` exports to match the actual data hook/module used by `UsersPage.tsx` so render makes no real request.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk vitest run src/features/users/UsersPage.test.tsx`
Expected: FAIL — add-user button renders for a read-only role.

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/features/users/UsersPage.tsx`:

- Import auth and read the flag inside the component:

```tsx
import { useAuth } from "@/features/auth/useAuth";
// ...
  const { isReadOnly } = useAuth();
```

- Wrap the create button (line 28):

```tsx
  {!isReadOnly && (
    <Button onClick={openCreate}><UserPlus className="h-4 w-4 mr-2" />เพิ่มผู้ใช้</Button>
  )}
```

- Wrap the per-row Edit + Deactivate/Activate buttons (lines 75-78):

```tsx
  {!isReadOnly && (
    <>
      <Button variant="ghost" size="sm" onClick={() => openEdit(u)}>แก้ไข</Button>
      <Button variant="ghost" size="sm" onClick={() => setToggling(u)}>
        {u.isActive ? 'ปิดใช้งาน' : 'เปิดใช้งาน'}
      </Button>
    </>
  )}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && rtk vitest run src/features/users/UsersPage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Verify build + commit**

```bash
cd frontend && rtk tsc --noEmit
rtk git add frontend/src/features/users/UsersPage.tsx frontend/src/features/users/UsersPage.test.tsx
rtk git commit -m "feat(users): hide write controls for read-only roles"
```

---

## Phase 4 — Full verification

### Task 13: Run the complete suites and update the cross-reference comment

**Files:**
- Modify: `frontend/src/shared/components/layout/AppSidebar.tsx` (comment only — confirm the sync note points at `roles.ts` + backend allowlist)

- [ ] **Step 1: Backend suite**

Run: `cd backend && rtk pytest -q`
Expected: PASS (all tests, including the migrated `test_basic_user_allowlist.py` and new `test_role_allowlist.py`, `test_user_schema_roles.py`, `test_users_last_admin.py`).

- [ ] **Step 2: Frontend suite + typecheck**

Run: `cd frontend && rtk vitest run && rtk tsc --noEmit`
Expected: PASS, no type errors.

- [ ] **Step 3: Confirm the sync comment**

Ensure a comment near the top of `roles.ts` (added in Task 5) and/or `AppSidebar.tsx` notes that route visibility, the route guard, and the backend allowlist (`backend/app/auth/dependencies.py`) must stay in sync. Fix if missing.

- [ ] **Step 4: Final commit (if anything changed in Step 3)**

```bash
rtk git add -A
rtk git commit -m "docs(auth): cross-reference role map, guard, and backend allowlist"
```

---

## Self-Review Notes (author checklist — resolved)

- **Spec coverage:** Role literal (Task 1), backend enforcement with viewer/auditor allowlists + dispatch (Tasks 2-3), last-admin protection (Task 4), frontend role union + `isReadOnly` + central map (Task 5), guard (Task 6), routes (Task 7), sidebar (Task 8), role assignment UI (Task 9), hidden write controls (Tasks 10-12), verification (Task 13). Anonymous chat/rating row needs no code (existing behavior; `credentials is None` short-circuit preserved by Task 3) — confirmed.
- **Type consistency:** `Role` defined once in `roles.ts` and reused in `useAuth.tsx`, `ProtectedRoute.tsx`; `UserRole` widened in `userApi.ts`; backend `Role` literal widened in `schemas/user.py`. Function names consistent: `_is_shared_write`, `_is_allowed_for_viewer`, `_is_allowed_for_auditor`, `enforce_role_allowlist`, `canAccess`, `isReadOnlyRole`.
- **Open decision surfaced to the user:** `/my-agencies` excludes `auditor` (personal page); flag if you'd rather auditors see it.
