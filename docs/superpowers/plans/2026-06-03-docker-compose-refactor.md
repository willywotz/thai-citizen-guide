# Docker Compose Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `docker-compose.yaml` into a production base + auto-applied dev override so `git clone && docker compose up` works with zero configuration.

**Architecture:** `docker-compose.yaml` holds only production-ready service definitions. `docker-compose.override.yaml` (auto-merged by Docker Compose) adds dev targets, hot-reload watch blocks, and health check overrides for the dev image. `.env.example` is committed with all variables documented and safe defaults.

**Tech Stack:** Docker Compose v2, multi-stage Dockerfiles (`development` / `production` targets).

---

### Task 1: Rewrite `docker-compose.yaml` (production base)

**Files:**
- Modify: `docker-compose.yaml`

Context:
- `BUILD_TARGET` is removed — hardcoded as `target: production` per service.
- Backend health check uses `curl` (installed in the production image via `apt install curl`).
- Agent-proxy and frontend health checks keep `wget` (available in those images).
- All `develop.watch` blocks removed.
- Secrets default to empty string so services start silently degraded.
- Services ordered top-to-bottom by dependency: postgres → backend / agent-proxy → frontend → nginx → observability / tailscale.

- [ ] **Step 1: Replace the file contents**

```yaml
services:

  postgres:
    image: pgvector/pgvector:pg16
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-chatbot}
      POSTGRES_USER: ${POSTGRES_USER:-chatbot}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-chatbot_secret}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - chatbot-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-chatbot} -d ${POSTGRES_DB:-chatbot}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  backend:
    build:
      context: ./backend
      target: production
    restart: unless-stopped
    environment:
      DATABASE_URL: postgres://${POSTGRES_USER:-chatbot}:${POSTGRES_PASSWORD:-chatbot_secret}@${POSTGRES_HOST:-postgres}:5432/${POSTGRES_DB:-chatbot}
      OPENROUTER_API_KEY: ${OPENROUTER_API_KEY:-}
    depends_on:
      postgres:
        condition: service_healthy
        restart: true
    networks:
      - chatbot-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s

  agent-proxy:
    build:
      context: ./agent-proxy
      target: production
    restart: unless-stopped
    environment:
      DATABASE_URL: postgres://${POSTGRES_USER:-chatbot}:${POSTGRES_PASSWORD:-chatbot_secret}@${POSTGRES_HOST:-postgres}:5432/${POSTGRES_DB:-chatbot}
    depends_on:
      postgres:
        condition: service_healthy
        restart: true
    networks:
      - chatbot-network
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s

  frontend:
    build:
      context: ./frontend
      target: production
    restart: unless-stopped
    networks:
      - chatbot-network
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:8080"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s

  nginx:
    image: nginx
    restart: unless-stopped
    volumes:
      - ./default.conf:/etc/nginx/conf.d/default.conf
    depends_on:
      frontend:
        condition: service_healthy
        restart: true
      backend:
        condition: service_healthy
        restart: true
      agent-proxy:
        condition: service_healthy
        restart: true
      otel-collector:
        condition: service_started
      zipkin:
        condition: service_started
    networks:
      - chatbot-network
    ports:
      - "${PORT:-80}:80"

  otel-collector:
    image: otel/opentelemetry-collector
    restart: unless-stopped
    volumes:
      - ./otel-collector-config.yaml:/etc/otelcol/config.yaml
    networks:
      - chatbot-network

  zipkin:
    image: openzipkin/zipkin
    restart: unless-stopped
    networks:
      - chatbot-network

  tailscale:
    image: tailscale/tailscale:latest
    restart: unless-stopped
    environment:
      - TS_AUTHKEY=${TS_AUTHKEY:-}
      - TS_EXTRA_ARGS=--advertise-tags=tag:container
      - TS_STATE_DIR=/var/lib/tailscale
      - TS_USERSPACE=false
      - TS_SERVE_CONFIG=/config/serve.json
    volumes:
      - tailscale:/var/lib/tailscale
      - ./serve.json:/config/serve.json:ro
    devices:
      - /dev/net/tun:/dev/net/tun
    cap_add:
      - net_admin
      - net_raw
    networks:
      - chatbot-network

volumes:
  postgres_data:
  tailscale:

networks:
  chatbot-network:
```

