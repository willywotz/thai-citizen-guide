# Restrict `user` Role to Chat + Architecture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A person with role `user` may access only the Chat and Architecture pages; every other page is hidden in the UI, redirected in the router, and blocked at the API. `admin` and `agency_owner` are unaffected.

**Architecture:** Frontend filters the sidebar and gates routes (redirect to `/chat`). Backend adds one centralized allowlist dependency wired as a global FastAPI dependency — a single chokepoint that 403s any `user`-role request outside the allowlist. The allowlist maps 1:1 to the Chat + Architecture pages (plus auth/self endpoints every session needs).

**Tech Stack:** FastAPI + Tortoise ORM + pytest (backend); React + React Router + TypeScript + Vitest + Testing Library (frontend).

---

## File Structure

**Backend**
- Modify `backend/app/auth/dependencies.py` — add `_resolve_role`, `_is_allowed_for_basic_user`, and the `enforce_basic_user_allowlist` dependency.
- Modify `backend/app/main.py` — wire the dependency globally on the `FastAPI(...)` constructor.
- Create `backend/tests/test_basic_user_allowlist.py` — unit tests for the allowlist matcher and the dependency.

**Frontend**
- Modify `frontend/src/features/auth/ProtectedRoute.tsx` — add `requireNonBasic` gating.
- Modify `frontend/src/App.tsx` — group non-allowed routes under a `requireNonBasic` layout route.
- Modify `frontend/src/shared/components/layout/AppSidebar.tsx` — filter nav items for `user` role.
- Create `frontend/src/features/auth/ProtectedRoute.test.tsx`.
- Create `frontend/src/shared/components/layout/AppSidebar.test.tsx`.

**Why a side-effect-free role resolver:** the existing `_resolve_token` consumes API-key rate-limit tokens and stamps `last_used_at` on every call. A global dependency that called it would double-charge those side effects for every authenticated request (the endpoint resolves the token again under a different callable). `_resolve_role` does a read-only role lookup instead.

---

## Task 1: Backend allowlist matcher (pure function)

**Files:**
- Modify: `backend/app/auth/dependencies.py`
- Test: `backend/tests/test_basic_user_allowlist.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_basic_user_allowlist.py`:

```python
"""The basic-user allowlist maps 1:1 to the Chat + Architecture pages."""
from app.auth.dependencies import _is_allowed_for_basic_user


def test_chat_endpoints_allowed():
    assert _is_allowed_for_basic_user("POST", "/api/v1/chat")
    assert _is_allowed_for_basic_user("POST", "/api/v1/chat/stream")


def test_message_rating_allowed():
    assert _is_allowed_for_basic_user("PATCH", "/api/v1/messages/abc-123/rating")


def test_agencies_list_allowed_but_not_mutations():
    assert _is_allowed_for_basic_user("GET", "/api/v1/agencies")
    assert not _is_allowed_for_basic_user("DELETE", "/api/v1/agencies/abc-123")
    assert not _is_allowed_for_basic_user("PATCH", "/api/v1/agencies/abc-123/status")


def test_own_conversations_allowed():
    assert _is_allowed_for_basic_user("GET", "/api/v1/conversations")
    assert _is_allowed_for_basic_user("DELETE", "/api/v1/conversations/abc-123")


def test_auth_self_endpoints_allowed():
    assert _is_allowed_for_basic_user("GET", "/api/v1/auth/me")
    assert _is_allowed_for_basic_user("POST", "/api/v1/auth/login")


def test_restricted_pages_blocked():
    assert not _is_allowed_for_basic_user("GET", "/api/v1/dashboard/stats")
    assert not _is_allowed_for_basic_user("GET", "/api/v1/connection-logs")
    assert not _is_allowed_for_basic_user("GET", "/api/v1/api-keys/")
    assert not _is_allowed_for_basic_user("GET", "/api/v1/executive-summary")
    assert not _is_allowed_for_basic_user("GET", "/api/v1/insight/usage")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && rtk pytest tests/test_basic_user_allowlist.py -v`
