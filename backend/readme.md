cd backend

# 1. Create venv + install all deps (first time)
uv sync

# 2. First-time DB setup
uv run aerich init-db

# 3. Start the dev server
uv run uvicorn app.main:app --reload

# ── After changing models ──────────────────────
uv run aerich migrate --name "describe_change"
uv run aerich upgrade

# ── Add a new package ─────────────────────────
uv add some-package

# ── Add a dev-only package ────────────────────
uv add --dev pytest-something

npx @modelcontextprotocol/inspector
