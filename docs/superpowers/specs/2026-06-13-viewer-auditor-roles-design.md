# Design: `viewer` and `auditor` roles

**Date:** 2026-06-13
**Status:** Approved (design), pending implementation plan

## Problem

The app has three authenticated roles: `user` (basic — chat + architecture),
`agency_owner` (operational pages, write access), and `admin` (everything). We
need two new **read-only** roles:

- **`viewer`** — read-only operational/analytics view, plus chat.
- **`auditor`** — read-only access to *everything except Settings*, plus chat.

Both may send chat messages and manage their own conversations; that is the only
write exception. Everything else is read-only and enforced server-side.

## Access matrix

| Page / capability | anonymous | user | **viewer** | **auditor** | agency_owner | admin |
|---|---|---|---|---|---|---|
| Public portal, status, auth | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Chat (send messages) | ✅ (public portal) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Rate message / feedback | ✅ (public portal) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Architecture | — | ✅ | ✅ read | ✅ read | ✅ | ✅ |
| Dashboard / Executive / Health / Heatmap | — | — | ✅ read | ✅ read | ✅ | ✅ |
| Usage analytics | — | — | ✅ read | ✅ read | — | ✅ |
| Feedback | — | — | ✅ read | ✅ read | — | ✅ |
| Agencies mgmt / History / Connection logs / API keys | — | — | — | ✅ read | ✅ | ✅ |
| Users / Audit log | — | — | — | ✅ read | — | ✅ |
| Settings | — | — | — | — | — | ✅ |
| Write actions (create/edit/delete) | chat + rating only | chat only | chat only | chat only | ✅ | ✅ |

- **Anonymous (public portal):** unauthenticated visitors at `/` may send chat
  (`POST /api/v1/chat`, `/api/v1/chat/stream`) and rate messages
  (`PATCH /api/v1/messages/{id}/rating`) via optional auth. The chokepoint
  already returns early for anonymous callers, so no enforcement change is
  needed here — this row documents existing behaviour the new roles must not
  regress.
- **Data scope:** `viewer` and `auditor` see organization-wide data across all
  agencies (like admin), read-only. No per-agency association is added.
- **Write exception (all non-privileged roles):** `POST /api/v1/chat`,
  `POST /api/v1/chat/stream`, `PATCH /api/v1/messages/{id}/rating`, all verbs on
  `/api/v1/conversations` and `/api/v1/conversations/{id}`, and `/api/v1/auth/*`.

## Architecture — Approach A: explicit per-role allowlists

Mirror the existing `_is_allowed_for_basic_user` / `enforce_basic_user_allowlist`
pattern rather than introducing a permission framework. This keeps the new code
consistent with the codebase's current explicit-allowlist style and is
straightforward to TDD.

### Backend (`backend/app/`)

1. **Role definition.**
   - `schemas/user.py:12` — extend `Role = Literal["user", "admin", "agency_owner"]`
     to add `"viewer"` and `"auditor"`.
   - `models/user.py:17` — update the `role` field comment to list all five roles
     (the column is already `CharField(max_length=20)`, no migration needed).

2. **Chokepoint generalization** (`auth/dependencies.py`).
   - Keep `_is_allowed_for_basic_user(method, path)` as-is.
   - Add `_is_allowed_for_viewer(method, path)` — the shared write exceptions
     (chat / conversations / ratings / auth) **plus** `GET` on the data endpoints
     backing: Architecture (`GET /api/v1/agencies`), Dashboard/Executive/Health/
     Heatmap/Usage analytics, and Feedback. No `GET` on users, audit log,
     api-keys, connection-logs, or agency detail/history.
   - Add `_is_allowed_for_auditor(method, path)` — the shared write exceptions
     **plus** *any* `GET` request, **except** `GET` on Settings endpoints.
     (Auditor reads everything but Settings; writes only chat.)
   - Rename/generalize `enforce_basic_user_allowlist` →
     `enforce_role_allowlist`: resolve the caller role, then dispatch to the
     matching allowlist function. `admin`, `agency_owner`, and anonymous pass
     through unchanged (their access is governed per-endpoint as today). A
     restricted role hitting a disallowed `(method, path)` gets `403`.
   - Update the global wiring in `main.py:104` to the renamed dependency.

   The exact endpoint→page mapping for the viewer GET allowlist will be
   enumerated during planning by reading each feature router; the allowlist must
   be expressed as explicit path patterns (regex/prefix), consistent with the
   existing `_MESSAGE_RATING_PATH` / `_CONVERSATION_PATH` constants.

