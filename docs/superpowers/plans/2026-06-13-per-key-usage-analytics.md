# Per-API-Key Usage Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Attribute every `LlmUsage` record to the API key (and user) that drove it, and surface per-key token/cost totals to admins via an endpoint and a new admin page.

**Architecture:** A request-scoped `ContextVar` is set in the auth dependency when a token resolves, and read by the usage writer — so attribution crosses all service layers without threading a parameter through every call site. The existing grouped-usage endpoint gains an `api_key` group mode (with metadata enrichment), a catch-all bucket for keyless usage, and a UTC date-range filter. A React admin page mirrors the existing audit-log page.

**Tech Stack:** Python 3.12, FastAPI, Tortoise ORM, Aerich migrations, pytest-asyncio (SQLite in-memory). Frontend: React + TypeScript, TanStack Query, shadcn/ui.

**Spec:** `docs/superpowers/specs/2026-06-13-per-key-usage-analytics-design.md`

---

## File Structure

| File | Responsibility | Action |
|------|----------------|--------|
| `backend/app/models/llm_usage.py` | Add `api_key_id` column | Modify |
| `backend/migrations/models/15_*_llm_usage_api_key_id.py` | Schema migration | Create (via aerich) |
| `backend/app/services/usage_context.py` | Request-scoped attribution ContextVars | Create |
| `backend/app/services/llm_client.py` | Read attribution from ContextVars when writing usage | Modify |
| `backend/app/auth/dependencies.py` | Set ContextVars on token resolution | Modify |
| `backend/app/routers/insight.py` | `api_key` group mode + date filter + enrichment | Modify |
| `frontend/src/features/usage/usageApi.ts` | API client + types | Create |
| `frontend/src/features/usage/useUsage.ts` | React Query hook | Create |
| `frontend/src/features/usage/UsageAnalyticsPage.tsx` | Admin page | Create |
| `frontend/src/App.tsx` | Route | Modify |
| `frontend/src/shared/components/layout/AppSidebar.tsx` | Nav link | Modify |

