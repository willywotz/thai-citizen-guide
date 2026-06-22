# System / CI / Infra Hygiene Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Get every existing test running in CI, add a pre-deploy gate, drive hardcoded config/secrets into env/secrets, document the nginx routing contract, standardize healthchecks, and speed the pipeline with caching — without changing application behavior.

**Architecture:** Three GitHub Actions workflows on a `dev → main` flow. `test.yml` is the reusable unit/integration suite (`workflow_call`). `test-e2e.yaml` is the full-stack docker-compose sweep. `deploy.yml` (self-hosted) deploys to prod on merged PR→`main`, now gated on both. nginx keeps its two-file split (gateway `default.conf` + SPA `frontend/nginx.conf`) with a documented routing contract. Config defaults stay localhost-safe for zero-config `docker compose up`; prod values come from secrets.

**Tech Stack:** Docker Compose, nginx, GitHub Actions, Playwright, Vitest, pytest, uv, Go, pnpm, self-hosted runner for deploy.

Each task is small and independently shippable as its own PR into `dev`. Respect CLAUDE.md: branch off `dev`, PR into `dev`; never push to `main` directly (prod deploys only via merged PR `dev → main`).

---

## File Map

**Created:**
- `.env.prod.example` — committed template documenting all prod vars (no real secrets)
- (optional) `docs/ROUTING.md` — only if the inline nginx comments prove insufficient; default is inline comments + the spec table

**Modified:**
- `.github/workflows/test.yml` — add frontend vitest + coverage; add uv & go caching
- `.github/workflows/test-e2e.yaml` — also trigger on PR→`dev`; creds from secrets; docker layer cache
- `.github/workflows/deploy.yml` — `needs:` gate on reusable test + test-e2e; write prod secrets to `.env`
- `default.conf` — header comment documenting the routing contract + pointer to `frontend/nginx.conf`
- `frontend/nginx.conf` — header comment pointing back to the gateway contract
- `docker-compose.yaml` — standardize healthcheck host/path/timing
- `e2e/.env.test.example`, `blackbox/.env.test.example` — comment that CI overrides creds from secrets

**Deleted:** none.

---

## Task 1: Create branch

**Files:** none.

- [ ] **Step 1: Branch off `dev`**

```bash
rtk git checkout dev && rtk git pull
rtk git checkout -b chore/system-ci-hygiene
```

- [ ] **Step 2: Verify clean baseline**

```bash
rtk git status
docker compose -f docker-compose.yaml config >/dev/null && echo "compose ok"
```

Expected: clean tree on `chore/system-ci-hygiene`; `compose ok`.

---

## Task 2: Run frontend vitest + coverage in CI

**Files:** Modify `.github/workflows/test.yml`.

The frontend job today ends at `tsc --noEmit`. There are 30 `src/**/*.test.{ts,tsx}` files and a `"test": "vitest run"` script (verified). Add vitest with coverage report (report-only, no threshold yet).

- [ ] **Step 1: Append test step to the frontend job**

```yaml
  frontend:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: frontend } }
    steps:
      - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3
      - uses: pnpm/action-setup@0e279bb959325dab635dd2c09392533439d90093 # v6.0.8
        with: { version: 11.5.0 }
      - uses: actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e # v6.4.0
        with: { node-version: 22, cache: pnpm, cache-dependency-path: frontend/pnpm-lock.yaml }
      - run: pnpm install --frozen-lockfile
      - run: pnpm exec tsc --noEmit
      - run: pnpm test
```

(`@vitest/coverage-v8` is not yet a dep. If `pnpm test -- --coverage` fails, run plain `pnpm test` here and add coverage in a follow-up to keep this task shippable. Verify locally first — see Step 2.)

- [ ] **Step 2: Verify the suite is green locally before pushing**

```bash
cd frontend && pnpm install --frozen-lockfile && pnpm test
```

Expected: all test files pass. If any fail, they were already broken — quarantine with `test.skip` + a TODO referencing the relevant component spec (do NOT fix app logic in this infra PR), then note it in the PR description.

