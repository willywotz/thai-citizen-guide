"""OpenAI-shaped errors, scoped to the /responses surface.

Every other route uses app/errors.py's {"error": {"code", "message", ...}}
envelope. An OpenAI SDK client parses {"error": {"message", "type", "param",
"code"}} instead, so this router deliberately diverges.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ResponsesApiError(Exception):
    def __init__(
        self, message: str, *, type: str = "invalid_request_error",
        param: str | None = None, code: str | None = None, status: int = 400,
    ):
        super().__init__(message)
        self.message = message
        self.type = type
        self.param = param
        self.code = code
        self.status = status

    def envelope(self) -> dict:
        return {
            "error": {
                "message": self.message,
                "type": self.type,
                "param": self.param,
                "code": self.code,
            }
        }


def register_responses_error_handler(app: FastAPI) -> None:
    @app.exception_handler(ResponsesApiError)
    async def _responses_error(_req: Request, exc: ResponsesApiError):
        return JSONResponse(status_code=exc.status, content=exc.envelope())