Expected: FAIL with `ImportError: cannot import name '_is_allowed_for_basic_user'`

- [ ] **Step 3: Write minimal implementation**

In `backend/app/auth/dependencies.py`, add `import re` to the top imports, then add after the `_invalid_credentials` definition (around line 36):

```python
_MESSAGE_RATING_PATH = re.compile(r"^/api/v1/messages/[^/]+/rating$")
_CONVERSATION_PATH = re.compile(r"^/api/v1/conversations(?:/[^/]+)?$")


def _is_allowed_for_basic_user(method: str, path: str) -> bool:
    """Allowlist of (method, path) a plain ``user`` role may reach.

    Maps 1:1 to the Chat and Architecture pages, plus the auth/self endpoints
    every authenticated session needs. Everything else is forbidden.
    """
    if path.startswith("/api/v1/auth/"):
        return True
    if method == "POST" and path in ("/api/v1/chat", "/api/v1/chat/stream"):
        return True
    if method == "PATCH" and _MESSAGE_RATING_PATH.match(path):
        return True
    if method == "GET" and path == "/api/v1/agencies":  # Architecture page (list only)
        return True
    if _CONVERSATION_PATH.match(path):  # the user's own chat history
        return True
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && rtk pytest tests/test_basic_user_allowlist.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
rtk git add backend/app/auth/dependencies.py backend/tests/test_basic_user_allowlist.py
rtk git commit -m "feat(authz): add basic-user page allowlist matcher"
```

---

## Task 2: Side-effect-free role resolver

**Files:**
- Modify: `backend/app/auth/dependencies.py`
- Test: `backend/tests/test_basic_user_allowlist.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_basic_user_allowlist.py`:

```python
import pytest

from app.auth.dependencies import _resolve_role
from app.auth.security import create_access_token, generate_api_key, hash_api_key
from app.models.user import User, UserAPIKey

pytestmark = pytest.mark.asyncio


async def test_resolve_role_from_jwt(db):
    user = await User.create(email="role-jwt@x.com", hashed_password="h", role="user")
    token = create_access_token({"sub": str(user.id)})
    assert await _resolve_role(token) == "user"


async def test_resolve_role_admin(db):
    user = await User.create(email="role-admin@x.com", hashed_password="h", role="admin")
    token = create_access_token({"sub": str(user.id)})
    assert await _resolve_role(token) == "admin"


async def test_resolve_role_from_api_key(db):
    user = await User.create(email="role-key@x.com", hashed_password="h", role="user")
    raw = generate_api_key()
    await UserAPIKey.create(
        user_id=user.id, name="n", key_hash=hash_api_key(raw), key_prefix=raw[:12]
    )
    assert await _resolve_role(raw) == "user"


async def test_resolve_role_invalid_returns_none(db):
    assert await _resolve_role("not-a-jwt") is None
    assert await _resolve_role("tcg_bogus") is None
```

Note: the `db` fixture comes from `backend/tests/conftest.py`. `pytestmark` here marks only the async tests added in this file; if the earlier pure tests are in the same file they remain sync and unaffected (they take no `db`/await).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && rtk pytest tests/test_basic_user_allowlist.py -k resolve_role -v`
Expected: FAIL with `ImportError: cannot import name '_resolve_role'`

- [ ] **Step 3: Write minimal implementation**

In `backend/app/auth/dependencies.py`, add after `_resolve_token` (around line 81):

```python
async def _resolve_role(token: str) -> str | None:
    """Return the caller's role without the side effects of ``_resolve_token``.

    Used only by the basic-user chokepoint. Deliberately skips API-key rate
    limiting and ``last_used_at`` stamping so wiring it globally never double-
    charges those — it only needs the role.
    """
    if token.startswith(API_KEY_PREFIX):
        api_key = await UserAPIKey.filter(key_hash=hash_api_key(token)).first()
        if api_key is None or not api_key.is_usable():
            return None
        user = await User.filter(id=api_key.user_id, is_active=True).first()
        return user.role if user else None

    try:
        payload = decode_access_token(token)
    except JWTError:
        return None
    user_id: str = payload.get("sub", "")
    if not user_id:
        return None
    user = await User.filter(id=user_id, is_active=True).first()
    return user.role if user else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && rtk pytest tests/test_basic_user_allowlist.py -k resolve_role -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
