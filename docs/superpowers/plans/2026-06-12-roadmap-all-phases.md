# Roadmap Implementation Plan — All Phases (spec/roadmap.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all 6 phases of `spec/roadmap.md`: security hardening + CI, usage/cost tracking + rate limits + quotas, reliability (retry/breaker/error envelope/cache flush), consolidation cleanups, ReBAC+ABAC authorization + agency self-service, and quality/trust features.

**Architecture:** FastAPI + Tortoise ORM (Postgres/pgvector, aerich migrations, in-memory SQLite for tests), Go agent-proxy, React/Vite frontend. Each phase is an independent branch + PR. New cross-cutting modules: `app/services/llm_client.py` (usage-recording OpenRouter wrapper), `app/services/rate_limit.py`, `app/errors.py` (error envelope), `app/auth/authz.py` (RBAC→ReBAC→ABAC decision point).

**Tech Stack:** Python 3.12, pytest + pytest-asyncio (`db` fixture = in-memory SQLite), uv, aerich, httpx, APScheduler, React + TypeScript, GitHub Actions.

**Conventions for every task (do not repeat per task):**
- All shell commands prefixed with `rtk`. Backend commands run from `backend/`: `uv run pytest …`, `uv run aerich migrate --name <n> && uv run aerich upgrade`.
- Each phase starts with `rtk git checkout -b <branch>` from up-to-date `main` and ends with a PR (`superpowers:finishing-a-development-branch`).
- TDD: write the failing test, run it (expect FAIL), implement minimally, run again (expect PASS), commit.
- After Python changes: `uv run pytest` (full suite) before each commit.
- New models must be importable via `app.models` — add the import to `backend/app/models/__init__.py` when a task creates a model.

---

## Phase 1 — Security & CI safety net

Branch: `feat/phase1-security-ci`

### Task 1: CI test workflow gating deploy

**Files:**
- Create: `.github/workflows/test.yml`
- Modify: `.github/workflows/deploy.yml`

- [ ] **Step 1: Create the test workflow**

```yaml
# .github/workflows/test.yml
name: Test

on:
  pull_request:
  push:
    branches: [main]
  workflow_call:

jobs:
  backend:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: backend } }
    steps:
      - uses: actions/checkout@v6.0.3
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --extra dev
      - run: uv run pytest -q

  agent-proxy:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: agent-proxy } }
    steps:
      - uses: actions/checkout@v6.0.3
      - uses: actions/setup-go@v5
        with: { go-version-file: agent-proxy/go.mod }
      - run: go build ./... && go test ./...

  frontend:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: frontend } }
    steps:
      - uses: actions/checkout@v6.0.3
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: pnpm, cache-dependency-path: frontend/pnpm-lock.yaml }
      - run: pnpm install --frozen-lockfile
      - run: pnpm exec tsc --noEmit
```

(If `frontend/package.json` has a `typecheck` or `build` script, use that instead of raw `tsc --noEmit` — check first with `rtk read frontend/package.json`.)

- [ ] **Step 2: Gate deploy on tests** — in `.github/workflows/deploy.yml` add a `test` job and make `deploy` need it:

```yaml
  test:
    needs: check-deploy
    if: ${{ needs.check-deploy.outputs.deploy == 'true' }}
    uses: ./.github/workflows/test.yml

  deploy:
    runs-on: self-hosted
    needs: [check-deploy, test]
    if: ${{ needs.check-deploy.outputs.deploy == 'true' }}
```

- [ ] **Step 3: Verify locally what CI will run**: `cd backend && uv run pytest -q` → all pass; `cd agent-proxy && go test ./...` → pass.
- [ ] **Step 4: Commit** — `ci: run backend/go/frontend tests and gate deploy on them`
- [ ] **Step 5: After push, verify**: `rtk gh run list --limit 3` shows the Test workflow green.

### Task 2: Refuse production boot with default JWT secret

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py` (startup/lifespan — call the guard once at app start)
- Test: `backend/tests/test_config_guard.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_config_guard.py
import pytest

from app.config import Settings, assert_production_secrets, DEFAULT_JWT_SECRET


def test_production_with_default_secret_raises():
    s = Settings(ENV="production", JWT_SECRET=DEFAULT_JWT_SECRET)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        assert_production_secrets(s)


def test_production_with_real_secret_passes():
    assert_production_secrets(Settings(ENV="production", JWT_SECRET="x" * 64))


def test_development_with_default_secret_passes():
    assert_production_secrets(Settings(ENV="development", JWT_SECRET=DEFAULT_JWT_SECRET))
```

- [ ] **Step 2: Run** `uv run pytest tests/test_config_guard.py -v` → FAIL (`ImportError: assert_production_secrets`).
- [ ] **Step 3: Implement in `config.py`**

```python
# In Settings class, under "── App ──":
    ENV: str = "development"  # development | production

# Module level, after the Settings class:
DEFAULT_JWT_SECRET = "change-me-in-production-use-a-long-random-string"


def assert_production_secrets(s: "Settings") -> None:
    if s.ENV == "production" and s.JWT_SECRET == DEFAULT_JWT_SECRET:
        raise RuntimeError("JWT_SECRET must be changed when ENV=production")
```

In `main.py`, at the top of the startup/lifespan function (find it: `rtk grep -n "lifespan\|on_event\|startup" backend/app/main.py`), add `assert_production_secrets(settings)`. Add `ENV` to `SETTINGS_GROUPS["App"]`.

- [ ] **Step 4: Run** the test file (PASS) then the full suite.
- [ ] **Step 5: Commit** — `feat(config): refuse production startup with default JWT secret`. Also add `ENV=production` to the `.env` heredoc in `.github/workflows/deploy.yml` and a `JWT_SECRET=${{ secrets.JWT_SECRET }}` line (create the GitHub secret; note this for the user in the PR description).

### Task 3: Hash user API keys (columns + create/verify path)

**Files:**
- Modify: `backend/app/models/user.py`, `backend/app/auth/security.py`, `backend/app/routers/api_key.py`, `backend/app/mcp/server.py`
- Test: `backend/tests/test_api_key_hashing.py`
- Create migration via aerich.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_api_key_hashing.py
import hashlib

from app.auth.security import hash_api_key, generate_api_key
from app.models.user import User, UserAPIKey


def test_hash_api_key_is_sha256_hex():
    assert hash_api_key("abc") == hashlib.sha256(b"abc").hexdigest()


def test_generate_api_key_has_prefix():
    raw = generate_api_key()
    assert raw.startswith("tcg_") and len(raw) > 30


async def test_create_key_stores_hash_not_plaintext(db):
    user = await User.create(email="k@x.com", hashed_password="h")
    raw = generate_api_key()
    key = await UserAPIKey.create(
        user_id=user.id, name="n",
        key_hash=hash_api_key(raw), key_prefix=raw[:12],
    )
    assert key.key_hash != raw
    assert await UserAPIKey.filter(key_hash=hash_api_key(raw)).first() is not None
```

- [ ] **Step 2: Run** → FAIL (no `hash_api_key`, no `key_hash` field).
- [ ] **Step 3: Implement.** In `auth/security.py`:

```python
import hashlib

API_KEY_PREFIX = "tcg_"


def generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

In `models/user.py`, on `UserAPIKey` replace the plaintext design (keep `key` nullable for the backfill window):

```python
    key = fields.CharField(max_length=255, unique=True, null=True)  # legacy; dropped in Task 4
    key_hash = fields.CharField(max_length=64, unique=True, null=True)
    key_prefix = fields.CharField(max_length=16, default="")
    last_used_at = fields.DatetimeField(null=True)
```

- [ ] **Step 4: Rewrite `routers/api_key.py`** — response no longer exposes the key except once at creation:

```python
class APIKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    last_used_at: str | None
    created_at: str


class CreatedAPIKeyResponse(APIKeyResponse):
    key: str  # full key — shown only in the create response


def _resp(k: UserAPIKey) -> APIKeyResponse:
    return APIKeyResponse(
        id=str(k.id), name=k.name, key_prefix=k.key_prefix,
        last_used_at=str(k.last_used_at) if k.last_used_at else None,
        created_at=str(k.created_at),
    )
```

`create_api_key` becomes:

```python
    raw = generate_api_key()
    new_key = await UserAPIKey.create(
        user_id=user.id, name=body.name,
        key_hash=hash_api_key(raw), key_prefix=raw[:12],
    )
    return CreatedAPIKeyResponse(**_resp(new_key).model_dump(), key=raw)
```

List/rename return `_resp(k)`. In `backend/app/mcp/server.py` find the bearer lookup (`rtk grep -n "UserAPIKey" backend/app/mcp/server.py`) and change `filter(key=token)` to:

```python
    api_key = await UserAPIKey.filter(key_hash=hash_api_key(token)).first()
    if api_key:
        api_key.last_used_at = now()
        await api_key.save(update_fields=["last_used_at"])
```

(`now` from `app.utils`.) Keep a fallback `or await UserAPIKey.filter(key=token).first()` until Task 4 drops the column.

- [ ] **Step 5: Migration**: `uv run aerich migrate --name api_key_hashing && uv run aerich upgrade`.
- [ ] **Step 6: Run** new test file + full suite → PASS.
- [ ] **Step 7: Frontend** — `rtk grep -rn "\.key" frontend/src/features/api-keys frontend/src --include=*.tsx -l` and update `ApiKeysPage.tsx` + its API types: list rows show `key_prefix` + "…" instead of `key`; on create, show the returned `key` once in a copy-to-clipboard dialog with a "you won't see this again" note.
- [ ] **Step 8: Commit** — `feat(auth): store API keys as sha256 hashes, show raw key once`

### Task 4: Backfill + drop plaintext key column

**Files:**
- Create: `backend/scripts/hash_existing_api_keys.py`
- Modify: `backend/app/models/user.py`, `backend/app/mcp/server.py`

- [ ] **Step 1: Write the backfill script**

```python
# backend/scripts/hash_existing_api_keys.py
"""One-off: hash legacy plaintext API keys in place. Run: uv run python scripts/hash_existing_api_keys.py"""
import asyncio

from tortoise import Tortoise

from app.auth.security import hash_api_key
from app.config import TORTOISE_ORM
from app.models.user import UserAPIKey