- [ ] **Step 3: Commit**

```bash
rtk git add .github/workflows/test.yml && rtk git commit -m "ci: run frontend vitest in CI (was tsc-only)"
```

- [ ] **Step 4: Push and confirm the run is green**

```bash
rtk git push -u origin chore/system-ci-hygiene
rtk gh run list --limit 3
```

Expected: latest `Test` run for this branch concludes `success`.

---

## Task 3: Add dependency caching (uv + go)

**Files:** Modify `.github/workflows/test.yml`.

Frontend already caches pnpm. Backend (uv) and agent-proxy (go) re-resolve every run.

- [ ] **Step 1: Cache uv in the backend job (before `uv sync`)**

```yaml
      - uses: astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39 # v8.2.0
        with:
          enable-cache: true
          cache-dependency-glob: backend/uv.lock
      - run: uv sync --extra dev
```

- [ ] **Step 2: Enable Go module/build cache in the agent-proxy job**

`actions/setup-go` caches by default when a `go.sum` is found; point it at the right path:

```yaml
      - uses: actions/setup-go@4a3601121dd01d1626a1e23e37211e3254c1c06c # v6.4.0
        with:
          go-version-file: agent-proxy/go.mod
          cache-dependency-path: agent-proxy/go.sum
      - run: go build ./... && go test ./...
```

- [ ] **Step 3: Verify YAML and run**

```bash
docker compose -f docker-compose.yaml config >/dev/null && echo ok   # sanity, unrelated YAML
rtk git add .github/workflows/test.yml && rtk git commit -m "ci: cache uv and go deps"
rtk git push
rtk gh run list --limit 3
```

Expected: green run; second run shows `Cache restored` for uv and go in the logs.

---

## Task 4: Source test credentials from secrets

**Files:** Modify `.github/workflows/test-e2e.yaml`, `e2e/.env.test.example`, `blackbox/.env.test.example`.

Admin creds `admin@example.com`/`admin1234` are literal in YAML. Move to repo secrets `E2E_ADMIN_EMAIL`, `E2E_ADMIN_PASSWORD`, `E2E_TEST_USER_PASSWORD`. The committed `.env.test.example` files keep localhost defaults for dev with a comment.

- [ ] **Step 1: Create the repo secrets (one-time)**

```bash
rtk gh secret set E2E_ADMIN_EMAIL --body "admin@example.com"
rtk gh secret set E2E_ADMIN_PASSWORD --body "admin1234"
rtk gh secret set E2E_TEST_USER_PASSWORD --body "blackbox1234"
```

(Values match the current bootstrap admin; change them only alongside the backend bootstrap.)

- [ ] **Step 2: Replace literals in both env blocks of `test-e2e.yaml`**

Both the "Blackbox API tests" and "E2E UI tests" steps, and the "Wait for admin bootstrap" curl payload, reference creds. Update the env blocks:

```yaml
        env:
          API_URL: http://localhost:8080
          ADMIN_EMAIL: ${{ secrets.E2E_ADMIN_EMAIL }}
          ADMIN_PASSWORD: ${{ secrets.E2E_ADMIN_PASSWORD }}
          TEST_USER_PASSWORD: ${{ secrets.E2E_TEST_USER_PASSWORD }}
```

And the bootstrap-wait step:

```yaml
      - name: Wait for admin bootstrap
        env:
          ADMIN_EMAIL: ${{ secrets.E2E_ADMIN_EMAIL }}
          ADMIN_PASSWORD: ${{ secrets.E2E_ADMIN_PASSWORD }}
        run: |
          for i in $(seq 1 30); do
            if curl -fsS -X POST http://localhost:8080/api/v1/auth/login \
                 -H 'Content-Type: application/json' \
                 -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" >/dev/null 2>&1; then
              echo "admin account ready"; exit 0
            fi
            echo "waiting for admin bootstrap ($i)…"; sleep 5
          done
          echo "::error::admin account never became available"; exit 1
```