rtk git add backend/app/auth/dependencies.py backend/tests/test_basic_user_allowlist.py
rtk git commit -m "feat(authz): add side-effect-free role resolver"
```

---

## Task 3: The `enforce_basic_user_allowlist` dependency

**Files:**
- Modify: `backend/app/auth/dependencies.py`
- Test: `backend/tests/test_basic_user_allowlist.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_basic_user_allowlist.py`:

```python
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

from app.auth.dependencies import enforce_basic_user_allowlist


def _request(method: str, path: str) -> Request:
    return Request(
        {"type": "http", "method": method, "path": path,
         "headers": [], "query_string": b""}
    )


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


async def _token_for(email: str, role: str) -> str:
    user = await User.create(email=email, hashed_password="h", role=role)
    return create_access_token({"sub": str(user.id)})


async def test_basic_user_blocked_on_restricted_page(db):
    token = await _token_for("b1@x.com", "user")
    with pytest.raises(HTTPException) as e:
        await enforce_basic_user_allowlist(
            _request("GET", "/api/v1/dashboard/stats"), _creds(token)
        )
    assert e.value.status_code == 403


async def test_basic_user_allowed_on_chat(db):
    token = await _token_for("b2@x.com", "user")
    # No raise == allowed.
    assert await enforce_basic_user_allowlist(
        _request("POST", "/api/v1/chat"), _creds(token)
    ) is None


async def test_admin_unaffected(db):
    token = await _token_for("b3@x.com", "admin")
    assert await enforce_basic_user_allowlist(
        _request("GET", "/api/v1/dashboard/stats"), _creds(token)
    ) is None


async def test_agency_owner_unaffected(db):
    token = await _token_for("b4@x.com", "agency_owner")
    assert await enforce_basic_user_allowlist(
        _request("GET", "/api/v1/connection-logs"), _creds(token)
    ) is None


async def test_anonymous_unaffected(db):
    assert await enforce_basic_user_allowlist(
        _request("GET", "/api/v1/dashboard/stats"), None
    ) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && rtk pytest tests/test_basic_user_allowlist.py -k "blocked or allowed_on_chat or unaffected" -v`
Expected: FAIL with `ImportError: cannot import name 'enforce_basic_user_allowlist'`

- [ ] **Step 3: Write minimal implementation**

In `backend/app/auth/dependencies.py`, add `Request` to the FastAPI import line so it reads:

```python
from fastapi import Depends, HTTPException, Request, status
```

Then add at the end of the file:

```python
async def enforce_basic_user_allowlist(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_optional),
) -> None:
    """Chokepoint: a ``user``-role caller may only reach chat + architecture.

    Anonymous, ``admin`` and ``agency_owner`` callers pass straight through;
    their access is governed by each endpoint's own auth. Wired as a global
    dependency in ``app.main`` so it runs once per request.
    """
    if credentials is None:
        return
    role = await _resolve_role(credentials.credentials)
    if role != "user":
        return
    if not _is_allowed_for_basic_user(request.method, request.url.path):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This role may only access chat and architecture",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && rtk pytest tests/test_basic_user_allowlist.py -v`
Expected: PASS (all tests in the file pass)

- [ ] **Step 5: Commit**

```bash
rtk git add backend/app/auth/dependencies.py backend/tests/test_basic_user_allowlist.py
rtk git commit -m "feat(authz): add basic-user allowlist enforcement dependency"
```

