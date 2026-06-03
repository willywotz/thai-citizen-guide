# Docker Compose Refactor Design

**Date:** 2026-06-03
**Goal:** Clone → `docker compose up` works with zero configuration.

## Context

The existing `docker-compose.yaml` mixes production and development concerns in a single file. `BUILD_TARGET` is controlled via `.env`, health checks are inconsistent (some use `wget`, some use `curl`, none work in the dev image), and `develop.watch` hot-reload blocks live alongside production service definitions. A new dev cloning the repo cannot run the stack without manually configuring `.env`.

## File Structure

```
docker-compose.yaml          # production base — CI uses this alone
docker-compose.override.yaml # dev overrides — auto-merged by `docker compose up`
.env.example                 # committed template with all vars documented
.env                         # gitignored, copied from .env.example
```

- `docker compose up` automatically merges both YAML files.
- `docker compose -f docker-compose.yaml up` skips the override (CI/prod).

## Base `docker-compose.yaml`

Production-only concerns. Changes from current:

- `BUILD_TARGET=production` hardcoded — no longer an env var.
- Health checks use `curl` (installed in the production image) on port `8080`.
- All `develop.watch` blocks removed.
- Secrets default to empty string so services start silently degraded:
  - `OPENROUTER_API_KEY:-""` — AI features disabled, service starts.
  - `TS_AUTHKEY:-""` — Tailscale no-ops, service starts.
- Services ordered top-to-bottom matching dependency graph: postgres → backend / agent-proxy → frontend → nginx → observability + tailscale.
- Postgres credentials keep current defaults (`chatbot` / `chatbot_secret`), overridable via `.env`.

## `docker-compose.override.yaml`

Dev-only deltas, deep-merged by Docker Compose:

- `BUILD_TARGET=development` for backend and agent-proxy.
- Health checks for backend, agent-proxy, and frontend overridden to use `python3 -c "import urllib.request; urllib.request.urlopen(...)"` — the dev image has no `curl` or `wget`.
- `develop.watch` blocks:
  - **backend**: sync `./backend/app` → `/app/app`; restart on `./backend/migrations` change; rebuild on `pyproject.toml` / `uv.lock` change.
  - **agent-proxy**: sync+restart `./agent-proxy` → `/app`.
  - **frontend**: sync `./frontend/src` → `/app/src`; rebuild on `package.json` change.

## `.env.example`

Committed. Documents every variable a deployer may need to set:

```bash
# Database
POSTGRES_DB=chatbot
POSTGRES_USER=chatbot
POSTGRES_PASSWORD=chatbot_secret

# AI backend — leave empty to run degraded without AI features
OPENROUTER_API_KEY=

# Tailscale VPN — leave empty to skip VPN tunnel
TS_AUTHKEY=

# Nginx port
PORT=80
```

`BUILD_TARGET` is not in `.env.example` — it is now hardcoded per file.

## Out of Scope

- Resource limits / memory caps
- Additional debug ports in dev override
- CI-specific compose file