**Conventions confirmed from the codebase:**
- Backend tests live in `backend/tests/`, use the `db` fixture (in-memory SQLite via `Tortoise.generate_schemas()`), `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed).
- `LlmUsage.user_id`/`agency_id` are plain `fields.UUIDField(null=True)` — **not** `ForeignKeyField`. `api_key_id` follows the same pattern.
- Run backend commands from `backend/`. Tests: `rtk pytest tests/<file>::<test> -v`.

---

## Task 1: Add `api_key_id` to LlmUsage model

**Files:**
- Modify: `backend/app/models/llm_usage.py:8-27`
- Test: `backend/tests/test_llm_usage_model.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_llm_usage_model.py`:

```python
async def test_usage_row_stores_api_key_id(db):
    from uuid import uuid4
    kid = uuid4()
    row = await LlmUsage.create(
        model="m", purpose="classification",
        prompt_tokens=1, completion_tokens=1, api_key_id=kid,
    )
    assert row.api_key_id == kid
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk pytest tests/test_llm_usage_model.py::test_usage_row_stores_api_key_id -v`
Expected: FAIL — `TypeError` / unexpected keyword `api_key_id` (column does not exist).

- [ ] **Step 3: Add the column**

In `backend/app/models/llm_usage.py`, add the field directly after the `conversation_id` line:

```python
    conversation_id = fields.UUIDField(null=True)
    api_key_id = fields.UUIDField(null=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk pytest tests/test_llm_usage_model.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
rtk git add backend/app/models/llm_usage.py backend/tests/test_llm_usage_model.py
rtk git commit -m "feat(usage): add api_key_id to LlmUsage model"
```

---

## Task 2: Aerich migration for the new column

**Files:**
- Create: `backend/migrations/models/15_<timestamp>_llm_usage_api_key_id.py` (generated)

The latest migration is `14_*_api_key_lifecycle.py`, so this becomes migration 15. Aerich autogenerates the file (including the `MODELS_STATE` snapshot) — do **not** hand-write that blob.

- [ ] **Step 1: Generate the migration**

Run (from `backend/`, requires the configured Postgres reachable):

```bash
rtk proxy aerich migrate --name llm_usage_api_key_id
```

- [ ] **Step 2: Verify the generated SQL**

Open the new `backend/migrations/models/15_*_llm_usage_api_key_id.py` and confirm `upgrade()` contains exactly:

```sql
ALTER TABLE "llm_usage" ADD "api_key_id" UUID;
```

and `downgrade()` contains:

```sql
ALTER TABLE "llm_usage" DROP COLUMN "api_key_id";
```

If aerich produced extra unrelated statements, the model state was stale — discard the file, run `rtk proxy aerich migrate` again only after confirming no other model changes are pending.

> **Fallback if aerich/Postgres is unavailable in this environment:** skip generation and note in the commit that migration 15 must be generated before deploy. Do NOT hand-author the `MODELS_STATE` blob. Tests in this plan use SQLite `generate_schemas()` and do not depend on the migration.

- [ ] **Step 3: Apply and confirm**

```bash
rtk proxy aerich upgrade
```

Expected: applies migration 15 with no error.

- [ ] **Step 4: Commit**

```bash
rtk git add backend/migrations/models/
rtk git commit -m "chore(db): migration for llm_usage.api_key_id"
```

---

## Task 3: Attribution ContextVars + usage writer wiring

**Files:**
- Create: `backend/app/services/usage_context.py`
- Modify: `backend/app/services/llm_client.py:35-50`
- Test: `backend/tests/test_llm_client.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_llm_client.py`:

```python
async def test_records_attribution_from_context(db, monkeypatch):
    from uuid import uuid4
    from app.services.usage_context import current_user_id, current_api_key_id

    async def fake_post(self, url, **kwargs):
        return _FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    uid, kid = uuid4(), uuid4()
    ut = current_user_id.set(uid)
    kt = current_api_key_id.set(kid)
    try:
        await llm_client.openrouter_chat(
            {"model": "m", "messages": []}, purpose="classification",
        )
    finally:
        current_user_id.reset(ut)
        current_api_key_id.reset(kt)

    row = await LlmUsage.first()
    assert row.user_id == uid
    assert row.api_key_id == kid
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk pytest tests/test_llm_client.py::test_records_attribution_from_context -v`
Expected: FAIL — `ModuleNotFoundError: app.services.usage_context`.

- [ ] **Step 3: Create the ContextVars module**

Create `backend/app/services/usage_context.py`:

```python
"""Request-scoped attribution for LLM usage records.

Each FastAPI request runs in its own asyncio task, which copies the context,
so values set here during request handling are isolated per request.
"""
from contextvars import ContextVar
from uuid import UUID

current_user_id: ContextVar[UUID | None] = ContextVar("current_user_id", default=None)
current_api_key_id: ContextVar[UUID | None] = ContextVar("current_api_key_id", default=None)
```

- [ ] **Step 3b: Add an autouse reset fixture (prevents cross-test leakage)**

Because the auth dependency (Task 4) sets these ContextVars and tests run sequentially in one context, a set without reset would leak into later tests. Add to `backend/tests/conftest.py`:

```python
@pytest_asyncio.fixture(autouse=True)
async def _reset_usage_context():
    from app.services.usage_context import current_api_key_id, current_user_id
    ut = current_user_id.set(None)
    kt = current_api_key_id.set(None)
    try:
        yield
    finally:
        current_user_id.reset(ut)
        current_api_key_id.reset(kt)
```

- [ ] **Step 4: Read the ContextVars in the usage writer**

In `backend/app/services/llm_client.py`, add the import after the existing imports:

```python
from app.services.usage_context import current_api_key_id, current_user_id
```

Replace `_record_usage` (lines 35-50) with:

```python
async def _record_usage(resp, payload, purpose, user_id, agency_id, conversation_id) -> None:
    try:
        body = resp.json()
        usage = body.get("usage") or {}
        await LlmUsage.create(
            model=body.get("model") or payload.get("model", ""),
            purpose=purpose,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            cost_usd=usage.get("cost"),
            user_id=user_id if user_id is not None else current_user_id.get(),
            agency_id=agency_id,
            conversation_id=conversation_id,
            api_key_id=current_api_key_id.get(),
        )
    except Exception:  # accounting must never break the chat path
        logger.exception("failed to record llm usage")
```

An explicitly-passed `user_id` still wins (background jobs pass it / stay None); request-driven calls fall back to the ContextVar.

- [ ] **Step 5: Run tests to verify they pass**

Run: `rtk pytest tests/test_llm_client.py -v`
Expected: PASS (both `test_openrouter_chat_records_usage` and the new test).

- [ ] **Step 6: Commit**

```bash
rtk git add backend/app/services/usage_context.py backend/app/services/llm_client.py backend/tests/test_llm_client.py
rtk git commit -m "feat(usage): record api_key_id/user_id from request context"
```

---

## Task 4: Set ContextVars in the auth dependency

**Files:**
- Modify: `backend/app/auth/dependencies.py:38-74`
- Test: `backend/tests/test_api_key_rest_auth.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_api_key_rest_auth.py`:

```python
async def test_resolve_sets_context_for_api_key(db):
    from app.auth.dependencies import _resolve_token
    from app.services.usage_context import current_user_id, current_api_key_id

    user, raw, key = await _user_with_key("ctx@x.com")
    resolved = await _resolve_token(raw)

    assert resolved.id == user.id
    assert current_user_id.get() == user.id
    assert current_api_key_id.get() == key.id


async def test_resolve_sets_user_only_for_jwt(db):
    from app.auth.dependencies import _resolve_token
    from app.services.usage_context import current_user_id, current_api_key_id

    user = await User.create(email="jwt@x.com", hashed_password="h", is_active=True)
    token = create_access_token({"sub": str(user.id)})
    resolved = await _resolve_token(token)

    assert resolved.id == user.id
    assert current_user_id.get() == user.id
    assert current_api_key_id.get() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk pytest tests/test_api_key_rest_auth.py::test_resolve_sets_context_for_api_key tests/test_api_key_rest_auth.py::test_resolve_sets_user_only_for_jwt -v`
Expected: FAIL — ContextVars are never set (`None`, not the expected ids).

- [ ] **Step 3: Set the ContextVars in `_resolve_token`**

In `backend/app/auth/dependencies.py`, add the import after the existing `app.*` imports:

```python
from app.services.usage_context import current_api_key_id, current_user_id
```

In the API-key branch, set both ContextVars just before `return user` (after the `last_used_at` save at line 64):

```python
        api_key.last_used_at = now()
        await api_key.save(update_fields=["last_used_at"])
        current_user_id.set(user.id)
        current_api_key_id.set(api_key.id)
        return user
```

In the JWT branch, set the user ContextVar before returning. Replace the final two lines (73-74):

```python
    user = await User.filter(id=user_id, is_active=True).first()
    if user is not None:
        current_user_id.set(user.id)
    return user
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk pytest tests/test_api_key_rest_auth.py -v`
Expected: PASS (all tests, including the pre-existing ones).

- [ ] **Step 5: Commit**

```bash
rtk git add backend/app/auth/dependencies.py backend/tests/test_api_key_rest_auth.py
rtk git commit -m "feat(auth): populate usage attribution context on token resolve"
```

---

## Task 5: Endpoint — `api_key` group mode, date filter, enrichment

**Files:**
- Modify: `backend/app/routers/insight.py:18-37` and `:207-209`
- Test: `backend/tests/test_usage_endpoint.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_usage_endpoint.py`:

```python
async def test_usage_groups_by_api_key_with_metadata(db):
    from app.models.user import User, UserAPIKey
    user = await User.create(email="owner@x.com", hashed_password="h", is_active=True)
    key = await UserAPIKey.create(user_id=user.id, name="prod", key_hash="h1", key_prefix="tcg_abc123")

    await LlmUsage.create(model="m", purpose="router", prompt_tokens=10, completion_tokens=2,
                          cost_usd=0.01, api_key_id=key.id)
    await LlmUsage.create(model="m", purpose="router", prompt_tokens=5, completion_tokens=1,
                          cost_usd=0.02)  # keyless

    rows = await usage_summary(group_by="api_key")
    by_key = {r["key"]: r for r in rows}

    keyed = by_key[str(key.id)]
    assert keyed["prompt_tokens"] == 10
    assert keyed["name"] == "prod"
    assert keyed["key_prefix"] == "tcg_abc123"
    assert keyed["owner_email"] == "owner@x.com"

    bucket = by_key["—"]
    assert bucket["prompt_tokens"] == 5
    assert bucket["name"] == "web/session"


async def test_usage_date_filter(db):
    from datetime import datetime, timezone
    old = await LlmUsage.create(model="m", purpose="router", prompt_tokens=1, completion_tokens=0)
    await LlmUsage.filter(id=old.id).update(created_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
    await LlmUsage.create(model="m", purpose="router", prompt_tokens=9, completion_tokens=0)

    rows = await usage_summary(group_by="purpose", date_from=datetime(2021, 1, 1, tzinfo=timezone.utc))
    by_key = {r["key"]: r for r in rows}
    assert by_key["router"]["prompt_tokens"] == 9
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk pytest tests/test_usage_endpoint.py -v`
Expected: FAIL — `usage_summary` rejects `date_from`, has no `api_key` mode / metadata keys.

- [ ] **Step 3: Update `usage_summary` and the route**

In `backend/app/routers/insight.py`, update imports at the top — add `datetime`, `Query`, and `User`/`UserAPIKey`:

```python
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from app.models.user import User, UserAPIKey
```

Replace `_GROUP_FIELDS` and `usage_summary` (lines 18-37) with:

```python
_GROUP_FIELDS = {"purpose": "purpose", "model": "model", "user": "user_id", "api_key": "api_key_id"}


async def _enrich_api_keys(rows: list[dict]) -> None:
    ids = [r["key"] for r in rows if r["key"] is not None]
    keys = await UserAPIKey.filter(id__in=ids) if ids else []
    users = await User.filter(id__in={k.user_id for k in keys}) if keys else []
    email_by_user = {str(u.id): u.email for u in users}
    meta = {str(k.id): (k.name, k.key_prefix, email_by_user.get(str(k.user_id))) for k in keys}
    for r in rows:
        info = meta.get(r["key"]) if r["key"] is not None else None
        if info is not None:
            r["name"], r["key_prefix"], r["owner_email"] = info
        else:
            r["key"] = "—"
            r["name"], r["key_prefix"], r["owner_email"] = "web/session", "—", None


async def usage_summary(group_by: str = "purpose", date_from: datetime | None = None,
                        date_to: datetime | None = None) -> list[dict]:
    field = _GROUP_FIELDS.get(group_by, "purpose")
    qs = LlmUsage.all()
    if date_from is not None:
        qs = qs.filter(created_at__gte=date_from)
    if date_to is not None:
        qs = qs.filter(created_at__lt=date_to)
    rows = (
        await qs
        .annotate(prompt=Sum("prompt_tokens"), completion=Sum("completion_tokens"), cost=Sum("cost_usd"))
        .group_by(field)
        .values(field, "prompt", "completion", "cost")
    )
    result = [
        {
            "key": str(r[field]) if r[field] is not None else None,
            "prompt_tokens": r["prompt"] or 0,
            "completion_tokens": r["completion"] or 0,
            "cost_usd": round(r["cost"] or 0.0, 6),
        }
        for r in rows
    ]
    if group_by == "api_key":
        await _enrich_api_keys(result)
    return result
```

Replace the route (lines 207-209) with:

```python
@router.get("/insight/usage", summary="LLM token/cost usage grouped")
async def get_usage(
    group_by: str = "purpose",
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
    _admin: User = Depends(require_admin),
):
    return await usage_summary(group_by=group_by, date_from=date_from, date_to=date_to)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk pytest tests/test_usage_endpoint.py -v`
Expected: PASS (all four tests).

- [ ] **Step 5: Lint (if configured)**

Run: `cd backend && rtk proxy ruff check app/routers/insight.py --fix || true`
This change is Python-only; skip if the project has no ruff config.

- [ ] **Step 6: Commit**

```bash
rtk git add backend/app/routers/insight.py backend/tests/test_usage_endpoint.py
rtk git commit -m "feat(usage): per-api-key grouping, metadata enrichment, date filter"
```

---

## Task 6: Frontend API client + hook

**Files:**
- Create: `frontend/src/features/usage/usageApi.ts`
- Create: `frontend/src/features/usage/useUsage.ts`

- [ ] **Step 1: Create the API client**

Create `frontend/src/features/usage/usageApi.ts`:

```typescript
import { api } from '@/shared/lib/apiClient';

export interface UsageRow {
  key: string;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
  name?: string;
  key_prefix?: string;
  owner_email?: string | null;
}

export interface UsageParams {
  group_by: 'api_key';
  from?: string;
  to?: string;
}

export async function getUsage(params: UsageParams): Promise<UsageRow[]> {
  return api.get<UsageRow[]>('/api/v1/insight/usage', params);
}
```

- [ ] **Step 2: Create the React Query hook**

Create `frontend/src/features/usage/useUsage.ts`:

```typescript
import { useQuery } from '@tanstack/react-query';
import { getUsage, type UsageParams } from './usageApi';

const KEY = 'usage-analytics';

export function useUsage(params: UsageParams) {
  return useQuery({
    queryKey: [KEY, params],
    queryFn: () => getUsage(params),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });
}
```

- [ ] **Step 3: Type-check**

Run: `cd frontend && rtk tsc --noEmit`
Expected: no errors from the new files.

- [ ] **Step 4: Commit**

```bash
rtk git add frontend/src/features/usage/usageApi.ts frontend/src/features/usage/useUsage.ts
rtk git commit -m "feat(usage): frontend api client + query hook"
```

---

## Task 7: Frontend admin page

**Files:**
- Create: `frontend/src/features/usage/UsageAnalyticsPage.tsx`

- [ ] **Step 1: Create the page**

Create `frontend/src/features/usage/UsageAnalyticsPage.tsx` (mirrors `features/audit/AuditLogPage.tsx` structure):

```tsx
import { useState } from 'react';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/shared/components/ui/table';
import { Input } from '@/shared/components/ui/input';
import { BarChart3 } from 'lucide-react';
import { useUsage } from './useUsage';

export default function UsageAnalyticsPage() {
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');

  const { data, isLoading, isError } = useUsage({
    group_by: 'api_key',
    from: from ? new Date(from).toISOString() : undefined,
    to: to ? new Date(to).toISOString() : undefined,
  });

  const rows = data ?? [];

  return (
    <div className="p-4 md:p-6 space-y-4">
      <div className="flex items-center gap-2">
        <BarChart3 className="h-5 w-5 text-primary" />
        <h1 className="text-2xl font-semibold">การใช้งานต่อ API Key</h1>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm text-muted-foreground">ตั้งแต่</label>
        <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="max-w-[12rem]" />
        <label className="text-sm text-muted-foreground">ถึง</label>
        <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="max-w-[12rem]" />
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>API Key</TableHead>
            <TableHead>เจ้าของ</TableHead>
            <TableHead className="text-right">Prompt</TableHead>
            <TableHead className="text-right">Completion</TableHead>
            <TableHead className="text-right">รวม</TableHead>
            <TableHead className="text-right">ค่าใช้จ่าย (USD)</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading && (
            <TableRow><TableCell colSpan={6}>กำลังโหลด...</TableCell></TableRow>
          )}
          {isError && !isLoading && (
            <TableRow><TableCell colSpan={6}>เกิดข้อผิดพลาดในการโหลดข้อมูล</TableCell></TableRow>
          )}
          {!isLoading && !isError && rows.length === 0 && (
            <TableRow><TableCell colSpan={6}>ไม่พบข้อมูล</TableCell></TableRow>
          )}
          {rows.map((r) => (
            <TableRow key={r.key}>
              <TableCell>
                <div className="font-medium">{r.name ?? r.key}</div>
                {r.key_prefix && r.key_prefix !== '—' && (
                  <div className="text-xs text-muted-foreground">{r.key_prefix}</div>
                )}
              </TableCell>
              <TableCell className="text-sm">{r.owner_email ?? '—'}</TableCell>
              <TableCell className="text-right tabular-nums">{r.prompt_tokens.toLocaleString()}</TableCell>
              <TableCell className="text-right tabular-nums">{r.completion_tokens.toLocaleString()}</TableCell>
              <TableCell className="text-right tabular-nums">
                {(r.prompt_tokens + r.completion_tokens).toLocaleString()}
              </TableCell>
              <TableCell className="text-right tabular-nums">${r.cost_usd.toFixed(6)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && rtk tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
rtk git add frontend/src/features/usage/UsageAnalyticsPage.tsx
rtk git commit -m "feat(usage): admin per-key usage analytics page"
```

---

## Task 8: Route + sidebar nav (admin-only)

**Files:**
- Modify: `frontend/src/App.tsx:31` (import) and `:70-71` (route)
- Modify: `frontend/src/shared/components/layout/AppSidebar.tsx` (admin nav group, near the `/audit-log` entry around line 40)

- [ ] **Step 1: Add the import**

In `frontend/src/App.tsx`, after the `AuditLogPage` import (line 31):

```tsx
import AuditLogPage from "@/features/audit/AuditLogPage";
import UsageAnalyticsPage from "@/features/usage/UsageAnalyticsPage";
```

- [ ] **Step 2: Add the route**

In `frontend/src/App.tsx`, after the `/audit-log` route (line 70):

```tsx
<Route path="/audit-log" element={<ProtectedRoute requireAdmin><AuditLogPage /></ProtectedRoute>} />
<Route path="/usage" element={<ProtectedRoute requireAdmin><UsageAnalyticsPage /></ProtectedRoute>} />
```

- [ ] **Step 3: Add the sidebar link**

In `frontend/src/shared/components/layout/AppSidebar.tsx`, find the admin nav entry for `บันทึกการตรวจสอบ` (`/audit-log`, icon `ScrollText`). Add `BarChart3` to the existing `lucide-react` import, then add a sibling entry directly after the audit-log one:

```tsx
{ title: "การใช้งาน API Key", url: "/usage", icon: BarChart3 },
```

Match the exact object shape and array used by the neighbouring admin items (the audit-log/users entries are in the admin-only group).

- [ ] **Step 4: Type-check and verify the nav renders**

Run: `cd frontend && rtk tsc --noEmit`
Expected: no errors.

Run the app and confirm (as an admin user) the "การใช้งาน API Key" link appears in the sidebar and `/usage` renders the table:

```bash
cd frontend && rtk npm run dev
```

- [ ] **Step 5: Commit**

```bash
rtk git add frontend/src/App.tsx frontend/src/shared/components/layout/AppSidebar.tsx
rtk git commit -m "feat(usage): route + sidebar nav for per-key usage page"
```

---

## Final verification

- [ ] **Backend full suite**

Run: `cd backend && rtk pytest tests/ -q`
Expected: all pass.

- [ ] **Frontend type-check + lint**

Run: `cd frontend && rtk tsc --noEmit && rtk lint`
Expected: no errors.

- [ ] **Manual smoke (admin login → `/usage`)**

Confirm: keyed rows show name/prefix/owner; keyless usage collapses into the single "— / web/session" row; date filter narrows results; totals reconcile against `group_by=purpose`.

---

## Notes / out of scope

- Per-key drill-down (by model/purpose or time series) — not in this iteration.
- Backfilling attribution onto historical rows — impossible (data unavailable); they fall into the catch-all bucket.
- Multi-worker rate limiting (Redis) — tracked separately.
```