---

## Task 4: Wire the chokepoint globally

**Files:**
- Modify: `backend/app/main.py:39` (import) and `backend/app/main.py:91` (constructor)

- [ ] **Step 1: Add the import**

In `backend/app/main.py`, add this import in the app imports block (after line 39's router import):

```python
from app.auth.dependencies import enforce_basic_user_allowlist
```

- [ ] **Step 2: Wire it onto the FastAPI constructor**

Add a `dependencies=[...]` argument to the `app = FastAPI(...)` call (line 91). Add it right after `lifespan=lifespan,`:

```python
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Central AI Chatbot Portal API.\n\n"
        "**MCP SSE** (OneChat-compatible): `GET /sse` → open stream, `POST /messages/` → send commands.\n\n"
        "**MCP Streamable-HTTP** (legacy): available at `/mcp`.\n\n"
        "**REST API** endpoints are under `/api/v1`."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    dependencies=[Depends(enforce_basic_user_allowlist)],
)
```

Add `Depends` to the FastAPI import at line 28 so it reads:

```python
from fastapi import Depends, FastAPI
```

Note: a global app dependency does **not** apply to the mounted MCP sub-apps (`/mcp`, `/messages`) or the `add_route('/sse')` handler — those are out of scope (API-key-driven MCP traffic, not the web app's pages).

- [ ] **Step 3: Verify the app imports and the full backend suite passes**

Run: `cd backend && rtk pytest -q`
Expected: PASS — the new file passes and no existing test regresses. In particular confirm `test_api_key_rest_auth.py`, `test_api_key_enforcement.py`, and `test_user_rate_limit.py` still pass (they assert the rate-limit/last_used side effects that `_resolve_role` deliberately avoids).

- [ ] **Step 4: Commit**

```bash
rtk git add backend/app/main.py
rtk git commit -m "feat(authz): wire basic-user allowlist as a global chokepoint"
```

---

## Task 5: Frontend route guard — `requireNonBasic`

**Files:**
- Modify: `frontend/src/features/auth/ProtectedRoute.tsx`
- Test: `frontend/src/features/auth/ProtectedRoute.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/auth/ProtectedRoute.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProtectedRoute } from "./ProtectedRoute";

const auth = { user: null as { role: string } | null, isAdmin: false, isLoading: false };
vi.mock("@/features/auth/useAuth", () => ({ useAuth: () => auth }));

function renderAt(initial: string, ui: React.ReactNode) {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route path="/chat" element={<div>chat page</div>} />
        <Route path="/secret" element={ui} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute requireNonBasic", () => {
  beforeEach(() => {
    auth.user = { role: "user" };
    auth.isAdmin = false;
    auth.isLoading = false;
  });

  it("redirects a basic user to /chat", () => {
    renderAt("/secret", <ProtectedRoute requireNonBasic><div>secret content</div></ProtectedRoute>);
    expect(screen.getByText("chat page")).toBeInTheDocument();
    expect(screen.queryByText("secret content")).not.toBeInTheDocument();
  });

  it("lets an admin through", () => {
    auth.user = { role: "admin" };
    auth.isAdmin = true;
    renderAt("/secret", <ProtectedRoute requireNonBasic><div>secret content</div></ProtectedRoute>);
    expect(screen.getByText("secret content")).toBeInTheDocument();
  });

  it("does not gate routes without requireNonBasic", () => {
    renderAt("/secret", <ProtectedRoute><div>secret content</div></ProtectedRoute>);
    expect(screen.getByText("secret content")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk npx vitest run src/features/auth/ProtectedRoute.test.tsx`
Expected: FAIL — basic user is not redirected (the `requireNonBasic` prop does nothing yet), so "secret content" is found.

- [ ] **Step 3: Write minimal implementation**

Edit `frontend/src/features/auth/ProtectedRoute.tsx`. Change the props interface and signature, and add the gate after the `!user` check:

```tsx
interface ProtectedRouteProps {
  children: React.ReactNode;
  requireAdmin?: boolean;
  requireNonBasic?: boolean;
}

export function ProtectedRoute({
  children,
  requireAdmin = false,
  requireNonBasic = false,
}: ProtectedRouteProps) {
  const { user, isAdmin, isLoading } = useAuth();
```

Leave the `isLoading` block unchanged. Leave `if (!user) { return <Navigate to="/login" replace />; }` unchanged. Immediately after it, add:

```tsx
  if (requireNonBasic && user.role === "user") {
    return <Navigate to="/chat" replace />;
  }
```

Leave the `requireAdmin` block and the final `return <>{children}</>;` unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && rtk npx vitest run src/features/auth/ProtectedRoute.test.tsx`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
rtk git add frontend/src/features/auth/ProtectedRoute.tsx frontend/src/features/auth/ProtectedRoute.test.tsx
rtk git commit -m "feat(auth): add requireNonBasic guard to ProtectedRoute"
```

---

## Task 6: Group non-allowed routes under `requireNonBasic`

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add the `Outlet` import**

Change line 5 of `frontend/src/App.tsx` to import `Outlet`:

```tsx
import { BrowserRouter, Routes, Route, Outlet } from "react-router-dom";
```

- [ ] **Step 2: Restructure the protected routes**

Replace the protected-routes block (lines 54–74) with the following. Chat and Architecture stay directly under the auth wrapper; everything else is nested under a `requireNonBasic` layout route:

```tsx
              <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
                <Route path="/chat" element={<ChatPage />} />
                <Route path="/architecture" element={<ArchitecturePage />} />

                <Route element={<ProtectedRoute requireNonBasic><Outlet /></ProtectedRoute>}>
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/executive" element={<ExecutivePage />} />
                  <Route path="/health" element={<HealthPage />} />
                  <Route path="/heatmap" element={<HeatmapPage />} />
                  <Route path="/agencies" element={<AgenciesPage />} />
                  <Route path="/my-agencies" element={<MyAgenciesPage />} />
                  <Route path="/agencies/new" element={<AgencyWizardPage />} />
                  <Route path="/agencies/:id/setup" element={<AgencyWizardPage />} />
                  <Route path="/agencies/:id" element={<AgencyDetailPage />} />
                  <Route path="/history" element={<HistoryPage />} />
                  <Route path="/connection-logs" element={<ConnectionLogsPage />} />
                  <Route path="/api-keys" element={<ApiKeysPage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                  <Route path="/users" element={<ProtectedRoute requireAdmin><UsersPage /></ProtectedRoute>} />
                  <Route path="/audit-log" element={<ProtectedRoute requireAdmin><AuditLogPage /></ProtectedRoute>} />
                  <Route path="/usage" element={<ProtectedRoute requireAdmin><UsageAnalyticsPage /></ProtectedRoute>} />
                  <Route path="/feedback" element={<ProtectedRoute requireAdmin><FeedbackPage /></ProtectedRoute>} />
                </Route>
              </Route>
```

- [ ] **Step 3: Verify the app builds / type-checks**

Run: `cd frontend && rtk npx tsc --noEmit`
Expected: PASS (no type errors).

- [ ] **Step 4: Commit**

```bash
rtk git add frontend/src/App.tsx
rtk git commit -m "feat(routing): gate non-chat/architecture routes behind requireNonBasic"
```

---

## Task 7: Filter the sidebar for the `user` role

**Files:**
- Modify: `frontend/src/shared/components/layout/AppSidebar.tsx`
- Test: `frontend/src/shared/components/layout/AppSidebar.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/shared/components/layout/AppSidebar.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppSidebar } from "./AppSidebar";
import { SidebarProvider } from "@/shared/components/ui/sidebar";

const auth = { user: { role: "user" } as { role: string }, signOut: vi.fn() };
vi.mock("@/features/auth/useAuth", () => ({ useAuth: () => auth }));
vi.mock("@/features/agencies/useAgencies", () => ({ useAgencies: () => ({ data: [] }) }));

function renderSidebar() {
  return render(
    <MemoryRouter>
      <SidebarProvider>
        <AppSidebar />
      </SidebarProvider>
    </MemoryRouter>,
  );
}

describe("AppSidebar role filtering", () => {
  beforeEach(() => {
    auth.user = { role: "user" };
  });

  it("shows only chat and architecture for a basic user", () => {
    renderSidebar();
    expect(screen.getByText("แชท")).toBeInTheDocument();
    expect(screen.getByText("Architecture")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
    expect(screen.queryByText("จัดการหน่วยงาน")).not.toBeInTheDocument();
    expect(screen.queryByText("API Keys")).not.toBeInTheDocument();
  });

  it("shows the full common menu for an admin", () => {
    auth.user = { role: "admin" };
    renderSidebar();
    expect(screen.getByText("แชท")).toBeInTheDocument();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("API Keys")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk npx vitest run src/shared/components/layout/AppSidebar.test.tsx`
Expected: FAIL — "Dashboard" is still rendered for a basic user (no filtering yet).

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/shared/components/layout/AppSidebar.tsx`, add a route allowlist constant just below the `navItems` array (after line 31):

```tsx
const BASIC_USER_ROUTES = new Set(["/chat", "/architecture"]);
```

Inside `AppSidebar`, after the `const collapsed = ...` line (line 49), derive the visible items:

```tsx
  const visibleNavItems =
    user?.role === "user"
      ? navItems.filter((item) => BASIC_USER_ROUTES.has(item.url))
      : navItems;
```

Change the common-menu map (line 81) from `navItems.map(` to `visibleNavItems.map(`. Leave the owner/admin sections unchanged (a `user` never matches those conditions).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && rtk npx vitest run src/shared/components/layout/AppSidebar.test.tsx`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
rtk git add frontend/src/shared/components/layout/AppSidebar.tsx frontend/src/shared/components/layout/AppSidebar.test.tsx
rtk git commit -m "feat(sidebar): show only chat + architecture for the user role"
```

---

## Task 8: Full verification

- [ ] **Step 1: Backend suite + lint**

Run: `cd backend && rtk pytest -q`
Expected: PASS (no regressions).

If the repo uses a Python linter/formatter, run it on the changed files (`backend/app/auth/dependencies.py`, `backend/app/main.py`) and fix any issues.

- [ ] **Step 2: Frontend suite + types**

Run: `cd frontend && rtk npx vitest run && rtk npx tsc --noEmit`
Expected: PASS for both.

- [ ] **Step 3: Lint the frontend**

Run: `cd frontend && rtk lint`
Expected: no new violations in the changed files. Fix any that appear.

- [ ] **Step 4: Final commit (if lint produced fixes)**

```bash
rtk git add -A
rtk git commit -m "chore: lint/format basic-user restriction changes"
```

---

## Self-Review notes

- **Spec coverage:** Frontend sidebar (Task 7), frontend route redirect to `/chat` (Tasks 5–6), backend chokepoint + allowlist incl. own-conversations (Tasks 1–4), admin/agency_owner unaffected (Task 3 tests), TDD throughout. ✓
- **Shared `GET /agencies`:** allowlisted for the Architecture page while `/agencies` mutations stay blocked (Task 1 test `test_agencies_list_allowed_but_not_mutations`). ✓
- **No double side effects:** `_resolve_role` is read-only; Task 4 Step 3 re-runs the API-key/rate-limit tests to confirm no regression. ✓
- **Out of scope:** MCP transports (`/mcp`, `/sse`, `/messages`) are not covered by the global app dependency — noted in Task 4.
