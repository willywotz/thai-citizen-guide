"""Tests for _test_rest's POST-on-405 verification.

A POST-only chat endpoint answers HEAD/GET with 405. The connection test should
not report that as plain success; it should POST a probe and judge by the real
response.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.agency import _test_rest


class _Resp:
    def __init__(self, status_code, reason="OK", headers=None):
        self.status_code = status_code
        self.reason_phrase = reason
        self.headers = headers or {"content-type": "application/json", "server": "nginx"}


class _FakeClient:
    def __init__(self, head=None, post=None, head_exc=None):
        self._head = head
        self._post = post
        self._head_exc = head_exc
        self.posted = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def head(self, url, headers=None):
        if self._head_exc:
            raise self._head_exc
        return self._head

    async def get(self, url, headers=None):
        return self._head

    async def post(self, url, headers=None, json=None):
        self.posted = {"url": url, "headers": headers, "json": json}
        return self._post


def _agency(**kw):
    base = {"endpoint_url": "https://x.example/chat", "api_headers": [], "expected_payload": None}
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_rest_head_2xx_is_success():
    fake = _FakeClient(head=_Resp(200, "OK"))
    with patch("app.services.agency.httpx.AsyncClient", return_value=fake):
        res = await _test_rest(_agency())
    assert res["success"] is True
    assert res["statusCode"] == 200
    assert fake.posted is None  # no POST probe needed


@pytest.mark.asyncio
async def test_rest_405_then_post_2xx_is_success():
    fake = _FakeClient(head=_Resp(405, "Method Not Allowed"), post=_Resp(200, "OK"))
    with patch("app.services.agency.httpx.AsyncClient", return_value=fake):
        res = await _test_rest(_agency(expected_payload={"query": "__query__"}))
    assert res["success"] is True
    assert res["statusCode"] == 200
    # the POST probe substituted the __query__ placeholder
    assert fake.posted["json"]["query"] == "ทดสอบการเชื่อมต่อ"
    assert any("POST" in s["label"] for s in res["steps"])


@pytest.mark.asyncio
async def test_rest_405_then_post_4xx_not_success():
    fake = _FakeClient(head=_Resp(405, "Method Not Allowed"), post=_Resp(401, "Unauthorized"))
    with patch("app.services.agency.httpx.AsyncClient", return_value=fake):
        res = await _test_rest(_agency())
    assert res["success"] is False
    assert res["statusCode"] == 401
    assert "401" in (res.get("error") or "")
