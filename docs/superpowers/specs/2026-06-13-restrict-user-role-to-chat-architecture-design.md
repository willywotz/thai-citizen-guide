# Restrict `user` role to Chat + Architecture pages

**Date:** 2026-06-13
**Status:** Approved design — pending implementation plan

## Goal

A person with role `user` (the default role) may access **only** the Chat page and
the Architecture page. All other application pages are hidden from navigation and
unreachable, both in the React frontend and at the FastAPI backend. The `admin` and
`agency_owner` roles are unaffected.

## Background

- Roles: `user | admin | agency_owner` (`backend/app/schemas/user.py`, default `user`).
- Frontend protected routes live in `frontend/src/App.tsx`; the nav menu in
  `frontend/src/shared/components/layout/AppSidebar.tsx` already gates `ownerItems`
  (owner/admin) and `adminItems` (admin) but shows all "common" `navItems` to everyone.
- Backend gating is **inconsistent**: some pages behind "restricted" routes are not
  actually protected (`GET /executive-summary` and `GET /agencies` are public,
  `GET /conversations` allows anonymous). This is why a single backend chokepoint is
  used rather than trusting per-endpoint guards.
- **Shared endpoint:** the Architecture page consumes `GET /api/v1/agencies` — the same
  list endpoint the (now-forbidden) Agencies page uses. The allowlist must keep this
  endpoint open while the Agencies *page* stays hidden.
- Login/Signup already redirect to `/chat` (`LoginPage.tsx:23,37`, `SignupPage.tsx:35`),
  so a `user` lands on an allowed page after authenticating.

## Allowed pages for `user`

| Page | Route | Backend endpoints |
|------|-------|-------------------|
| Chat | `/chat` | `POST /api/v1/chat`, `POST /api/v1/chat/stream`, `PATCH /api/v1/messages/{id}/rating`, `GET`+read of the user's own conversations |
| Architecture | `/architecture` | `GET /api/v1/agencies` (list) |

Everything else (dashboard, executive, health, heatmap, agencies, history,
connection-logs, api-keys, settings, users, audit-log, usage, feedback) is forbidden.

## Design

### Frontend

1. **Sidebar (`AppSidebar.tsx`).** Introduce an allowlist of routes visible to the
   `user` role: `{"/chat", "/architecture"}`. When `user?.role === "user"`, filter the
   common `navItems` to only those routes. Owner/admin sections remain as-is (a `user`
   never matches those conditions anyway).

2. **Route guard (`ProtectedRoute.tsx`).** Add an optional `allowBasicUser?: boolean`
   prop (default `false`). When the authenticated user's role is `user` and the route is
   **not** flagged `allowBasicUser`, render `<Navigate to="/chat" replace />`. The Chat
   and Architecture routes in `App.tsx` get `allowBasicUser`. The existing
   `requireAdmin` behavior is unchanged. Loading/unauthenticated branches unchanged.

   Redirect-to-`/chat` is the chosen UX (no "Access Denied" screen) so a `user` only ever
   sees pages they may use.

### Backend — centralized allowlist chokepoint (Option B)

3. **New dependency** in `backend/app/auth/dependencies.py`, e.g.
   `enforce_basic_user_allowlist(request: Request, user: User | None = Depends(get_current_user_optional))`:
   - If `user is None` or `user.role != "user"` → return (no restriction; anonymous,
     admin, and agency_owner are unaffected here — their access is governed by the
     existing per-endpoint auth).
   - If `user.role == "user"`: allow the request only if `(method, path)` matches the
     allowlist below; otherwise raise `HTTPException(403, "Restricted role")`.

4. **Allowlist** (method + path prefix, matched against the request path under
   `/api/v1`):
   - `POST   /api/v1/chat`
   - `POST   /api/v1/chat/stream`
   - `PATCH  /api/v1/messages/{message_id}/rating`
   - `GET    /api/v1/agencies` (list only — not `/agencies/{id}` mutations)
   - `GET/POST/DELETE` on the user's **own** conversations
     (`/api/v1/conversations`, `/api/v1/conversations/{id}`) — included so the Chat page
     can show the user's own history; ownership is still enforced by the existing
     conversation auth.
   - `/api/v1/auth/*` and self-profile endpoints (e.g. `/me`) — required so the user can
     authenticate, refresh, and fetch their own profile.

5. **Wiring.** Attach the dependency at the API-router level (the `/api/v1` router in
   `backend/app/main.py`) so it runs for every API request as a single chokepoint, rather
   than being added per endpoint. Path matching uses route templates (so `{id}` segments
   match) — implement against the matched route path, not raw string compare, to avoid
   brittleness.

## Error handling

- Frontend: guarded route → silent redirect to `/chat`. No new error UI.
- Backend: forbidden request for a `user` → `403` with a clear `detail`
  (`"This role may only access chat and architecture"`).

## Testing (TDD — write failing tests first)

**Backend (`pytest`):**
- `user` token gets `403` on: `GET /dashboard/stats`, `GET /insight/usage`,
  `GET /usage-heatmap`, `GET /connection-logs`, `GET /api-keys/`,
  `GET /executive-summary`, `GET /feedback/stats`.
- `user` token gets allowed (non-403) on: `POST /chat`, `POST /chat/stream`,
  `PATCH /messages/{id}/rating`, `GET /agencies`, `GET /conversations`.
- `admin` token still reaches all of the above (no regression).
- `agency_owner` token unaffected on its endpoints.
- Anonymous behavior unchanged.

**Frontend:**
- `AppSidebar` renders exactly two items (`/chat`, `/architecture`) for role `user`;
  renders the full set for `admin`.
- `ProtectedRoute` redirects a `user` to `/chat` for a non-allowlisted route and renders
  children for `/chat` and `/architecture`.

## Out of scope

- No changes to `admin` / `agency_owner` capabilities.
- No new roles or permission model; this is a targeted allowlist for the existing `user`
  role.
- No refactor of the broader inconsistent per-endpoint auth (only the chokepoint is added).
