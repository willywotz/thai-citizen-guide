# Design: Centralize LLM purpose (backend single source of truth)

**Date:** 2026-07-23
**Status:** Approved

## Problem

The set of LLM "purposes" (which route a request to a provider+model) is duplicated
across the codebase as raw string literals:

- Partial central list already exists: `KNOWN_PURPOSES` in
  `backend/app/services/llm/client.py:13` =
  `("classification", "brief", "judge", "parse_spec", "popular_questions")`, served by
  `GET /api/v1/llm/purposes` (`backend/app/routers/llm.py:81`).
- But **5 service files hardcode the purpose string** independently instead of referencing it:
  - `services/chat/llm.py:23` → `purpose="classification"`
  - `services/analytics/brief.py:24` → `purpose="brief"`
  - `services/evaluation.py:42` → `purpose="judge"`
  - `services/agency.py:157` → `purpose="parse_spec"`
  - `services/popular_questions.py:157` → `purpose="popular_questions"`
- `services/llm/seed.py` re-lists all 5; `schemas/llm_route.py` and the DB models accept
  `purpose: str` with **no validation**; there is **no enum/type** in either language.
- The frontend already fetches purposes at runtime via `listPurposes()`; there is a stale
  test fixture using `"chat"` (not a valid purpose).

## Goal

Make the **backend the single source of truth**. One Python `StrEnum` defines every purpose;
all backend code references it; the API validates against it; the frontend re-declares
**nothing** and reads the list at runtime.

## Backend — single source of truth

### New enum (leaf module, dependency-free)
Create `backend/app/services/llm/purpose.py`:

```python
from enum import StrEnum


class Purpose(StrEnum):
    CLASSIFICATION = "classification"
    BRIEF = "brief"
    JUDGE = "judge"
    PARSE_SPEC = "parse_spec"
    POPULAR_QUESTIONS = "popular_questions"


# Serialized string values, kept for the /llm/purposes endpoint and any list use.
KNOWN_PURPOSES = tuple(p.value for p in Purpose)
```

This module imports only the stdlib, so both `app.schemas.*` and `app.services.*` can import
it without a cycle (verified: `schemas/llm_route.py` imports only stdlib + pydantic).

### Reference the enum everywhere
- `services/llm/client.py`: delete the local `KNOWN_PURPOSES`; add
  `from app.services.llm.purpose import KNOWN_PURPOSES, Purpose`; retype
  `async def chat(*, purpose: Purpose, ...)`.
- `services/llm/__init__.py`: export `Purpose` alongside the existing `KNOWN_PURPOSES`.
- The 5 call sites above: pass the enum member, e.g.
  `chat(purpose=Purpose.CLASSIFICATION, ...)` (import `Purpose` in each file).
- `services/llm/seed.py`: use `Purpose.*` members instead of the raw purpose strings.
- `models/llm_usage.py`: fix the stale purpose comment (currently lists
  `router | synthesis | classification | embedding | brief | judge`) to point at `Purpose`.
  The column stays a free-form `CharField` (usage logging), only the comment changes.

### Validation
- `schemas/llm_route.py`: import `Purpose`; change `LLMRouteBase.purpose` from `str` to
  `Purpose` (covers `LLMRouteCreate` validation and `LLMRouteResponse` output), and
  `LLMRouteUpdate.purpose` from `str | None` to `Purpose | None`. Pydantic then returns
  **422** for any purpose not in the enum. No DB migration — validation is at the API boundary;
  the model column stays `CharField`.

## Frontend — consumes the backend source, declares nothing

- **No** hardcoded purpose list and **no** TS union type. `LlmRoute.purpose` stays `string`;
  `listPurposes()` (`features/llm-routes/llmRouteApi.ts`) remains the runtime access point to
  the backend list. No change needed to `llmRouteApi.ts`.
- Delete the orphaned, now-dead components (unused since routes became edit-only in the
  LLM Settings merge): `features/llm-routes/CreateLlmRouteDialog.tsx` and
  `features/llm-routes/DeleteLlmRouteDialog.tsx`, plus any of their `*.test.tsx` files.
  Keep the `createRoute` / `deleteRoute` / `listPurposes` API wrappers — they mirror real
  backend endpoints.
- Fix the stale fixture in `features/llm/LlmSettingsPage.test.tsx` (`purpose: "chat"`) to a
  real purpose value (e.g. `"classification"`).

## Testing (TDD)

**Backend (pytest):**
- `Purpose` enum exposes exactly the 5 expected members/values; `KNOWN_PURPOSES` equals their
  values (order preserved).
- `GET /api/v1/llm/purposes` still returns `list(KNOWN_PURPOSES)`
  (existing `tests/routers/test_llm_admin.py:150-151` must stay green).
- Creating a route with an **invalid** purpose (e.g. `"nope"`) returns **422**; creating with a
  valid `Purpose` value succeeds.

**Frontend (vitest):**
- Existing suite stays green after the stale-fixture fix and dialog deletions; no references to
  the deleted dialogs remain.

## Out of scope

- No DB enum constraint or Alembic/migration change.
- No OpenAPI/codegen pipeline.
- No routing/UI behavior changes; no changes to the `/llm/purposes` endpoint contract.