async def main() -> None:
    await Tortoise.init(config=TORTOISE_ORM)
    legacy = await UserAPIKey.filter(key_hash=None).exclude(key=None)
    for k in legacy:
        k.key_hash = hash_api_key(k.key)
        k.key_prefix = k.key[:12]
        await k.save(update_fields=["key_hash", "key_prefix"])
    print(f"hashed {len(legacy)} keys")
    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run it against the dev database** (`uv run python scripts/hash_existing_api_keys.py`) → prints count, no errors.
- [ ] **Step 3: Drop the legacy column**: delete the `key` field line from `UserAPIKey`, delete the `or filter(key=token)` fallback in `mcp/server.py`, then `uv run aerich migrate --name drop_plaintext_api_key && uv run aerich upgrade`.
- [ ] **Step 4: Full suite → PASS. Commit** — `chore(auth): backfill hashes and drop plaintext api key column`. PR note: run the backfill script in production BEFORE deploying the drop migration.

### Task 5: Sanitize connection-log bodies

**Files:**
- Create: `backend/app/services/log_sanitize.py`
- Modify: `backend/app/config.py`, every `ConnectionLog.create` call site (`rtk grep -rn "ConnectionLog.create" backend/app` — currently `app/scheduler.py` and sites in `app/services/agency.py` / `app/routers/chat.py`)
- Test: `backend/tests/test_log_sanitize.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_log_sanitize.py
from app.services.log_sanitize import sanitize_body, sanitize_headers


def test_truncates_long_bodies():
    out = sanitize_body("x" * 10_000, max_chars=100)
    assert len(out) <= 100 + len("…[truncated]") and out.endswith("…[truncated]")


def test_short_body_unchanged():
    assert sanitize_body("hello", max_chars=100) == "hello"


def test_none_becomes_empty():
    assert sanitize_body(None) == ""


def test_redacts_auth_headers():
    out = sanitize_headers({"Authorization": "Bearer s3cret", "X-Api-Key": "k", "accept": "json"})
    assert out["Authorization"] == "[REDACTED]" and out["X-Api-Key"] == "[REDACTED]"
    assert out["accept"] == "json"
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement**

```python
# backend/app/services/log_sanitize.py
"""Sanitize request/response data before persisting to ConnectionLog (PDPA)."""
from app.config import settings

_REDACTED = "[REDACTED]"
_SENSITIVE = {"authorization", "apikey", "api-key", "x-api-key", "cookie"}


def sanitize_body(text: str | None, max_chars: int | None = None) -> str:
    if not text:
        return ""
    limit = max_chars or settings.CONNECTION_LOG_BODY_MAX_CHARS
    if len(text) <= limit:
        return text
    return text[:limit] + "…[truncated]"


def sanitize_headers(headers: dict) -> dict:
    return {k: (_REDACTED if k.lower() in _SENSITIVE else v) for k, v in headers.items()}
```

Add to `Settings`: `CONNECTION_LOG_BODY_MAX_CHARS: int = 4096` (group: "Agency health"). At every `ConnectionLog.create` call site wrap body kwargs, e.g. in `app/scheduler.py`:

```python
                        detail=sanitize_body(f"Query: {payload.get('query', '')}\n\nAnswer: {resp.text}"),
                        request_body=sanitize_body(json.dumps(payload)),
                        response_body=sanitize_body(resp.text),
```

- [ ] **Step 4: Run full suite → PASS. Commit** — `feat(logs): truncate bodies and redact auth headers in connection logs`

### Task 6: Connection-log retention job

**Files:**
- Modify: `backend/app/scheduler.py`, `backend/app/config.py`
- Test: `backend/tests/test_log_retention.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_log_retention.py
from datetime import timedelta

from app.models import ConnectionLog
from app.scheduler import purge_old_connection_logs
from app.utils import now


async def test_purges_only_logs_older_than_retention(db):
    old = await ConnectionLog.create(connection_type="API", status="success")
    await ConnectionLog.filter(id=old.id).update(created_at=now() - timedelta(days=120))
    fresh = await ConnectionLog.create(connection_type="API", status="success")

    deleted = await purge_old_connection_logs()

    assert deleted == 1
    assert await ConnectionLog.filter(id=old.id).first() is None
    assert await ConnectionLog.filter(id=fresh.id).first() is not None
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement** — `Settings`: `CONNECTION_LOG_RETENTION_DAYS: int = 90`. In `scheduler.py`:

```python
from datetime import timedelta


async def purge_old_connection_logs() -> int:
    cutoff = now() - timedelta(days=settings.CONNECTION_LOG_RETENTION_DAYS)
    return await ConnectionLog.filter(created_at__lt=cutoff).delete()
```

In `start_scheduler()` add: `scheduler.add_job(purge_old_connection_logs, IntervalTrigger(hours=24))`.

- [ ] **Step 4: Run → PASS. Commit** — `feat(logs): purge connection logs older than retention window`

### Task 7: Rotate exposed credentials (manual, no commit)

- [ ] Rotate the OpenRouter key (openrouter.ai dashboard), the OpenAI `sk-proj-…` key, and the Dify `app-…` key found in `spec/agent-onechat.md` / `spec/agent-promes.md`. Update GitHub secret `OPENROUTER_API_KEY` and the server `.env`.
- [ ] Edit both local files replacing every key with `<REDACTED>` (files are gitignored — local edit only).
- [ ] Finish Phase 1: full suite green, push branch, open PR titled `Phase 1: security hardening + CI test gate`.

---

## Phase 2 — Usage tracking, rate limits, quotas

Branch: `feat/phase2-usage-limits`

### Task 8: LlmUsage model

**Files:**
- Create: `backend/app/models/llm_usage.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_llm_usage_model.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_llm_usage_model.py
from app.models import LlmUsage


async def test_create_usage_row(db):
    row = await LlmUsage.create(
        model="google/gemini-2.5-flash-lite", purpose="classification",
        prompt_tokens=120, completion_tokens=8, cost_usd=0.000034,
    )
    assert row.total_tokens == 128
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement**

```python
# backend/app/models/llm_usage.py
"""Per-call LLM token/cost accounting."""
from tortoise import fields
from tortoise.models import Model

from app.utils import generate_uuid


class LlmUsage(Model):
    id = fields.UUIDField(primary_key=True, default=generate_uuid)
    model = fields.CharField(max_length=100)
    purpose = fields.CharField(max_length=30)  # router | synthesis | classification | embedding | brief | judge
    prompt_tokens = fields.IntField(default=0)
    completion_tokens = fields.IntField(default=0)
    cost_usd = fields.FloatField(null=True)
    user_id = fields.UUIDField(null=True)
    agency_id = fields.UUIDField(null=True)
    conversation_id = fields.UUIDField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "llm_usage"
        ordering = ["-created_at"]

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens
```

Export from `models/__init__.py` (match the existing import style there).

- [ ] **Step 4: Migration** `uv run aerich migrate --name llm_usage && uv run aerich upgrade`. Test → PASS. **Commit** — `feat(usage): add LlmUsage accounting model`

### Task 9: Usage-recording OpenRouter client, used everywhere

**Files:**
- Create: `backend/app/services/llm_client.py`
- Modify: every direct `settings.OPENROUTER_API_URL` post — find them: `rtk grep -rn "OPENROUTER_API_URL" backend/app` (known: `app/services/chat/llm.py:classify_message_category`; expect more in `app/services/chat/graph.py`, `app/services/analytics.py`)
- Test: `backend/tests/test_llm_client.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_llm_client.py
import httpx

from app.models import LlmUsage
from app.services import llm_client


class _FakeResponse:
    status_code = 200

    def json(self):
        return {
            "choices": [{"message": {"content": "ok"}}],
            "model": "google/gemini-2.5-flash-lite",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.00002},
        }


async def test_openrouter_chat_records_usage(db, monkeypatch):
    async def fake_post(self, url, **kwargs):
        return _FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    resp = await llm_client.openrouter_chat(
        {"model": "google/gemini-2.5-flash-lite", "messages": []}, purpose="classification",
    )
    assert resp.status_code == 200
    row = await LlmUsage.first()
    assert row.prompt_tokens == 10 and row.completion_tokens == 5
    assert row.cost_usd == 0.00002 and row.purpose == "classification"
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement**

```python
# backend/app/services/llm_client.py
"""Single entry point for OpenRouter chat calls — records LlmUsage for every call."""
import logging

import httpx

from app.config import settings
from app.models import LlmUsage

logger = logging.getLogger(__name__)


async def openrouter_chat(
    payload: dict,
    *,
    purpose: str,
    user_id=None,
    agency_id=None,
    conversation_id=None,
    timeout: float | None = None,
) -> httpx.Response:
    payload = {**payload, "usage": {"include": True}}  # OpenRouter returns cost when asked
    async with httpx.AsyncClient(timeout=timeout or settings.LLM_CALL_TIMEOUT) as client:
        resp = await client.post(
            settings.OPENROUTER_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            },
            json=payload,
        )
    await _record_usage(resp, payload, purpose, user_id, agency_id, conversation_id)
    return resp


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
            user_id=user_id, agency_id=agency_id, conversation_id=conversation_id,
        )
    except Exception:  # accounting must never break the chat path
        logger.exception("failed to record llm usage")
```

- [ ] **Step 4: Refactor call sites.** Example — `classify_message_category` in `app/services/chat/llm.py` becomes:

```python
    payload = {
        "model": settings.CLASSIFICATION_MODEL,
        "messages": [{"role": "user", "content": content}],
    }
    resp = await openrouter_chat(payload, purpose="classification", conversation_id=None)
```

Apply the same substitution to every grep hit from Step 1 file list, choosing `purpose` per site (`router`, `synthesis`, `brief`). Pass `user_id`/`conversation_id` where the surrounding function already has them; otherwise omit. Run the full suite after each file.

- [ ] **Step 5: Full suite → PASS. Commit** — `feat(usage): record tokens and cost for every OpenRouter call`

### Task 10: Usage insight endpoint + dashboard card

**Files:**
- Modify: `backend/app/routers/insight.py`
- Test: `backend/tests/test_usage_endpoint.py`
- Frontend: `frontend/src/features/dashboard/DashboardPage.tsx` (+ its api client module)

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_usage_endpoint.py
from app.models import LlmUsage
from app.routers.insight import usage_summary


