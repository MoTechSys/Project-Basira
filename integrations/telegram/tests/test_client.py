"""client.py against httpx.MockTransport: success, every documented error code, timeouts, garbage."""

from __future__ import annotations

import json

import httpx
import pytest

from bot.client import ApiError, ApiTimeoutError, BasiraClient, UnreachableError

from conftest import api_transport, load


def client(routes: dict[str, object], log: list[httpx.Request] | None = None, **kw: object) -> BasiraClient:
    return BasiraClient("https://api.test", transport=api_transport(routes, log=log), **kw)  # type: ignore[arg-type]


async def test_check_200_sends_text_and_ui_lang() -> None:
    log: list[httpx.Request] = []
    c = client({"/v1/check": "found_quran"}, log)
    body = await c.check("قال تعالى: ﴿إن الله مع الصابرين﴾")
    assert body["quotes"][0]["status"] == "found"
    sent = json.loads(log[0].content)
    assert sent == {"text": "قال تعالى: ﴿إن الله مع الصابرين﴾", "ui_lang": "ar"}
    assert log[0].headers["user-agent"].startswith("basira-telegram-bot/")
    assert "x-eval-key" not in log[0].headers
    await c.aclose()


async def test_eval_key_header_only_when_set() -> None:
    log: list[httpx.Request] = []
    c = client({"/v1/check": "no_quotes"}, log, eval_key="k-123")
    await c.check("x")
    assert log[0].headers["x-eval-key"] == "k-123"
    await c.aclose()


@pytest.mark.parametrize(
    ("status", "fixture", "code"),
    [(413, "err_413", "text_too_long"), (422, "err_422", "invalid_input")],
)
async def test_error_envelope_is_surfaced(status: int, fixture: str, code: str) -> None:
    c = client({"/v1/check": (status, load(fixture))})
    with pytest.raises(ApiError) as e:
        await c.check("x")
    assert (e.value.status, e.value.code) == (status, code)
    assert e.value.message_ar == load(fixture)["error"]["message_ar"]


@pytest.mark.parametrize(("status", "code"), [(429, "rate_limited"), (503, "degraded")])
async def test_429_and_503(status: int, code: str) -> None:
    body = {"error": {"code": code, "message_ar": f"رسالة {code}", "message_en": "m"}}
    c = client({"/v1/check": (status, body)})
    with pytest.raises(ApiError) as e:
        await c.check("x")
    assert e.value.status == status and e.value.message_ar == f"رسالة {code}"


async def test_timeout_maps_to_api_timeout() -> None:
    def slow(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    c = client({"/v1/check": slow})
    with pytest.raises(ApiTimeoutError):
        await c.check("x")


async def test_connection_error_maps_to_unreachable() -> None:
    def down(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    c = client({"/v1/check": down})
    with pytest.raises(UnreachableError):
        await c.check("x")


@pytest.mark.parametrize(
    "response",
    [httpx.Response(502, text="<html>Bad Gateway</html>"), httpx.Response(500, json={"detail": "x"})],
)
async def test_non_envelope_errors_are_unreachable(response: httpx.Response) -> None:
    c = client({"/v1/check": lambda _: response})
    with pytest.raises(UnreachableError):
        await c.check("x")


async def test_image_is_multipart_field_image() -> None:
    log: list[httpx.Request] = []
    c = client({"/v1/check/image": "image_hadith"}, log)
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    body = await c.check_image(png, "image/png")
    assert body["quotes"][0]["review_reason"] == "image_unconfirmed"
    req = log[0]
    assert req.headers["content-type"].startswith("multipart/form-data")
    assert b'name="image"; filename="image.png"' in req.content and png in req.content
    assert b'name="ui_lang"' in req.content


async def test_sources_list_and_messages_cache() -> None:
    log: list[httpx.Request] = []
    c = client({"/v1/sources": "sources"}, log)
    assert {s["id"] for s in await c.sources()} >= {"tanzil_uthmani", "ohd", "hadeethenc_ar"}
    a = await c.messages("ar")
    b = await c.messages("ar")
    assert a is b and sum(r.url.path == "/v1/messages/ar" for r in log) == 1


async def test_no_redirects_followed() -> None:
    c = client({"/v1/check": lambda _: httpx.Response(302, headers={"location": "https://evil.test/"})})
    with pytest.raises(UnreachableError):
        await c.check("x")