- [ ] **Step 3: Annotate the example files**

Add a leading comment to `e2e/.env.test.example` and `blackbox/.env.test.example`:

```bash
# Local defaults only. CI overrides ADMIN_EMAIL / ADMIN_PASSWORD / TEST_USER_PASSWORD
# from repo secrets E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD / E2E_TEST_USER_PASSWORD.
```

- [ ] **Step 4: Verify and commit**

```bash
docker run --rm -i ghcr.io/rhysd/actionlint:latest < /dev/null  # optional lint
rtk git add .github/workflows/test-e2e.yaml e2e/.env.test.example blackbox/.env.test.example
rtk git commit -m "ci: source e2e admin creds from secrets, not literal YAML"
```

---

## Task 5: Run the full-stack sweep on PR→dev

**Files:** Modify `.github/workflows/test-e2e.yaml`.

Today it triggers only on `pull_request:[main]`. Add `dev` so the dev flow exercises the stack.

- [ ] **Step 1: Extend the trigger**

```yaml
on:
  workflow_dispatch:
  workflow_call:
  pull_request:
    branches: [main, dev]
```

- [ ] **Step 2: Commit and confirm it triggers on this PR**

```bash
rtk git add .github/workflows/test-e2e.yaml
rtk git commit -m "ci: run full-stack e2e sweep on PR to dev"
rtk git push
rtk gh run list --limit 5
```

Expected: a `Test-E2E` run appears for this branch's PR into `dev` and concludes `success`.

---

## Task 6: De-hardcode prod config + add `.env.prod.example`

**Files:** Create `.env.prod.example`; modify `deploy.yml`. (Do NOT edit `backend/app/config.py` defaults — they stay as localhost-safe fallbacks; we only ensure prod values are *provided* via `.env`, which pydantic-settings already reads.)

`config.py` already loads `.env` (`SettingsConfigDict(env_file=".env")`) and `apply_overrides` exists. The fix is operational: make deploy write the real values from secrets instead of relying on code defaults that contain prod IPs.

- [ ] **Step 1: Create `.env.prod.example` (committed, no real secrets)**

```bash
# Copy to .env on the prod host (or generate in CI from secrets). No real secrets in this file.

# ── Gateway ──────────────────────────────────────────────────────────────
EXTERNAL_HTTP_PORT=80
EXTERNAL_POSTGRES_PORT=5432

# ── Environment ──────────────────────────────────────────────────────────
ENV=production            # triggers assert_production_secrets (JWT_SECRET must change)

# ── Database ─────────────────────────────────────────────────────────────
POSTGRES_DB=chatbot
POSTGRES_USER=chatbot
POSTGRES_PASSWORD=          # set a strong value in prod

# ── Auth ─────────────────────────────────────────────────────────────────
JWT_SECRET=                 # python -c "import secrets; print(secrets.token_hex(32))"

# ── CORS / URLs (no IPs in source) ───────────────────────────────────────
CORS_ORIGINS=["https://your-prod-host"]
FRONTEND_BASE_URL=https://your-prod-host

# ── External services ────────────────────────────────────────────────────
ONECHAT_V3_URL=
ONECHAT_V4_URL=
MCP_ENDPOINT_URL=

# ── LLM ──────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY=         # rotate the previously-committed key
```

- [ ] **Step 2: Expand the `.env` heredoc in `deploy.yml`**

```yaml
      - run: |
          cat > .env << EOF
          EXTERNAL_HTTP_PORT=80
          EXTERNAL_POSTGRES_PORT=5432
          ENV=production
          POSTGRES_PASSWORD=${{ secrets.POSTGRES_PASSWORD }}
          JWT_SECRET=${{ secrets.JWT_SECRET }}
          CORS_ORIGINS=${{ secrets.CORS_ORIGINS }}
          FRONTEND_BASE_URL=${{ secrets.FRONTEND_BASE_URL }}
          ONECHAT_V3_URL=${{ secrets.ONECHAT_V3_URL }}
          ONECHAT_V4_URL=${{ secrets.ONECHAT_V4_URL }}
          MCP_ENDPOINT_URL=${{ secrets.MCP_ENDPOINT_URL }}
          OPENROUTER_API_KEY=${{ secrets.OPENROUTER_API_KEY }}
          EOF
```