async def test_usage_groups_by_purpose(db):
    await LlmUsage.create(model="m", purpose="router", prompt_tokens=10, completion_tokens=2, cost_usd=0.01)
    await LlmUsage.create(model="m", purpose="router", prompt_tokens=5, completion_tokens=1, cost_usd=0.02)
    await LlmUsage.create(model="m", purpose="synthesis", prompt_tokens=7, completion_tokens=3, cost_usd=0.005)

    rows = await usage_summary(group_by="purpose")

    by_key = {r["key"]: r for r in rows}
    assert by_key["router"]["prompt_tokens"] == 15
    assert by_key["router"]["cost_usd"] == 0.03
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement in `insight.py`** (match the router's existing auth pattern — admin-guarded like its siblings):

```python
from tortoise.functions import Sum

_GROUP_FIELDS = {"purpose": "purpose", "model": "model", "user": "user_id"}


async def usage_summary(group_by: str = "purpose") -> list[dict]:
    field = _GROUP_FIELDS.get(group_by, "purpose")
    rows = (
        await LlmUsage.all()
        .annotate(prompt=Sum("prompt_tokens"), completion=Sum("completion_tokens"), cost=Sum("cost_usd"))
        .group_by(field)
        .values(field, "prompt", "completion", "cost")
    )
    return [
        {
            "key": str(r[field]),
            "prompt_tokens": r["prompt"] or 0,
            "completion_tokens": r["completion"] or 0,
            "cost_usd": round(r["cost"] or 0.0, 6),
        }
        for r in rows
    ]


@router.get("/insight/usage", summary="LLM token/cost usage grouped")
async def get_usage(group_by: str = "purpose", _admin: User = Depends(require_admin)):
    return await usage_summary(group_by=group_by)
```

(Adjust imports/decorator prefix to match the file's existing style — read it first.)

- [ ] **Step 4: Run → PASS. Commit** — `feat(insight): usage summary endpoint grouped by purpose/model/user`
- [ ] **Step 5: Frontend card** — add a "LLM cost (30d)" stat card to `DashboardPage.tsx` fetching `/api/v1/insight/usage?group_by=model`, rendering total `cost_usd` and a small per-model table. Follow the page's existing card/fetch pattern. `pnpm exec tsc --noEmit` → clean. **Commit** — `feat(dashboard): show LLM cost card`

### Task 11: Sliding-window rate limiter + per-agency enforcement

**Files:**
- Create: `backend/app/services/rate_limit.py`
- Modify: `backend/app/services/chat/graph.py` (route building — include `rate_limit_rpm` and `agency_id` in each route dict; find it: `rtk grep -n "sub_question\|routes" backend/app/services/chat/graph.py`), `backend/app/services/chat/dispatch.py`
- Test: `backend/tests/test_rate_limit.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_rate_limit.py
from app.services.rate_limit import SlidingWindowLimiter


def test_allows_up_to_limit_then_blocks():
    t = [0.0]
    lim = SlidingWindowLimiter(now_fn=lambda: t[0])
    assert all(lim.allow("a", limit=3) for _ in range(3))
    assert lim.allow("a", limit=3) is False


def test_window_expiry_frees_slots():
    t = [0.0]
    lim = SlidingWindowLimiter(now_fn=lambda: t[0])
    for _ in range(3):
        lim.allow("a", limit=3)
    t[0] = 61.0
    assert lim.allow("a", limit=3) is True


def test_keys_are_independent():
    t = [0.0]
    lim = SlidingWindowLimiter(now_fn=lambda: t[0])
    for _ in range(3):
        lim.allow("a", limit=3)
    assert lim.allow("b", limit=3) is True
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement**

```python
# backend/app/services/rate_limit.py
"""In-process sliding-window rate limiter (single-worker deployment)."""
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, now_fn=time.monotonic):
        self._now = now_fn
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, *, limit: int, window_s: float = 60.0) -> bool:
        if limit <= 0:
            return True  # 0/None-configured = unlimited
        now = self._now()
        q = self._events[key]
        while q and q[0] <= now - window_s:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True

    def retry_after(self, key: str, *, window_s: float = 60.0) -> int:
        q = self._events.get(key)
        if not q:
            return 0
        return max(0, int(q[0] + window_s - self._now()) + 1)


agency_limiter = SlidingWindowLimiter()
user_limiter = SlidingWindowLimiter()
```

- [ ] **Step 4: Enforce per-agency in `dispatch.py`** — at the top of `dispatch_one`:

```python
from app.services.rate_limit import agency_limiter

    rpm = route.get("rate_limit_rpm") or 0
    if rpm and not agency_limiter.allow(f"agency:{route.get('agency_id')}", limit=rpm):
        return {"agency": name, "response": "rate limit exceeded", "status": "rate_limited"}
```

In `graph.py`, where route dicts are built from `Agency` rows (same place `dispatch_timeout_s`/`router_hint` are read), add `"rate_limit_rpm": ag.rate_limit_rpm` and ensure `"agency_id"` is present. Add a dispatch test in the existing dispatch test file (`rtk grep -l dispatch backend/tests`) asserting `dispatch_one` returns `status == "rate_limited"` when a 1-rpm route is called twice.

- [ ] **Step 5: Full suite → PASS. Commit** — `feat(rate-limit): enforce per-agency rate_limit_rpm in dispatch`

### Task 12: Per-user rate limit on chat endpoints

**Files:**
- Modify: `backend/app/config.py`, `backend/app/routers/chat.py`
- Test: `backend/tests/test_user_rate_limit.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_user_rate_limit.py
import pytest
from fastapi import HTTPException

from app.routers.chat import enforce_user_rate_limit
from app.services.rate_limit import SlidingWindowLimiter


def test_blocks_after_limit(monkeypatch):
    import app.routers.chat as chat_mod
    t = [0.0]
    monkeypatch.setattr(chat_mod, "user_limiter", SlidingWindowLimiter(now_fn=lambda: t[0]))
    monkeypatch.setattr(chat_mod.settings, "USER_RATE_LIMIT_RPM", 2)

    class U: id = "u1"

    enforce_user_rate_limit(U())
    enforce_user_rate_limit(U())
    with pytest.raises(HTTPException) as e:
        enforce_user_rate_limit(U())
    assert e.value.status_code == 429
    assert "Retry-After" in e.value.headers
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement.** `Settings`: `USER_RATE_LIMIT_RPM: int = 30` (group "Chat"). In `routers/chat.py`:

```python
from app.services.rate_limit import user_limiter


def enforce_user_rate_limit(user) -> None:
    key = f"user:{user.id}"
    if not user_limiter.allow(key, limit=settings.USER_RATE_LIMIT_RPM):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(user_limiter.retry_after(key))},
        )
```

Call it first in each chat POST handler that resolves a user (`/chat`, `/chat/stream` — check how they obtain the user: `rtk grep -n "get_current_user" backend/app/routers/chat.py`; for optional-auth handlers, skip when user is None).

- [ ] **Step 4: Full suite → PASS. Commit** — `feat(rate-limit): per-user RPM limit on chat endpoints`

### Task 13: Quotas — monthly user budget + global daily kill-switch

**Files:**
- Create: `backend/app/services/quota.py`
- Modify: `backend/app/config.py`, `backend/app/routers/chat.py`
- Test: `backend/tests/test_quota.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_quota.py
import pytest

from app.config import settings
from app.models import LlmUsage
from app.services.quota import QuotaExceeded, check_global_budget, check_user_quota


async def test_user_over_monthly_quota_raises(db, monkeypatch):
    monkeypatch.setattr(settings, "USER_MONTHLY_TOKEN_QUOTA", 100)
    await LlmUsage.create(model="m", purpose="synthesis", prompt_tokens=90, completion_tokens=20, user_id="0" * 32)
    with pytest.raises(QuotaExceeded):
        await check_user_quota("0" * 32)


async def test_zero_quota_means_unlimited(db, monkeypatch):
    monkeypatch.setattr(settings, "USER_MONTHLY_TOKEN_QUOTA", 0)
    await check_user_quota("0" * 32)  # no raise


async def test_global_daily_cost_kill_switch(db, monkeypatch):
    monkeypatch.setattr(settings, "GLOBAL_DAILY_COST_LIMIT_USD", 0.01)
    await LlmUsage.create(model="m", purpose="synthesis", cost_usd=0.02)
    with pytest.raises(QuotaExceeded):
        await check_global_budget()
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement.** `Settings` (new group `"Quota"` in `SETTINGS_GROUPS`): `USER_MONTHLY_TOKEN_QUOTA: int = 0`, `GLOBAL_DAILY_COST_LIMIT_USD: float = 0.0` (0 = unlimited).

```python
# backend/app/services/quota.py
"""Token/cost quota checks — raise QuotaExceeded before dispatching new LLM work."""
from tortoise.functions import Sum

from app.config import settings
from app.models import LlmUsage
from app.utils import now


class QuotaExceeded(Exception):
    pass


async def check_user_quota(user_id) -> None:
    limit = settings.USER_MONTHLY_TOKEN_QUOTA
    if not limit:
        return
    start = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    row = (
        await LlmUsage.filter(user_id=user_id, created_at__gte=start)
        .annotate(p=Sum("prompt_tokens"), c=Sum("completion_tokens"))
        .values("p", "c")
    )
    used = (row[0]["p"] or 0) + (row[0]["c"] or 0) if row else 0
    if used >= limit:
        raise QuotaExceeded(f"monthly token quota exceeded ({used}/{limit})")


async def check_global_budget() -> None:
    limit = settings.GLOBAL_DAILY_COST_LIMIT_USD
    if not limit:
        return
    start = now().replace(hour=0, minute=0, second=0, microsecond=0)
    row = await LlmUsage.filter(created_at__gte=start).annotate(s=Sum("cost_usd")).values("s")
    spent = (row[0]["s"] or 0.0) if row else 0.0
    if spent >= limit:
        raise QuotaExceeded(f"global daily budget exceeded (${spent:.4f}/${limit})")
```

In `routers/chat.py`, after `enforce_user_rate_limit` in each handler:

```python
    try:
        await check_global_budget()
        if user is not None:
            await check_user_quota(user.id)
    except QuotaExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))