3. **Role assignment** (`routers/users.py`).
   - Admins assign roles via the Users page. The role-update path already
     validates against the `Role` literal, so adding the two literals is enough;
     confirm the existing "last admin protection" logic at `users.py:84-86`
     still holds and does not need to special-case the new roles.

### Frontend (`frontend/src/`)

1. **Role type** (`features/auth/useAuth.tsx:19`) — extend the `role` union with
   `"viewer"` and `"auditor"`. Add an `isReadOnly` boolean to the auth context
   (`true` when role is `viewer` or `auditor`) for pages to consume.

2. **Route guard** (`features/auth/ProtectedRoute.tsx`) — replace the
   `requireNonBasic` / `requireAdmin` booleans with a declarative
   `allowedRoles?: Role[]` prop. When set, a logged-in user whose role is not in
   the list is redirected to their landing page (`/chat`, which every
   non-anonymous role can reach). `requireAdmin`'s "permission denied" screen is
   preserved for admin-only routes (kept as a thin wrapper or an `allowedRoles={["admin"]}`
   variant — decided in the plan).

3. **Route tree** (`App.tsx`) — annotate each protected route with the roles
   permitted by the matrix using `allowedRoles`. Chat/Architecture: all
   authenticated roles. Dashboard/Executive/Health/Heatmap/Usage/Feedback: add
   `viewer` + `auditor` to the existing owner/admin set. Agencies/History/
   Connection-logs/API-keys/Users/Audit-log: add `auditor`. Settings: admin only.

4. **Sidebar** (`shared/components/layout/AppSidebar.tsx`) — replace the
   `BASIC_USER_ROUTES` set and the per-group `role ===` checks with a single
   role→visible-routes map derived from the same matrix, so the sidebar and the
   route guard share one source of truth. Keep the existing cross-reference
   comment pointing at the backend allowlist.

5. **Hide write controls** — on every page a read-only role can open, hide or
   disable create/edit/delete/save controls when `isReadOnly` is true. Chat is
   exempt (sending is allowed). The set of pages/controls to touch
   (Architecture, Dashboard family, Usage, Feedback for viewer; plus Agencies,
   API-keys, Users for auditor) will be enumerated in the plan by inspecting each
   page's mutation buttons. Backend block is the security boundary; this is UX.

## Testing strategy (TDD)

- **Backend (pytest):** for each new role, table-driven tests over
  `(method, path)` asserting allow/deny through the chokepoint — every matrix row
  gets a positive and a negative case (e.g. viewer `GET /api/v1/agencies` → 200
  path allowed; viewer `GET /api/v1/users` → 403; auditor `POST /api/v1/agencies`
  → 403; auditor `GET /api/v1/users` → allowed; both `POST /api/v1/chat` → allowed).
  Confirm admin/agency_owner/anonymous still pass through.
- **Frontend (vitest):** `ProtectedRoute` redirect tests per role; `AppSidebar`
  renders exactly the matrix's visible items per role; a representative page
  hides its write button when `isReadOnly`.

## Out of scope (YAGNI)

- No per-agency scoping for the new roles (global read-only only).
- No permission/capability framework (Approach B rejected).
- No new self-service signup path for these roles — assigned by an admin only.
- No DB migration (role column already accommodates the new string values).

## Files touched

**Backend:** `schemas/user.py`, `models/user.py`, `auth/dependencies.py`,
`main.py`, `routers/users.py` (verify only), plus tests.
**Frontend:** `features/auth/useAuth.tsx`, `features/auth/ProtectedRoute.tsx`,
`App.tsx`, `shared/components/layout/AppSidebar.tsx`, the read-only-affected
feature pages, plus tests.
