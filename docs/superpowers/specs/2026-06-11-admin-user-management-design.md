# Admin User Management — Design

**Date:** 2026-06-11
**Branch:** `feat/admin-user-management`
**Status:** Approved design

## Summary

Add an admin-only capability to manage other user accounts: list/search, create
(with password or email invite), edit role/profile, and soft-delete via
activate/deactivate. Full stack — backend REST endpoints plus a new frontend
`Users` admin page.

The existing `User` model already has every field needed (`email`,
`display_name`, `role`, `is_active`, `reset_token`, `reset_token_expires`,
timestamps). **No migration is required.**

## Scope

In scope:

- List & search users with filters.
- Create / invite users (admin sets password OR sends an invite email).
- Edit a user's role and display name.
- Activate / deactivate (soft-delete). **No hard delete.**
- Frontend admin `Users` page + backend API + tests.

Out of scope:

- Hard deletion of user rows.
- Bulk operations.
- Managing a user's API keys from this screen (separate `api-keys` feature).

## Architecture

New dedicated admin module, separate from the self-service `auth.py` router:

- `backend/app/routers/users.py` — REST endpoints, all behind `require_admin`.
- `backend/app/schemas/user.py` — request/response Pydantic models.
- `backend/app/services/user.py` — guardrail logic (self-action, last-admin) and
  the create/invite flow, kept out of the router for testability.
- Registered in `app/main.py`: `app.include_router(users.router, prefix="/api/v1")`.

Self-service auth (`/auth/*`) is left untouched — that surface is for the
currently authenticated user acting on themselves; this module is for an admin
acting on others.

## Backend API

All endpoints require an authenticated admin (`Depends(require_admin)`) and live
under `/api/v1/users`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/users` | List with `search` (email/display_name `icontains`), `role`, `status` (`active`/`inactive`/`all`) query filters. Returns `{data, total}`. |
| POST | `/users` | Create a user (see create flow). Returns `UserResponse`, 201. |
| GET | `/users/{id}` | Get a single user. 404 if missing. |
| PATCH | `/users/{id}` | Partial update of `display_name` and/or `role`. |
| POST | `/users/{id}/deactivate` | Soft-delete: set `is_active=false`. |
| POST | `/users/{id}/activate` | Set `is_active=true`. |

### Create flow ("Both")

`UserCreate` carries `email`, `role` (default `user`), optional `display_name`,
optional `password`, optional `send_invite: bool`.

- Exactly one of `password` / `send_invite=true` must be provided — supplying
  both or neither → 400.
- `password` path: validate length against `settings.MIN_PASSWORD_LENGTH`, hash
  via `hash_password`, store; user can log in immediately.
- `send_invite` path: create the user with an unusable random password
  (hash of a random secret), then generate a reset token via
  `generate_reset_token()` / `reset_token_expiry()`, persist it, and email it
  with `send_password_reset_email`. Response mirrors `forgot_password`: includes
  `email_sent`, and the raw `reset_token` only when the email failed AND
  `settings.EXPOSE_PASSWORD_RESET_TOKEN` is set.
- Duplicate email → 409 (matches `register`).

### Guardrails

Implemented in `services/user.py`, enforced on every mutating endpoint. The
acting admin is resolved via `require_admin`.

1. **No self-mutation by an admin on their own account.** An admin cannot change
   their own role, deactivate, or (soft-)delete themselves → 400.
2. **Protect the last active admin.** Reject any action that would leave zero
   active admins in the system — i.e. demoting the last admin to `user`, or
   deactivating the last active admin → 400. The check counts active admins
   excluding the target where relevant.

## Schemas (`schemas/user.py`)

- `UserCreate` — `email: EmailStr`, `role: Literal["user","admin"] = "user"`,
  `display_name: str | None`, `password: str | None`, `send_invite: bool = False`.
- `UserUpdate` — `display_name: str | None`, `role: Literal["user","admin"] | None`.
- `UserResponse` — camelCase to match the existing `_user_dict` shape:
  `id`, `email`, `displayName`, `role`, `avatarUrl`, plus `isActive`, `createdAt`.
- `UserListResponse` — `{ data: list[UserResponse], total: int }`.

Response building reuses/extends the camelCase convention already used in
`auth.py::_user_dict`.

## Frontend (`features/users/`)

Mirrors the structure of `features/agencies/`:

- `UsersPage.tsx` — searchable/filterable table: email, display name, role badge,
  active/inactive status, created date; row actions (edit, activate/deactivate).
- `userApi.ts` — typed fetch wrappers for the endpoints above.
- `useUsers.ts` — react-query hooks (list/query + mutations with invalidation).
- `UserFormDialog.tsx` — create/edit dialog. On create, a toggle chooses
  "set password now" vs "send invite email". On edit, role + display name.
- `DeactivateUserDialog.tsx` — confirmation for deactivate/activate.

Wiring:

- `App.tsx`: add `<Route path="/users" element={<UsersPage />} />` inside the
  `ProtectedRoute`/`AppLayout` group.
- `AppSidebar.tsx`: add a nav entry to the admin-gated `adminItems` array
  (already rendered only when `user?.role === "admin"`).

## Error handling

- 400 — validation (password length, both/neither create mode, guardrail
  violations).
- 401/403 — handled by `require_admin`.
- 404 — user not found.
- 409 — duplicate email on create.

Messages follow the existing bilingual style in `auth.py` where user-facing
(Thai), plain English for internal/guardrail detail as appropriate.

## Testing (TDD)

Backend `backend/tests/test_users.py`:

- List returns all; `search`, `role`, `status` filters narrow correctly.
- Create with password → user can authenticate.
- Create with invite → reset token issued, email send invoked (mocked).
- Create validation: both password+invite → 400; neither → 400; short password
  → 400; duplicate email → 409.
- PATCH updates display_name and role.
- Guardrail: admin acting on self → 400.
- Guardrail: demote/deactivate last active admin → 400.
- Activate/deactivate toggles `is_active`.

Frontend: a form-logic unit test analogous to `agencyForm.test.ts` covering the
create-mode toggle validation (password vs invite).

Each endpoint is built test-first: failing test → minimal implementation → pass.

## Migration

None. Existing `users` table already has all required columns.