```

- [ ] **Step 4: Full suite → PASS. Commit** — `feat(quota): monthly user token quota and global daily cost kill-switch`
- [ ] Finish Phase 2: PR `Phase 2: usage tracking, rate limits, quotas`.

---

## Phase 3 — Reliability: retry, breaker, error envelope, cache flush

Branch: `feat/phase3-reliability`

### Task 14: Retry helper with exponential backoff

**Files:**
- Create: `backend/app/utils/retry.py`
- Modify: `backend/app/services/chat/dispatch.py`
- Test: `backend/tests/test_retry.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_retry.py
import httpx
import pytest

from app.utils.retry import retry_async


async def test_retries_transient_then_succeeds():
    calls = {"n": 0}
    sleeps: list[float] = []

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("boom")
        return "ok"

    async def fake_sleep(s):
        sleeps.append(s)

    assert await retry_async(flaky, attempts=3, base_delay=0.5, sleep=fake_sleep) == "ok"
    assert calls["n"] == 3 and sleeps == [0.5, 1.0]  # exponential


async def test_gives_up_after_attempts():
    async def always_fails():
        raise httpx.ConnectError("boom")

    async def fake_sleep(s):
        pass

    with pytest.raises(httpx.ConnectError):
        await retry_async(always_fails, attempts=2, sleep=fake_sleep)


async def test_non_retryable_raises_immediately():
    calls = {"n": 0}

    async def bad():
        calls["n"] += 1
        raise ValueError("not transient")

    with pytest.raises(ValueError):
        await retry_async(bad, attempts=3)
    assert calls["n"] == 1
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement**

```python
# backend/app/utils/retry.py
"""Retry an async callable on transient network errors with exponential backoff."""
import asyncio

import httpx

TRANSIENT = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.RemoteProtocolError)


async def retry_async(fn, *, attempts: int = 3, base_delay: float = 0.5, retry_on=TRANSIENT, sleep=asyncio.sleep):
    last: Exception | None = None
    for i in range(attempts):
        try:
            return await fn()
        except retry_on as e:
            last = e
            if i < attempts - 1:
                await sleep(base_delay * (2 ** i))
    raise last
```

- [ ] **Step 4: Use it in `dispatch.py`** — wrap the HTTP bodies of `dispatch_api` and `dispatch_a2a`:

```python
from app.utils.retry import retry_async

# dispatch_api: extract the existing client.post block into a closure and call
    async def _call():
        async with httpx.AsyncClient(timeout=_dispatch_timeout(route)) as client:
            return await client.post(route["endpoint_url"], headers=headers, json=payload)

    resp = await retry_async(_call)
```

