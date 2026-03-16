"""
FastAPI application entry point for Thai Citizen Guide backend.
Replaces all Supabase Edge Functions.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import chat, agencies, conversations, dashboard, feedback, api_keys, users, parse_spec


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: nothing required (SQLAlchemy engine is lazy)
    yield
    # Shutdown: dispose connection pool
    from app.database import engine
    await engine.dispose()


app = FastAPI(
    title="Thai Citizen Guide API",
    description="FastAPI + LangGraph backend for AI Portal กลาง",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(chat.router,          prefix="/api/v1")
app.include_router(agencies.router,      prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(dashboard.router,     prefix="/api/v1")
app.include_router(feedback.router,      prefix="/api/v1")
app.include_router(api_keys.router,      prefix="/api/v1")
app.include_router(users.router,         prefix="/api/v1")
app.include_router(parse_spec.router,    prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
