"""
Verify that the OpenAPI schema exposes only the canonical chat surfaces
(/chat and /chat/stream) and hides the internal/external variants.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.chat import router as chat_router


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(chat_router, prefix="/api/v1")
    return app


def test_openapi_hides_internal_chat_variants():
    schema = TestClient(_app()).get("/openapi.json").json()
    paths = schema["paths"]
    assert "/api/v1/chat" in paths
    assert "/api/v1/chat/stream" in paths
    assert "/api/v1/chat/external" not in paths
    assert "/api/v1/chat/internal" not in paths