(Same shape for `dispatch_a2a`. `dispatch_one`'s existing `except Exception` keeps final failures as `status: "error"`.)

- [ ] **Step 5: Full suite → PASS. Commit** — `feat(dispatch): retry transient agency failures with backoff`

### Task 15: Circuit breaker — live failures trip auto_maintenance

**Files:**
- Create: `backend/app/services/circuit_breaker.py`
- Modify: `backend/app/config.py`; the dispatch result handling in `backend/app/services/chat/graph.py` (where `dispatch_one` results are consumed)
- Test: `backend/tests/test_circuit_breaker.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_circuit_breaker.py
from app.config import settings
from app.models import Agency
from app.services.circuit_breaker import record_dispatch_result


async def test_consecutive_failures_trip_maintenance(db, monkeypatch):
    monkeypatch.setattr(settings, "BREAKER_FAILURE_THRESHOLD", 3)
    ag = await Agency.create(name="A", status="active")

    for _ in range(3):
        await record_dispatch_result(str(ag.id), success=False)

    await ag.refresh_from_db()
    assert ag.status == "maintenance" and ag.auto_maintenance is True


async def test_success_resets_counter(db, monkeypatch):
    monkeypatch.setattr(settings, "BREAKER_FAILURE_THRESHOLD", 3)
    ag = await Agency.create(name="B", status="active")

    await record_dispatch_result(str(ag.id), success=False)
    await record_dispatch_result(str(ag.id), success=True)
    await record_dispatch_result(str(ag.id), success=False)
    await record_dispatch_result(str(ag.id), success=False)

    await ag.refresh_from_db()
    assert ag.status == "active"
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement.** `Settings`: `BREAKER_FAILURE_THRESHOLD: int = 5` (group "Agency health").

```python
# backend/app/services/circuit_breaker.py
"""Trip agencies into auto-maintenance after N consecutive live-dispatch failures.

Recovery reuses the existing health-probe reconcile loop (app/services/agency_reconcile.py),
which re-activates agencies whose auto_maintenance flag is set once probes pass again.
"""
import logging
from collections import defaultdict

from app.config import settings
from app.models import Agency

logger = logging.getLogger(__name__)
_consecutive_failures: dict[str, int] = defaultdict(int)


async def record_dispatch_result(agency_id: str, *, success: bool) -> None:
    if success:
        _consecutive_failures.pop(agency_id, None)
        return
    _consecutive_failures[agency_id] += 1
    if _consecutive_failures[agency_id] < settings.BREAKER_FAILURE_THRESHOLD:
        return
    updated = await Agency.filter(id=agency_id, status="active").update(
        status="maintenance", auto_maintenance=True
    )
    if updated:
        logger.warning("circuit breaker tripped agency %s into maintenance", agency_id)
    _consecutive_failures.pop(agency_id, None)
```

- [ ] **Step 4: Wire into the chat pipeline** — in `graph.py`, where each `dispatch_one` result is handled, add `await record_dispatch_result(route["agency_id"], success=(result["status"] == "ok"))` (skip `rate_limited`). Confirm with `rtk grep -n "dispatch_one" backend/app/services/chat/graph.py` and the existing dispatch tests still pass.
- [ ] **Step 5: Full suite → PASS. Commit** — `feat(breaker): trip auto_maintenance after consecutive live failures`

### Task 16: Standard error envelope for /api/v1

**Files:**
- Create: `backend/app/errors.py`
- Modify: `backend/app/main.py` (register handlers)
- Test: `backend/tests/test_error_envelope.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_error_envelope.py
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.errors import ApiError, register_error_handlers


def _app():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/api/v1/boom")
    async def boom():
        raise ApiError("agency_timeout", "Agency X timed out", status=504, retryable=True)

    @app.get("/api/v1/http")
    async def http():
        raise HTTPException(status_code=404, detail="Not found")

    return app


def test_api_error_envelope():
    r = TestClient(_app()).get("/api/v1/boom")
    assert r.status_code == 504
    assert r.json() == {
        "error": {"code": "agency_timeout", "message": "Agency X timed out", "retryable": True}
    }


def test_http_exception_mapped_to_envelope():
    r = TestClient(_app()).get("/api/v1/http")
    assert r.status_code == 404
    body = r.json()["error"]
    assert body["code"] == "not_found" and body["message"] == "Not found"
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement**

```python
# backend/app/errors.py
"""Standard error envelope: {"error": {"code", "message", "retryable", ...}}.

Stable codes: invalid_request, unauthorized, forbidden, not_found, quota_exceeded,
rate_limited, agency_unavailable, agency_timeout, llm_error, internal.
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

_STATUS_CODES = {
    400: "invalid_request", 401: "unauthorized", 403: "forbidden",
    404: "not_found", 429: "rate_limited", 500: "internal",
    502: "agency_unavailable", 504: "agency_timeout",
}


class ApiError(Exception):
    def __init__(self, code: str, message: str, *, status: int = 400,
                 retryable: bool = False, upstream_status: int | None = None):
        self.code, self.message = code, message
        self.status, self.retryable, self.upstream_status = status, retryable, upstream_status


def _envelope(code: str, message: str, retryable: bool = False, upstream_status: int | None = None) -> dict:
    err: dict = {"code": code, "message": message, "retryable": retryable}
    if upstream_status is not None:
        err["upstream_status"] = upstream_status
    return {"error": err}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_req: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status,
            content=_envelope(exc.code, exc.message, exc.retryable, exc.upstream_status),
        )

    @app.exception_handler(HTTPException)
    async def _http_error(_req: Request, exc: HTTPException):
        code = _STATUS_CODES.get(exc.status_code, "internal")
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, str(exc.detail), retryable=exc.status_code == 429),
            headers=getattr(exc, "headers", None),
        )
```

Call `register_error_handlers(app)` in `main.py` next to where the app is constructed.

- [ ] **Step 4: Fix frontend error reads** — `rtk grep -rn "\.detail" frontend/src --include=*.ts --include=*.tsx` and update the shared API client error handling to read `body.error.message` (fall back to `body.detail` for safety). Run `pnpm exec tsc --noEmit`.
- [ ] **Step 5: Full suite → PASS (existing tests asserting `{"detail": ...}` shapes will need updating — change assertions, not behavior intent). Commit** — `feat(errors): standard error envelope on /api/v1`

### Task 17: Similarity-cache flush (admin) + flush on agency change

**Files:**
- Create: `backend/app/services/cache_flush.py`
- Modify: `backend/app/services/similarity.py`, `backend/app/routers/settings.py`, agency update handlers in `backend/app/routers/agencies.py`
- Test: `backend/tests/test_cache_flush.py`

Note: cache age is already bounded by `SIMILARITY_WINDOW_SECONDS` (3 days) — this task adds *manual/automatic invalidation*, the missing half of roadmap 1.6.

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_cache_flush.py
from datetime import timedelta

from app.services.cache_flush import effective_cutoff, flush_similarity_cache
from app.utils import now


async def test_flush_moves_cutoff_forward(db):
    window_cutoff = now() - timedelta(days=3)
    assert await effective_cutoff(window_cutoff) == window_cutoff  # no flush yet

    await flush_similarity_cache()

    cutoff = await effective_cutoff(window_cutoff)
    assert cutoff > window_cutoff  # flush timestamp wins
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement**

```python
# backend/app/services/cache_flush.py
"""Similarity-cache invalidation via a stored flush timestamp.

find_similar_question ignores any cached Q/A created before the last flush.
"""
from datetime import datetime

from app.models.setting import Setting
from app.utils import now

_KEY = "SIMILARITY_CACHE_FLUSHED_AT"


async def flush_similarity_cache() -> None:
    await Setting.update_or_create(defaults={"value": now().isoformat()}, key=_KEY)


async def effective_cutoff(window_cutoff: datetime) -> datetime:
    row = await Setting.filter(key=_KEY).first()
    if row is None:
        return window_cutoff
    flushed_at = datetime.fromisoformat(row.value)
    return max(window_cutoff, flushed_at)
```

In `similarity.py:find_similar_question`, replace the cutoff line:

```python
    cutoff = await effective_cutoff(now() - timedelta(seconds=settings.SIMILARITY_WINDOW_SECONDS))
```

In `routers/settings.py` add (admin-guarded like its siblings): `POST /settings/cache/flush` → `await flush_similarity_cache(); return {"detail": "cache flushed"}`. In `routers/agencies.py`, call `await flush_similarity_cache()` at the end of the PUT and PATCH update handlers (config changed → stale answers must not be served).

- [ ] **Step 4: Frontend** — add a "Flush answer cache" button to `SettingsPage.tsx` calling the new endpoint with a confirm dialog. **Step 5: Full suite + tsc → PASS. Commit** — `feat(cache): similarity cache flush endpoint and auto-flush on agency change`
- [ ] Finish Phase 3: PR `Phase 3: reliability — retry, breaker, error envelope, cache flush`.

---

## Phase 4 — Consolidation & cleanup

Branch: `chore/phase4-consolidation`

### Task 18: Spec file consolidation

**Files:** delete `spec/hello.md`, `spec/readme 2.md`; create `spec/archive/`; rename `spec/readme.md` → `spec/mcp-server.md`; modify `spec/.gitignore`.

- [ ] **Step 1:** `rtk git rm spec/hello.md "spec/readme 2.md"` (hello.md duplicates agent-onechat.md content; "readme 2.md" is an older readme.md).
- [ ] **Step 2:** `mkdir -p spec/archive && rtk git mv spec/ai-chat-api-spec.yaml spec/archive/` — add a one-line note at the top of the moved file: `# ARCHIVED: describes the pre-FastAPI Supabase Edge Functions architecture.`
- [ ] **Step 3:** `rtk git mv spec/readme.md spec/mcp-server.md` (it is the MCP server requirements doc). Fix any references: `rtk grep -rn "spec/readme" . --include=*.md`.
- [ ] **Step 4:** Append to `spec/.gitignore`: `*.pdf` and `*.html`, then `rtk git rm --cached spec/InceptionReport_Revised1_Submit1_16032026.pdf spec/v4-streaming.html` (files stay on disk).
- [ ] **Step 5: Commit** — `chore(spec): consolidate duplicate specs, archive supabase-era spec, untrack binaries`

### Task 19: Chat endpoint consolidation

**Files:**
- Modify: `backend/app/routers/chat.py`, frontend chat API client (`rtk grep -rln "chat/external\|chat/internal" frontend/src backend/tests`)

- [ ] **Step 1:** Read `backend/app/routers/chat.py` fully. Inline the `/chat` → `/chat/external` delegation so `POST /chat` *is* the canonical sync handler (move the body, keep behavior identical).
- [ ] **Step 2:** Mark `/chat/external` as a deprecated alias of the same function and hide internals from the public schema:

```python
@router.post("/chat/external", include_in_schema=False, deprecated=True)  # alias of /chat
@router.post("/chat/internal", include_in_schema=False)  # internal LangGraph pipeline
```

- [ ] **Step 3:** Update every frontend call site to use `/chat` and `/chat/stream` only. Update backend tests referencing the old paths (alias keeps them passing — switch them to `/chat` anyway).
- [ ] **Step 4: Full suite + tsc → PASS. Commit** — `refactor(chat): make /chat canonical, hide internal/external variants from schema`

### Task 20: pgvector expression index for similarity search

**Files:**
- Create migration (hand-written, aerich-style) under `backend/migrations/models/`
- Modify: `backend/app/models/conversation.py` (comment only)

Rationale: queries already cast `embedding::vector` in SQL (`similarity.py`); the missing piece is an index. A native `VectorField` would break the SQLite test fixture, so keep the TEXT column and index the cast expression.

- [ ] **Step 1:** `uv run aerich migrate --name embedding_vector_index` then edit the generated file so `upgrade` returns:

```sql
        CREATE INDEX IF NOT EXISTS idx_messages_embedding_cosine
        ON messages USING hnsw (((embedding)::vector(384)) vector_cosine_ops)
        WHERE role = 'user' AND embedding IS NOT NULL;
```

and `downgrade` returns `DROP INDEX IF EXISTS idx_messages_embedding_cosine;`. (Follow the structure of migration `5_20260612143252_Agency add auto_maintenance.py`.)

- [ ] **Step 2:** `uv run aerich upgrade` against dev Postgres → succeeds. Verify: `\d messages` shows the index (or `SELECT indexname FROM pg_indexes WHERE tablename='messages';` via the app's DB).
- [ ] **Step 3:** Update the `embedding` field comment in `models/conversation.py` to note the expression index and that dimensions are fixed by `EMBEDDING_DIMENSIONS=384`.
- [ ] **Step 4: Commit** — `perf(similarity): hnsw expression index on messages.embedding`

### Task 21: Collapse legacy `inactive` status into `disabled`

**Files:**
- Modify: `backend/app/models/agency.py`; data migration; `rtk grep -rn "inactive" backend/app backend/tests frontend/src` for stragglers.

- [ ] **Step 1:** Migration (aerich, hand-edit): `UPDATE agencies SET status='disabled' WHERE status='inactive';`
- [ ] **Step 2:** Remove `inactive = "inactive"` from `AgencyStatus`. Fix every grep hit (frontend status type unions, badge colors, filters; backend lifecycle/reconcile references if any).
- [ ] **Step 3: Full suite + tsc → PASS. Commit** — `chore(agency): collapse legacy inactive status into disabled`

### Task 22: Repo clutter

- [ ] **Step 1:** Create `lab/README.md`: `# Lab — experimental scripts. Not part of the product; not maintained; not imported by backend/frontend.`
- [ ] **Step 2: Commit** — `docs(lab): mark lab/ as experimental`. Finish Phase 4: PR `Phase 4: consolidation and cleanup`.

---

## Phase 5 — Authorization (ReBAC+ABAC over RBAC) + agency self-service

Branch: `feat/phase5-authz-onboarding`

### Task 23: Relationship model

**Files:**
- Create: `backend/app/models/relationship.py`; modify `backend/app/models/__init__.py`
- Test: `backend/tests/test_relationship_model.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_relationship_model.py
import pytest
from tortoise.exceptions import IntegrityError

from app.models import Relationship


async def test_create_and_unique(db):
    args = dict(subject_type="user", subject_id="0" * 32, relation="owner",
                object_type="agency", object_id="1" * 32)
    await Relationship.create(**args)
    with pytest.raises(IntegrityError):
        await Relationship.create(**args)
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement**

```python
# backend/app/models/relationship.py
"""ReBAC tuples: (subject, relation, object) — minimal Zanzibar-style storage."""
from tortoise import fields
from tortoise.models import Model

from app.utils import generate_uuid


class Relationship(Model):
    id = fields.UUIDField(primary_key=True, default=generate_uuid)
    subject_type = fields.CharField(max_length=20)   # user
    subject_id = fields.UUIDField()
    relation = fields.CharField(max_length=30)       # owner | viewer
    object_type = fields.CharField(max_length=30)    # agency | conversation
    object_id = fields.UUIDField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "relationships"
        unique_together = (("subject_type", "subject_id", "relation", "object_type", "object_id"),)
```

Export in `models/__init__.py`; `uv run aerich migrate --name relationships && uv run aerich upgrade`.

- [ ] **Step 4: Run → PASS. Commit** — `feat(authz): relationship model for ReBAC tuples`

### Task 24: authorize() decision point (TDD the matrix)

**Files:**
- Create: `backend/app/auth/authz.py`
- Test: `backend/tests/test_authz.py`

- [ ] **Step 1: Failing tests — one per matrix cell of roadmap §2.6**

```python
# backend/tests/test_authz.py
from app.auth.authz import authorize, grant
from app.models import Agency, User
from app.models.conversation import Conversation


async def _user(role="user", email="u@x.com"):
    return await User.create(email=email, hashed_password="h", role=role)


async def test_admin_allows_everything(db):
    admin = await _user("admin", "a@x.com")
    ag = await Agency.create(name="A", status="active")
    for action in ("agency:edit", "agency:change_status", "settings:edit", "user:manage"):
        assert (await authorize(admin, action, ag)).allowed


async def test_plain_user_cannot_edit_agency(db):
    u = await _user()
    ag = await Agency.create(name="A", status="draft")
    d = await authorize(u, "agency:edit", ag)
    assert not d.allowed and d.layer == "rebac"


async def test_owner_edits_draft_agency(db):
    u = await _user("agency_owner", "o@x.com")
    ag = await Agency.create(name="A", status="draft")
    await grant(u.id, "owner", "agency", ag.id)
    assert (await authorize(u, "agency:edit", ag)).allowed


async def test_abac_blocks_owner_editing_active_agency(db):
    u = await _user("agency_owner", "o2@x.com")
    ag = await Agency.create(name="A", status="active")
    await grant(u.id, "owner", "agency", ag.id)
    d = await authorize(u, "agency:edit", ag)
    assert not d.allowed and d.layer == "abac"


async def test_owner_cannot_change_status(db):
    u = await _user("agency_owner", "o3@x.com")
    ag = await Agency.create(name="A", status="draft")
    await grant(u.id, "owner", "agency", ag.id)
    assert not (await authorize(u, "agency:change_status", ag)).allowed


async def test_conversation_owner_reads_own_only(db):
    u1, u2 = await _user(email="c1@x.com"), await _user(email="c2@x.com")
    conv = await Conversation.create(title="t", user_id=u1.id)
    assert (await authorize(u1, "conversation:read", conv)).allowed
    assert not (await authorize(u2, "conversation:read", conv)).allowed


async def test_inactive_user_denied_everywhere(db):
    u = await _user(email="i@x.com")
    u.is_active = False
    conv = await Conversation.create(title="t", user_id=u.id)
    d = await authorize(u, "conversation:read", conv)
    assert not d.allowed and d.layer == "abac"
```

(If `Conversation`'s FK field name differs, check `backend/app/models/conversation.py` and adjust `user_id` kwarg.)

- [ ] **Step 2: Run → FAIL. Step 3: Implement**

```python
# backend/app/auth/authz.py
"""Layered authorization: RBAC (role) -> ReBAC (relationship) -> ABAC (attributes).

authorize() is the single decision point; routers depend on it instead of
require_admin + inline user_id filters. Deny overrides allow at the ABAC layer.
"""
import logging
from dataclasses import dataclass
from typing import Any

from app.models import Relationship
from app.models.user import User

logger = logging.getLogger(__name__)


@dataclass
class Decision:
    allowed: bool
    layer: str    # rbac | rebac | abac
    reason: str = ""


# Actions admins get implicitly; non-admins proceed to ReBAC unless listed here.
_ADMIN_ONLY = {"agency:change_status", "settings:edit", "user:manage", "agency:delete"}

# action -> (relation required, object_type)
_RELATION_FOR = {
    "agency:edit": ("owner", "agency"),
    "agency:read_logs": ("owner", "agency"),
    "conversation:read": ("owner", "conversation"),
    "conversation:delete": ("owner", "conversation"),
}


async def grant(subject_id, relation: str, object_type: str, object_id) -> None:
    await Relationship.get_or_create(
        subject_type="user", subject_id=subject_id, relation=relation,
        object_type=object_type, object_id=object_id,
    )


async def has_relation(subject_id, relation: str, object_type: str, object_id) -> bool:
    return await Relationship.filter(
        subject_type="user", subject_id=subject_id, relation=relation,
        object_type=object_type, object_id=object_id,
    ).exists()


def _abac(user: User, action: str, resource: Any) -> Decision | None:
    """Attribute conditions. Return a deny Decision, or None to pass."""
    if not user.is_active:
        return Decision(False, "abac", "user inactive")
    if action == "agency:edit" and getattr(resource, "status", None) == "active":
        return Decision(False, "abac", "active agencies are edited via admin approval")
    return None


async def authorize(user: User, action: str, resource: Any) -> Decision:
    # ABAC denials apply to everyone, admin included, except user-inactive for admin ops? No:
    # inactive users are denied first, full stop.
    if not user.is_active:
        return _log(user, action, Decision(False, "abac", "user inactive"))

    # RBAC
    if user.role == "admin":
        return _log(user, action, Decision(True, "rbac", "admin"))
    if action in _ADMIN_ONLY:
        return _log(user, action, Decision(False, "rbac", "admin required"))

    # Built-in ownership for conversations (FK), tuple lookup otherwise
    rel = _RELATION_FOR.get(action)
    if rel is None:
        return _log(user, action, Decision(False, "rbac", f"unknown action {action}"))
    relation, object_type = rel
    if object_type == "conversation":
        owned = str(getattr(resource, "user_id", "")) == str(user.id)
    else:
        owned = await has_relation(user.id, relation, object_type, resource.id)
    if not owned:
        return _log(user, action, Decision(False, "rebac", f"missing {relation} on {object_type}"))

    # ABAC
    deny = _abac(user, action, resource)
    if deny:
        return _log(user, action, deny)
    return Decision(True, "rebac", "")


def _log(user: User, action: str, d: Decision) -> Decision:
    if not d.allowed or d.reason == "admin":
        logger.info("authz %s user=%s action=%s layer=%s reason=%s",
                    "ALLOW" if d.allowed else "DENY", user.id, action, d.layer, d.reason)
    return d
```

(Note the inactive-user check moved before RBAC so the test's expected `layer == "abac"` holds — keep it that way.)

- [ ] **Step 4: Run the matrix tests → all PASS. Full suite → PASS. Commit** — `feat(authz): layered authorize() with RBAC/ReBAC/ABAC decision table`

### Task 25: FastAPI dependency + wire into routers

**Files:**
- Modify: `backend/app/auth/authz.py` (add `require()` helper), `backend/app/routers/agencies.py`, `backend/app/routers/conversations.py`, `backend/app/routers/connection_logs.py`
- Test: extend `backend/tests/test_authz.py`

- [ ] **Step 1:** Add to `authz.py`:

```python
from fastapi import HTTPException


async def authorize_or_403(user: User, action: str, resource: Any) -> None:
    d = await authorize(user, action, resource)
    if not d.allowed:
        raise HTTPException(status_code=403, detail=d.reason or "Forbidden")
```

Test: a denied call raises HTTPException 403 (pytest.raises).

- [ ] **Step 2:** Rewire routers, one at a time, running the suite after each:
  - `agencies.py`: PUT/PATCH handlers — replace `require_admin` with `get_current_user` + `await authorize_or_403(user, "agency:edit", agency)`; DELETE and `/status` keep admin via `authorize_or_403(user, "agency:delete"| "agency:change_status", agency)`.
  - `conversations.py`: GET/DELETE by id — replace inline `user_id=user.id` filters with a fetch + `authorize_or_403(user, "conversation:read"|"conversation:delete", conv)` (keep list endpoints filtered by `user_id` in the query — that is the scope_query form).
  - `connection_logs.py`: list/detail stay admin for now; owner scoping arrives with Task 26.
- [ ] **Step 3: Full suite → PASS. Commit** — `refactor(authz): route handlers use authorize() instead of scattered checks`

### Task 26: agency_owner role + ownership endpoints

**Files:**
- Modify: `backend/app/routers/agencies.py`, `backend/app/routers/users.py` (role validation accepts `agency_owner` — check existing role validation: `rtk grep -n "role" backend/app/routers/users.py backend/app/services/user.py`)
- Test: `backend/tests/test_agency_owners.py`

- [ ] **Step 1: Failing tests** — admin can `POST /agencies/{id}/owners {user_id}` (creates `owner` tuple), `GET /agencies/mine` returns only owned agencies for an `agency_owner`, plain users get `[]`. Write them against the service functions (router-level if the file already has TestClient-style tests — mirror `tests/test_users_router.py` style).

```python
# backend/tests/test_agency_owners.py
from app.auth.authz import grant, has_relation
from app.models import Agency, User
from app.routers.agencies import add_agency_owner, list_my_agencies


async def test_add_owner_creates_tuple(db):
    admin = await User.create(email="a@x.com", hashed_password="h", role="admin")
    owner = await User.create(email="o@x.com", hashed_password="h", role="agency_owner")
    ag = await Agency.create(name="A", status="draft")

    await add_agency_owner(str(ag.id), body=type("B", (), {"user_id": str(owner.id)})(), user=admin)

    assert await has_relation(owner.id, "owner", "agency", ag.id)


async def test_list_my_agencies_scoped(db):
    owner = await User.create(email="o2@x.com", hashed_password="h", role="agency_owner")
    mine = await Agency.create(name="Mine", status="draft")
    await Agency.create(name="NotMine", status="draft")
    await grant(owner.id, "owner", "agency", mine.id)

    result = await list_my_agencies(user=owner)

    assert [a.name for a in result] == ["Mine"]
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement in `agencies.py`** (match the router's existing response-serialization style):

```python
class AddOwnerRequest(BaseModel):
    user_id: str


@router.post("/{agency_id}/owners", summary="Assign an owner to an agency (admin)")
async def add_agency_owner(agency_id: str, body: AddOwnerRequest, user: User = Depends(get_current_user)):
    agency = await Agency.get_or_none(id=agency_id)
    if agency is None:
        raise HTTPException(status_code=404, detail="Agency not found")
    await authorize_or_403(user, "user:manage", agency)
    await grant(body.user_id, "owner", "agency", agency.id)
    return {"detail": "owner added"}


@router.get("/mine", summary="Agencies owned by the current user")
async def list_my_agencies(user: User = Depends(get_current_user)) -> list:
    ids = await Relationship.filter(
        subject_type="user", subject_id=user.id, relation="owner", object_type="agency"
    ).values_list("object_id", flat=True)
    return await Agency.filter(id__in=list(ids))
```

(Route ordering: register `/mine` BEFORE `/{agency_id}` or FastAPI will shadow it.) Allow `agency_owner` wherever user roles are validated.

- [ ] **Step 4: Owner-scoped logs** — in `connection_logs.py` list endpoint, when `user.role == "agency_owner"`, filter `agency_id__in=<owned ids>` (same tuple query); admins keep full view.
- [ ] **Step 5: Full suite → PASS. Commit** — `feat(authz): agency_owner role, owner assignment, owner-scoped views`

### Task 27: Conformance test battery

**Files:**
- Create: `backend/app/services/conformance.py`
- Modify: `backend/app/models/agency.py` (+ migration), `backend/app/routers/agencies.py`, the lifecycle transition (`backend/app/services/agency_lifecycle.py`)
- Test: `backend/tests/test_conformance.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_conformance.py
from app.models import Agency
from app.services import conformance


async def test_report_aggregates_checks(db, monkeypatch):
    ag = await Agency.create(name="A", status="draft", connection_type="API",
                             endpoint_url="http://x", expected_payload={"query": "__query__"})

    async def fake_ask(agency, question):
        return {"ok": True, "latency_ms": 120, "answer": "คำตอบภาษาไทย"}

    monkeypatch.setattr(conformance, "_ask", fake_ask)
    report = await conformance.run_conformance(ag)

    assert report["passed"] is True
    assert {c["name"] for c in report["checks"]} == {
        "responds", "thai_text", "non_empty", "concurrency_3", "garbage_input",
    }


async def test_failing_check_fails_report(db, monkeypatch):
    ag = await Agency.create(name="B", status="draft", connection_type="API", endpoint_url="http://x")

    async def fake_ask(agency, question):
        return {"ok": False, "latency_ms": 0, "answer": "", "error": "ConnectError"}

    monkeypatch.setattr(conformance, "_ask", fake_ask)
    report = await conformance.run_conformance(ag)
    assert report["passed"] is False
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement**

```python
# backend/app/services/conformance.py
"""Agency conformance battery — required before draft -> active."""
import asyncio

from app.models import Agency
from app.services.chat.dispatch import dispatch_one
from app.utils import now

_THAI_PROBE = "ขอข้อมูลการติดต่อหน่วยงาน"


async def _ask(agency: Agency, question: str) -> dict:
    route = {
        "agency_id": str(agency.id), "agency_name": agency.name,
        "connection_type": agency.connection_type, "endpoint_url": agency.endpoint_url,
        "sub_question": question, "expected_payload": agency.expected_payload,
        "api_headers": agency.api_headers, "dispatch_timeout_s": agency.dispatch_timeout_s,
        "rate_limit_rpm": None,
    }
    start = now()
    result = await dispatch_one(route, conversation_id="")
    latency_ms = int((now() - start).total_seconds() * 1000)
    ok = result.get("status") == "ok"
    return {"ok": ok, "latency_ms": latency_ms,
            "answer": str(result.get("response", "")), "error": None if ok else result.get("response")}


def _has_thai(text: str) -> bool:
    return any("฀" <= ch <= "๿" for ch in text)


async def run_conformance(agency: Agency) -> dict:
    checks: list[dict] = []
    first = await _ask(agency, _THAI_PROBE)
    checks.append({"name": "responds", "passed": first["ok"], "detail": first.get("error") or f"{first['latency_ms']}ms"})
    checks.append({"name": "non_empty", "passed": bool(first["answer"].strip()), "detail": ""})
    checks.append({"name": "thai_text", "passed": _has_thai(first["answer"]), "detail": ""})

    concurrent = await asyncio.gather(*[_ask(agency, _THAI_PROBE) for _ in range(3)])
    checks.append({"name": "concurrency_3", "passed": all(r["ok"] for r in concurrent), "detail": ""})

    garbage = await _ask(agency, "\x00\x01 ###")
    checks.append({"name": "garbage_input", "passed": True, "detail": "did not crash" if garbage else ""})

    report = {"ran_at": now().isoformat(), "passed": all(c["passed"] for c in checks), "checks": checks}
    agency.conformance_report = report
    await agency.save(update_fields=["conformance_report"])
    return report
```

Model: add `conformance_report = fields.JSONField(null=True)` to `Agency`; `uv run aerich migrate --name agency_conformance && uv run aerich upgrade`.

- [ ] **Step 4: Endpoint + gate.** `agencies.py`: `POST /{agency_id}/conformance` (owner or admin — `authorize_or_403(user, "agency:edit", agency)` then `return await run_conformance(agency)`). In the status-transition path (`agency_lifecycle.py` / the `/status` handler), block `draft → active` unless `agency.conformance_report and agency.conformance_report.get("passed")` — return the envelope error `invalid_request` "conformance test must pass before activation". Add a test for the gate in `tests/test_agency_status_endpoint.py` style.
- [ ] **Step 5: Full suite → PASS. Commit** — `feat(conformance): test battery gating draft->active`

### Task 28: Owner frontend — My Agencies + onboarding

**Files:**
- Create: `frontend/src/features/agencies/MyAgenciesPage.tsx`
- Modify: frontend router/nav config, agencies API client module

- [ ] **Step 1:** Add API functions `getMyAgencies()` (GET `/api/v1/agencies/mine`) and `runConformance(id)` (POST `/api/v1/agencies/{id}/conformance`) following the existing client pattern.
- [ ] **Step 2:** `MyAgenciesPage.tsx` — reuse the card/list components from `AgenciesPage.tsx`, data source `getMyAgencies()`; each card links to `AgencyDetailPage` and shows a "Run conformance test" button rendering the returned `checks` as a pass/fail list, plus a "Submit for approval" hint when `status === 'draft' && report.passed`.
- [ ] **Step 3:** Route `/my-agencies` visible when `user.role === 'agency_owner'`; hide admin-only nav for that role (follow the existing role-based nav pattern — `rtk grep -rn "role" frontend/src --include=*.tsx -l` to find it).
- [ ] **Step 4:** `pnpm exec tsc --noEmit` → clean. **Commit** — `feat(frontend): My Agencies page with conformance runner for owners`

### Task 29: Agency integration kit

**Files:**
- Create: `docs/agency-integration.md`, `examples/reference-agency/main.py`, `examples/reference-agency/README.md`

- [ ] **Step 1:** Write `examples/reference-agency/main.py` — a complete runnable reference:

```python
"""Reference agency endpoint for the Thai Citizen Guide gateway.

Implements the API connection contract: POST a JSON payload whose template is
declared in expected_payload; reply 200 JSON within the gateway timeout.
Run: uvicorn main:app --port 9000
"""
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Reference Agency")


class ChatIn(BaseModel):
    query: str
    session_id: str | None = None


@app.post("/chat")
async def chat(body: ChatIn):
    return {
        "answer": f"(ตัวอย่าง) ได้รับคำถาม: {body.query}",
        "sources": [{"title": "คู่มือประชาชน", "url": "https://example.go.th/guide"}],
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 2:** `docs/agency-integration.md` — document, from the gateway's actual behavior (verify each claim against `dispatch.py` / `scheduler.py` / `conformance.py`): the three connection types and when to choose each; the `expected_payload` placeholder contract (`__query__`, `__session_id__`, `__conversation_id__`, `__user_id__`); header config (`api_headers` name/value list, lower-cased on send); timeout expectations (`dispatch_timeout_s` override, default `AGENCY_CHAT_TIMEOUT`); health-probe behavior (interval, what a probe sends); the conformance battery checks and that activation requires passing; and a copy-paste onboarding walkthrough using the reference agency.
- [ ] **Step 3: Commit** — `docs: agency integration kit with runnable reference agency`. Finish Phase 5: PR `Phase 5: layered authorization + agency self-service onboarding`.

---

## Phase 6 — Quality loop & public trust

Branch: `feat/phase6-quality-trust`

### Task 30: Owner notifications on auto-maintenance

**Files:**
- Modify: `backend/app/services/agency_reconcile.py` (and/or `circuit_breaker.py` trip site), `backend/app/services/email.py` callers
- Test: `backend/tests/test_owner_notifications.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_owner_notifications.py
from app.auth.authz import grant
from app.models import Agency, User
from app.services import owner_notify


async def test_notifies_each_owner_once(db, monkeypatch):
    sent: list[tuple[str, str]] = []

    async def fake_send(to: str, subject: str, body: str) -> None:
        sent.append((to, subject))

    monkeypatch.setattr(owner_notify, "_send_email", fake_send)
    ag = await Agency.create(name="A", status="maintenance", auto_maintenance=True)
    owner = await User.create(email="o@x.com", hashed_password="h", role="agency_owner")
    await grant(owner.id, "owner", "agency", ag.id)

    await owner_notify.notify_owners_maintenance(ag)

    assert sent == [("o@x.com", f"[Thai Citizen Guide] {ag.name} ถูกปรับเป็นสถานะ maintenance")]
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement** `backend/app/services/owner_notify.py`:

```python
"""Email agency owners when their agency is auto-tripped into maintenance."""
import logging

from app.models import Agency, Relationship, User
from app.services.email import send_email as _send_email  # keep patchable alias

logger = logging.getLogger(__name__)


async def notify_owners_maintenance(agency: Agency) -> None:
    owner_ids = await Relationship.filter(
        relation="owner", object_type="agency", object_id=agency.id
    ).values_list("subject_id", flat=True)
    owners = await User.filter(id__in=list(owner_ids), is_active=True)
    subject = f"[Thai Citizen Guide] {agency.name} ถูกปรับเป็นสถานะ maintenance"
    body = (
        f"ระบบตรวจพบความผิดพลาดต่อเนื่องจาก endpoint ของ {agency.name} "
        f"และปรับสถานะเป็น maintenance อัตโนมัติ\n"
        f"กรุณาตรวจสอบ endpoint และดูประวัติได้ที่หน้า My Agencies"
    )
    for o in owners:
        try:
            await _send_email(o.email, subject, body)
        except Exception:
            logger.exception("failed to notify owner %s", o.email)
```

(Check `app/services/email.py` for the real send function signature first and adapt the import/alias.) Call `await notify_owners_maintenance(agency)` at both auto-maintenance trip sites: the reconcile rule in `agency_reconcile.py` and the breaker in `circuit_breaker.py` (fetch the Agency after update).

- [ ] **Step 4: Full suite → PASS. Commit** — `feat(notify): email owners on auto-maintenance trips`

### Task 31: Public status page

**Files:**
- Create: `backend/app/routers/public_status.py`, `frontend/src/features/status/StatusPage.tsx`
- Modify: `backend/app/main.py` (include router), frontend routes (public, no auth guard)
- Test: `backend/tests/test_public_status.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_public_status.py
from app.models import Agency, ConnectionLog
from app.routers.public_status import public_status


async def test_uptime_from_recent_logs_no_internal_fields(db):
    ag = await Agency.create(name="A", status="active")
    for ok in (True, True, True, False):
        await ConnectionLog.create(agency=ag, connection_type="API",
                                   status="success" if ok else "error", action="test")

    rows = await public_status()

    assert rows == [{"name": "A", "status": "active", "uptime_24h_pct": 75.0}]
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement**

```python
# backend/app/routers/public_status.py
"""Public, unauthenticated agency status — name, status, 24h uptime. No internals."""
from datetime import timedelta

from fastapi import APIRouter

from app.models import Agency, ConnectionLog
from app.utils import now

router = APIRouter(prefix="/public", tags=["Public"])


async def public_status() -> list[dict]:
    cutoff = now() - timedelta(hours=24)
    out: list[dict] = []
    for ag in await Agency.exclude(status="draft").order_by("name"):
        total = await ConnectionLog.filter(agency_id=ag.id, created_at__gte=cutoff).count()
        ok = await ConnectionLog.filter(agency_id=ag.id, created_at__gte=cutoff, status="success").count()
        uptime = round(ok / total * 100, 1) if total else None
        out.append({"name": ag.name, "status": str(ag.status), "uptime_24h_pct": uptime})
    return out


@router.get("/status", summary="Public agency status")
async def get_public_status() -> list[dict]:
    return await public_status()
```

Include the router in `main.py` under the `/api/v1` prefix like its siblings. (Test expectation note: with both fresh logs created inside the 24h window, uptime is 75.0.)

- [ ] **Step 4: Frontend** — `StatusPage.tsx` at public route `/status`: table of name / status badge / uptime bar, auto-refresh every 60 s; no auth wrapper. **Step 5: suite + tsc → PASS. Commit** — `feat(status): public agency status page`

### Task 32: Golden questions + scheduled eval harness

**Files:**
- Create: `backend/app/models/evaluation.py`, `backend/app/services/evaluation.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/scheduler.py`, `backend/app/routers/agencies.py` (CRUD endpoints)
- Test: `backend/tests/test_evaluation.py`

- [ ] **Step 1: Models**

```python
# backend/app/models/evaluation.py
"""Golden questions and per-run evaluation scores for agency answer quality."""
from tortoise import fields
from tortoise.models import Model

from app.utils import generate_uuid


class GoldenQuestion(Model):
    id = fields.UUIDField(primary_key=True, default=generate_uuid)
    agency = fields.ForeignKeyField("models.Agency", related_name="golden_questions", on_delete=fields.CASCADE)
    question = fields.TextField()
    expected_topics = fields.JSONField(default=list)  # list[str] the answer should cover
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "golden_questions"


class EvalResult(Model):
    id = fields.UUIDField(primary_key=True, default=generate_uuid)
    golden_question = fields.ForeignKeyField("models.GoldenQuestion", related_name="results", on_delete=fields.CASCADE)
    score = fields.FloatField()          # 0.0–1.0 from LLM judge
    answer = fields.TextField(default="")
    judge_reason = fields.TextField(default="")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "eval_results"
        ordering = ["-created_at"]
```

Export both; `uv run aerich migrate --name evaluation && uv run aerich upgrade`.

- [ ] **Step 2: Failing service test**

```python
# backend/tests/test_evaluation.py
import json

from app.models import Agency, EvalResult
from app.models.evaluation import GoldenQuestion
from app.services import evaluation


async def test_eval_run_scores_each_question(db, monkeypatch):
    ag = await Agency.create(name="A", status="active", connection_type="API", endpoint_url="http://x")
    gq = await GoldenQuestion.create(agency=ag, question="ทำบัตรประชาชนที่ไหน",
                                     expected_topics=["สถานที่", "เอกสาร"])

    async def fake_ask(agency, question):
        return {"ok": True, "latency_ms": 10, "answer": "ไปที่สำนักงานเขต ใช้บัตรเดิม"}

    class _Resp:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": json.dumps({"score": 0.8, "reason": "covers both"})}}],
                    "usage": {}}

    async def fake_judge(payload, **kw):
        return _Resp()

    monkeypatch.setattr(evaluation, "_ask", fake_ask)
    monkeypatch.setattr(evaluation, "openrouter_chat", fake_judge)

    await evaluation.run_evaluation()

    result = await EvalResult.filter(golden_question_id=gq.id).first()
    assert result.score == 0.8 and "สำนักงานเขต" in result.answer
```

- [ ] **Step 3: Run → FAIL. Step 4: Implement**

```python
# backend/app/services/evaluation.py
"""Scheduled answer-quality evaluation: dispatch golden questions, LLM-judge the answers."""
import json
import logging

from app.config import settings
from app.models import Agency, EvalResult
from app.models.evaluation import GoldenQuestion
from app.services.conformance import _ask  # same dispatch probe
from app.services.llm_client import openrouter_chat

logger = logging.getLogger(__name__)

_JUDGE_PROMPT = """\
คุณเป็นผู้ตรวจคุณภาพคำตอบบริการภาครัฐ ให้คะแนนคำตอบ 0.0–1.0
คำถาม: {question}
หัวข้อที่คำตอบควรครอบคลุม: {topics}
คำตอบที่ได้: {answer}

ตอบเป็น JSON เท่านั้น: {{"score": <float>, "reason": "<สั้นๆ>"}}"""


async def run_evaluation() -> int:
    ran = 0
    questions = await GoldenQuestion.all().prefetch_related("agency")
    for gq in questions:
        if gq.agency.status != "active":
            continue
        try:
            res = await _ask(gq.agency, gq.question)
            answer = res["answer"] if res["ok"] else ""
            score, reason = await _judge(gq.question, gq.expected_topics, answer)
            await EvalResult.create(golden_question=gq, score=score, answer=answer, judge_reason=reason)
            ran += 1
        except Exception:
            logger.exception("eval failed for question %s", gq.id)
    return ran


async def _judge(question: str, topics: list, answer: str) -> tuple[float, str]:
    if not answer.strip():
        return 0.0, "no answer from agency"
    prompt = _JUDGE_PROMPT.format(question=question, topics=", ".join(topics), answer=answer[:4000])
    resp = await openrouter_chat(
        {"model": settings.CLASSIFICATION_MODEL, "messages": [{"role": "user", "content": prompt}]},
        purpose="judge",
    )
    content = resp.json()["choices"][0]["message"]["content"]
    data = json.loads(content)
    return float(data["score"]), str(data.get("reason", ""))
```

Scheduler: `Settings` → `EVAL_INTERVAL_HOURS: int = 168` (weekly, group "Agency health"); in `start_scheduler()` add `scheduler.add_job(run_evaluation, IntervalTrigger(hours=settings.EVAL_INTERVAL_HOURS))` (import inside `scheduler.py`).

- [ ] **Step 5: CRUD + trend endpoints in `agencies.py`** — `GET/POST/DELETE /{agency_id}/golden-questions` (owner-or-admin via `authorize_or_403(user, "agency:edit", agency)`) and `GET /{agency_id}/eval-results?limit=50` returning recent scores for charting. Follow the router's existing pydantic/response style; add simple service-level tests for create + list scoped to agency.
- [ ] **Step 6: Full suite → PASS. Commit** — `feat(eval): golden-question harness with scheduled LLM-judge scoring`

### Task 33: Surface low-rated answers to owners

**Files:**
- Modify: `backend/app/routers/feedback.py` (or `agencies.py`), `frontend/src/features/agencies/MyAgenciesPage.tsx`
- Test: `backend/tests/test_owner_feedback.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_owner_feedback.py
from app.models import Agency, User
from app.models.conversation import Conversation, Message
from app.routers.feedback import agency_low_rated


async def test_returns_only_down_rated_for_agency(db):
    ag = await Agency.create(name="A", status="active")
    user = await User.create(email="u@x.com", hashed_password="h")
    conv = await Conversation.create(title="t", user_id=user.id)
    await Message.create(conversation_id=conv.id, role="assistant", content="bad",
                         rating="down", agency_ids=[str(ag.id)])
    await Message.create(conversation_id=conv.id, role="assistant", content="good",
                         rating="up", agency_ids=[str(ag.id)])

    rows = await agency_low_rated(str(ag.id))

    assert len(rows) == 1 and rows[0]["content"] == "bad"
```

(Adjust `Message`/`Conversation` required kwargs to the real model — check `models/conversation.py` field defaults first.)

- [ ] **Step 2: Run → FAIL. Step 3: Implement** in `feedback.py`:

```python
async def agency_low_rated(agency_id: str, limit: int = 50) -> list[dict]:
    rows = (
        await Message.filter(role="assistant", rating="down",
                             agency_ids__contains=[agency_id])
        .order_by("-created_at").limit(limit)
    )
    return [
        {"id": str(m.id), "content": m.content, "feedback_text": m.feedback_text,
         "created_at": str(m.created_at)}
        for m in rows
    ]


@router.get("/agencies/{agency_id}/low-rated", summary="Down-rated answers for an agency")
async def get_agency_low_rated(agency_id: str, user: User = Depends(get_current_user)):
    agency = await Agency.get_or_none(id=agency_id)
    if agency is None:
        raise HTTPException(status_code=404, detail="Agency not found")
    await authorize_or_403(user, "agency:read_logs", agency)
    return await agency_low_rated(agency_id)
```

(`agency_ids__contains` needs Postgres JSONB; if the SQLite test fixture rejects it, filter in Python: fetch `rating="down"` rows then `[m for m in rows if agency_id in (m.agency_ids or [])]` — keep the test green on SQLite.)

- [ ] **Step 4: Frontend** — add a "Low-rated answers" collapsible section per agency card on `MyAgenciesPage.tsx` fetching the new endpoint. **Step 5: suite + tsc → PASS. Commit** — `feat(feedback): surface down-rated answers to agency owners`

### Task 34: Developer quickstart docs

**Files:**
- Create: `docs/quickstart.md`
- Modify: `README.md` (link it)

- [ ] **Step 1:** Write `docs/quickstart.md`: how to get an API key (Profile → API Keys → Create — copy it immediately, shown once); auth header `Authorization: Bearer <key>`; the canonical endpoints (`POST /api/v1/chat`, `POST /api/v1/chat/stream` SSE, `GET /api/v1/conversations`); the error envelope shape and stable codes (from `app/errors.py`); rate limits/quotas (429 + `Retry-After`); working curl + Python (`httpx`) + JS (`fetch` with SSE reader) examples against `http://localhost:8080`; link to the live OpenAPI docs URL (verify the docs path in `main.py` — `/docs` unless customized).
- [ ] **Step 2:** Verify every example against a running dev stack (`docker compose up`), paste real (redacted) responses into the doc.
- [ ] **Step 3: Commit** — `docs: API consumer quickstart`. Finish Phase 6: PR `Phase 6: quality loop and public trust`.

---

## Self-review checklist (run after writing/before executing each phase)

- Spec coverage: roadmap §0→Tasks 2–7, §1.1→8–10, §1.2→11–12, §1.3→13, §1.4→14–15, §1.5→16, §1.6→17, §1.7→1, §2.1→26+28, §2.2→27, §2.3→29, §2.4→30–31, §2.5→32–33, §2.6→23–25, §2.7→10+34, §3.1→19, §3.2→18, §3.3→11+20+21, §3.4→22, §3.5→no tasks (deliberately).
- Known adaptation points (executor must verify, marked inline): exact route-dict construction in `graph.py` (Tasks 11, 15), user resolution in `routers/chat.py` (Tasks 12–13), `email.py` send signature (Task 30), `Message`/`Conversation` required fields (Tasks 24, 33), frontend client/nav patterns (Tasks 3, 10, 16, 28, 31, 33).
- Production sequencing: Task 4's backfill script runs in production BEFORE its drop migration deploys; Task 2 needs the `JWT_SECRET` GitHub secret created before merging.