- [ ] **Step 2: Validate the file parses cleanly**

```bash
docker compose -f docker-compose.yaml config --quiet
```

Expected: no output, exit code 0.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yaml
git commit -m "refactor: production-only base docker-compose.yaml"
```

---

### Task 2: Create `docker-compose.override.yaml` (dev overrides)

**Files:**
- Create: `docker-compose.override.yaml`

Context:
- Docker Compose automatically merges `docker-compose.override.yaml` when running `docker compose up` — no flag needed.
- Only the backend health check needs overriding: the dev image (`python:3.12-slim`) has no `curl` or `wget`. Agent-proxy and frontend dev images both have `wget`.
- `develop.watch` requires running `docker compose watch` (or `docker compose up --watch`), not plain `up`. The blocks are defined here so watch mode works when needed.

- [ ] **Step 1: Create the file**

```yaml
services:

  backend:
    build:
      target: development
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"]
    develop:
      watch:
        - action: rebuild
          path: ./backend/pyproject.toml
        - action: rebuild
          path: ./backend/uv.lock
        - action: restart
          path: ./backend/migrations
          target: /app/migrations
        - action: sync
          path: ./backend/app
          target: /app/app

  agent-proxy:
    build:
      target: development
    develop:
      watch:
        - action: sync+restart
          path: ./agent-proxy
          target: /app

  frontend:
    build:
      target: development
    develop:
      watch:
        - action: sync
          path: ./frontend/src
          target: /app/src
        - action: rebuild
          path: ./frontend/package.json
```

- [ ] **Step 2: Validate merged config**

```bash
docker compose config --quiet
```

Expected: no output, exit code 0. (This implicitly merges both files.)

- [ ] **Step 3: Commit**

```bash
git add docker-compose.override.yaml
git commit -m "refactor: add dev override for hot-reload and dev health checks"
```

---

### Task 3: Update `.env.example`

**Files:**
- Modify: `.env.example`

Context:
- `BUILD_TARGET` is removed — it is no longer a user-controlled variable.
- All other variables that can be customised are listed with safe defaults.
- `.env` is already in `.gitignore`.

- [ ] **Step 1: Replace the file contents**

```bash
# Database
POSTGRES_DB=chatbot
POSTGRES_USER=chatbot
POSTGRES_PASSWORD=chatbot_secret

# AI backend — leave empty to run degraded without AI features
OPENROUTER_API_KEY=

# Tailscale VPN — leave empty to skip VPN tunnel
TS_AUTHKEY=

# Nginx listen port
PORT=80
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "chore: update .env.example with all variables, remove BUILD_TARGET"
```

---

### Task 4: Verify full dev stack

**Files:** none (verification only)

- [ ] **Step 1: Rebuild images with new targets**

```bash
docker compose build
```

Expected: all three images build without error (`backend`, `agent-proxy`, `frontend`).

- [ ] **Step 2: Bring up the stack**

```bash
docker compose up -d
```

Expected: all 8 services start, no dependency failures.

- [ ] **Step 3: Confirm all services healthy**

```bash
docker compose ps
```

Expected: every service shows `(healthy)` or `Up` (tailscale and otel-collector do not have health checks).

- [ ] **Step 4: Spot-check backend health endpoint directly**

```bash
docker compose exec backend python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/health').status)"
```

Expected: `200`

- [ ] **Step 5: Remove BUILD_TARGET from local .env if present**

```bash
grep -v "^BUILD_TARGET" .env > .env.tmp && mv .env.tmp .env
```

Expected: `.env` no longer contains `BUILD_TARGET`. Re-run `docker compose ps` to confirm the stack is still healthy.
