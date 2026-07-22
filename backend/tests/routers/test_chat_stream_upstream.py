"""POST /api/v1/chat/stream against a stubbed httpx upstream.

Every other test in the suite patches `_stream_live` out entirely, so the ~70
lines that talk to the real upstream — non-200 handling, SSE reassembly
across chunk boundaries, `ReadTimeout`, and the generic-exception branch —
are asserted by nothing. These tests drive the real ASGI stack with a fake
`httpx.AsyncClient` so `_stream_live` runs for real while no network call
happens.

Characterization tests: they assert what the code does today, not what it
should do. Behaviour preservation is the whole point of this file.
"""

import json
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from tortoise import Tortoise
from unittest.mock import patch

from app.errors import register_error_handlers
from app.models.conversation import Message
from app.routers import chat as chat_router
from app.services.chat import stream as turn_stream


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
    await Tortoise.generate_schemas()
    try:
        yield
    finally:
        await Tortoise.close_connections()


def _client_app() -> FastAPI:
    app = FastAPI(lifespan=_lifespan)
    register_error_handlers(app)
    app.include_router(chat_router.router, prefix="/api/v1")
    return app


class _FakeResponse:
    def __init__(self, status_code: int, chunks: tuple[str, ...]):
        self.status_code = status_code
        self._chunks = chunks

    async def aiter_text(self):
        for chunk in self._chunks:
            yield chunk

    async def aread(self) -> bytes:
        return "".join(self._chunks).encode()


class _FakeStream:
    """The object returned by `client.stream(...)`, an async context manager."""

    def __init__(self, response: _FakeResponse | None, exc: Exception | None):
        self._response = response
        self._exc = exc

    async def __aenter__(self) -> _FakeResponse:
        if self._exc is not None:
            raise self._exc
        return self._response

    async def __aexit__(self, *exc_info) -> bool:
        return False


class _FakeAsyncClient:
    """Stands in for `httpx.AsyncClient` so `_stream_live` makes no real call."""

    def __init__(self, response: _FakeResponse | None = None, exc: Exception | None = None, **kwargs):
        self._response = response
        self._exc = exc

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *exc_info) -> bool:
        return False

    def stream(self, method: str, url: str, **kwargs) -> _FakeStream:
        return _FakeStream(self._response, self._exc)


def _stub_upstream(*, status: int = 200, chunks: tuple[str, ...] = (), exc: Exception | None = None):
    """Patch `app.services.chat.stream.httpx.AsyncClient` for the duration of a `with`."""
    response = None if exc is not None else _FakeResponse(status, chunks)
    factory = lambda **kwargs: _FakeAsyncClient(response, exc, **kwargs)
    return patch.object(turn_stream.httpx, "AsyncClient", factory)


def _events(text: str) -> list[dict]:
    events = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event_name, data = "message", None
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
        events.append({"event": event_name, "data": data})
    return events


def test_happy_path_streams_step_answer_and_done():
    body = (
        'event: step\ndata: {"name": "summarize"}\n\n'
        'event: answer\ndata: {"answer": "คำตอบ", "summary": "", "references": []}\n\n'
        'event: done\ndata: {"session_id": "s1", "total_ms": 42}\n\n'
    )
    with _stub_upstream(status=200, chunks=(body,)), TestClient(_client_app()) as client:
        r = client.post("/api/v1/chat/stream", json={"query": "บัตรหาย"})
        assert r.status_code == 200
        events = _events(r.text)
        assert [e["event"] for e in events] == ["step", "answer", "done"]
        assert events[1]["data"]["answer"] == "คำตอบ"
        assert "message_id" in events[2]["data"]

        message_id = events[2]["data"]["message_id"]

        async def _fetch():
            return await Message.get(id=message_id)

        saved = client.portal.call(_fetch)
    assert saved.role == "assistant"
    assert saved.content == "คำตอบ"


def test_sse_reassembly_across_chunk_boundaries():
    full = (
        'event: answer\ndata: {"answer": "OK", "summary": "", "references": []}\n\n'
        'event: done\ndata: {"session_id": "s1", "total_ms": 1}\n\n'
    )
    cut1 = full.index("event: answer") + len("event: ans")  # mid `event:` line
    cut2 = full.index('"answer":') + len('"answ')  # mid-JSON key
    chunks = (full[:cut1], full[cut1:cut2], full[cut2:])

    with _stub_upstream(status=200, chunks=chunks), TestClient(_client_app()) as client:
        r = client.post("/api/v1/chat/stream", json={"query": "q"})
    events = _events(r.text)
    assert [e["event"] for e in events] == ["answer", "done"]
    assert events[0]["data"]["answer"] == "OK"


def test_upstream_non_200_emits_error_then_done():
    with _stub_upstream(status=502, chunks=()), TestClient(_client_app()) as client:
        r = client.post("/api/v1/chat/stream", json={"query": "q"})
    events = _events(r.text)
    assert [e["event"] for e in events] == ["error", "done"]
    assert events[0]["data"]["code"] == 502


def test_read_timeout_emits_error_then_done():
    with _stub_upstream(exc=httpx.ReadTimeout("timed out")), TestClient(_client_app()) as client:
        r = client.post("/api/v1/chat/stream", json={"query": "q"})
    events = _events(r.text)
    assert [e["event"] for e in events] == ["error", "done"]
    assert "timed out" in events[0]["data"]["message"]