(Heredoc changed from quoted `'EOF'` to unquoted `EOF` so `${{ }}` expansion still happens at the YAML layer — these are Actions expressions, resolved before the shell runs, so quoting is moot, but unquoted is clearer. Verify the rendered file has no literal `${{`.)

- [ ] **Step 3: Set the prod secrets (one-time, by maintainer)**

```bash
rtk gh secret set JWT_SECRET --body "$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
# POSTGRES_PASSWORD, CORS_ORIGINS, FRONTEND_BASE_URL, ONECHAT_V3_URL, ONECHAT_V4_URL,
# MCP_ENDPOINT_URL, OPENROUTER_API_KEY — set with rtk gh secret set ...
```

- [ ] **Step 4: ROTATE the leaked OpenRouter key (out-of-band, mandatory)**

The key currently in the on-disk `.env` is live. Revoke it in the OpenRouter dashboard and set the new one as `secrets.OPENROUTER_API_KEY`. Confirm the on-disk `.env` is gitignored (it is) and never committed.

```bash
rtk git status   # confirm .env is NOT staged/tracked
git check-ignore .env && echo ".env ignored"
```

- [ ] **Step 5: Commit**

```bash
rtk git add .env.prod.example .github/workflows/deploy.yml
rtk git commit -m "chore: de-hardcode prod config into .env from secrets; add .env.prod.example"
```

---

## Task 7: Document the nginx routing contract

**Files:** Modify `default.conf`, `frontend/nginx.conf`.

The two files are not duplicates (gateway vs SPA server). Add cross-referencing header comments so they stop drifting; no routing behavior change.

- [ ] **Step 1: Header comment in `default.conf`**

```nginx
# Gateway reverse proxy (container: nginx). Routing contract — single source of truth:
#   /api,/sse,/messages,/mcp,/docs,/redoc,/openapi.json -> backend:8080
#   /agent-proxy/                                        -> agent-proxy:8080
#   /jaeger/                                             -> jaeger:16686
#   /                                                    -> frontend:8080 (SPA; see frontend/nginx.conf)
# See docs/superpowers/specs/2026-06-23-system-ci-refactor-design.md
server {
    listen 8080;
    ...
```

- [ ] **Step 2: Header comment in `frontend/nginx.conf`**

```nginx
# SPA static server INSIDE the frontend image (not the gateway). The gateway
# (../default.conf) forwards "/" here; this file does SPA fallback + asset caching.
# Health path is /healthz (NOT /health — that is a client route, see note below).
server {
    listen       8080;
    ...
```

- [ ] **Step 3: Validate nginx syntax for both**

```bash
docker run --rm -v "$PWD/default.conf:/etc/nginx/conf.d/default.conf:ro" nginx nginx -t
docker run --rm -v "$PWD/frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro" nginx nginx -t
```

Expected: both print `syntax is ok` / `test is successful`.

- [ ] **Step 4: Commit**

```bash
rtk git add default.conf frontend/nginx.conf
rtk git commit -m "docs(nginx): document gateway vs SPA routing contract inline"
```

---

## Task 8: Standardize healthchecks

**Files:** Modify `docker-compose.yaml`.

Align host (`127.0.0.1`) and timing across HTTP healthchecks; keep each service's real health path (frontend must stay `/healthz` — `/health` is a client route).

- [ ] **Step 1: Update backend/agent-proxy healthchecks to `127.0.0.1` and aligned timing**

```yaml
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/health"]
      interval: 15s
      timeout: 10s
      retries: 3
      start_period: 20s
```

- [ ] **Step 2: Align frontend healthcheck timing (keep `/healthz`)**

