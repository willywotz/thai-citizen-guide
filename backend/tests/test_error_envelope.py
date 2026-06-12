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
