"""Standard error envelope: {"error": {"code", "message", "retryable", ...}}.

Stable codes: invalid_request, unauthorized, forbidden, not_found, quota_exceeded,
rate_limited, agency_unavailable, agency_timeout, llm_error, internal.
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

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

    async def _http_error(_req: Request, exc):
        code = _STATUS_CODES.get(exc.status_code, "internal")
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, str(exc.detail), retryable=exc.status_code == 429),
            headers=getattr(exc, "headers", None),
        )

    app.add_exception_handler(HTTPException, _http_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)

    from app.services.responses.errors import register_responses_error_handler

    register_responses_error_handler(app)