```yaml
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]
      interval: 15s
      timeout: 10s
      retries: 3
      start_period: 20s
```

- [ ] **Step 3: Verify compose parses and the stack comes up healthy**

```bash
docker compose -f docker-compose.yaml config >/dev/null && echo "config ok"
docker compose -f docker-compose.yaml up -d --build --wait --wait-timeout 300
docker compose -f docker-compose.yaml ps
docker compose -f docker-compose.yaml down
```

Expected: `config ok`; all services reach `healthy`; `ps` shows no `unhealthy`.

- [ ] **Step 4: Commit**

```bash
rtk git add docker-compose.yaml
rtk git commit -m "chore(compose): standardize healthcheck host and timing"
```

---

## Task 9: Add the pre-deploy gate

**Files:** Modify `deploy.yml`. Do this LAST so earlier tasks have already proven the suites green.

`deploy.yml` deploys on merged PR→`main` with no gate. Add reusable calls to `test.yml` and `test-e2e.yaml`, and make `deploy` depend on both.

- [ ] **Step 1: Add gating jobs and `needs:` on deploy**

```yaml
jobs:
  test:
    if: github.event.pull_request.merged || github.event_name == 'workflow_dispatch'
    uses: ./.github/workflows/test.yml

  e2e:
    if: github.event.pull_request.merged || github.event_name == 'workflow_dispatch'
    uses: ./.github/workflows/test-e2e.yaml
    secrets: inherit

  deploy:
    needs: [test, e2e]
    if: github.event.pull_request.merged || github.event_name == 'workflow_dispatch'
    runs-on: self-hosted
    steps:
      - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3
      - run: |
          cat > .env << EOF
          ... (heredoc from Task 6 Step 2) ...
          EOF
      - run: docker compose -f docker-compose.yaml up -d --build --remove-orphans
```

(`test-e2e.yaml` already exposes `workflow_call`; `secrets: inherit` passes the E2E creds. `workflow_dispatch` remains a break-glass path that still runs the gate.)

- [ ] **Step 2: Validate the workflow graph**

```bash
docker run --rm -i ghcr.io/rhysd/actionlint:latest .github/workflows/deploy.yml || true
rtk grep -n "needs:" .github/workflows/deploy.yml
```

Expected: `deploy` shows `needs: [test, e2e]`.

- [ ] **Step 3: Commit and open the PR into `dev`**

```bash
rtk git add .github/workflows/deploy.yml
rtk git commit -m "ci: gate prod deploy on test + e2e (no more ungated deploy)"
rtk git push
rtk gh pr create --base dev --head chore/system-ci-hygiene \
  --title "chore: system/CI/infra hygiene" \
  --body "Runs frontend vitest in CI, adds pre-deploy gate, de-hardcodes config/secrets, documents nginx routing, standardizes healthchecks, caches deps. See docs/superpowers/specs/2026-06-23-system-ci-refactor-design.md"
```

- [ ] **Step 4: Confirm green before requesting review**

```bash
rtk gh pr checks
```

Expected: `Test`, `Test-E2E` checks all pass. The `Deploy` gate only runs on merge to `main` later (prod promotion via PR `dev → main`).

---

## Verification Checklist (whole plan)

- [ ] `rtk gh run list` shows `Test` running frontend vitest (not just tsc) and green.
- [ ] uv + go caches restore on the second run.
- [ ] No literal `admin@example.com` / passwords remain in `.github/workflows/` (`rtk grep -rn "admin1234" .github/`).
- [ ] `Test-E2E` triggers on PR→`dev`.
- [ ] `.env.prod.example` exists; `deploy.yml` writes all prod vars from secrets; old OpenRouter key rotated.
- [ ] `nginx -t` passes for both configs; routing comments present.
- [ ] `docker compose -f docker-compose.yaml up --wait` brings all services to `healthy`.
- [ ] `deploy.yml` `deploy` job has `needs: [test, e2e]`.
- [ ] No application request/response behavior changed (sibling component specs own that).
