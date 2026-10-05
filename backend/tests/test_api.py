"""HTTP contract (docs/API.md): envelopes, limits, health gate, sources, rate limit + bypass."""

from __future__ import annotations

import base64
import hashlib
import io
from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.main import RateLimiter, _inline_script_hashes, client_identity, create_app, parse_trusted_proxies


async def test_health_ok_after_lifespan(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["corpus_loaded"] is True
    assert body["counts"]["tanzil"] > 0 and body["providers"] == {"llm": "mock", "vision": "mock"}
    assert body["corpus"]["tanzil"] == "1.1"


async def test_health_503_before_load(test_settings) -> None:  # type: ignore[no-untyped-def]
    app: FastAPI = create_app(test_settings)  # lifespan NOT entered
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/health")
        assert r.status_code == 503 and r.json()["status"] == "loading"
        r = await c.post("/v1/check", json={"text": "﴿إن الله مع الصابرين﴾"})
        assert r.status_code == 503 and r.json()["error"]["code"] == "degraded"


async def test_check_contract(client: AsyncClient) -> None:
    r = await client.post("/v1/check", json={"text": "قال تعالى: ﴿إن الله مع الصابرين﴾", "ui_lang": "ar"})
    assert r.status_code == 200
    body = r.json()
    assert body["disclaimer_key"] == "footer" and body["transparency_key"] == "transparency_notice"
    assert body["extraction_provider"] == "mock" and body["extraction_degraded"] is False
    q = body["quotes"][0]
    assert q["status"] == "found" and q["matches"][0]["corpus"] == "tanzil"
    assert set(body["timings_ms"]) == {"extract", "retrieve", "match", "total"}
    assert "request_id" in body


async def test_validation_errors_use_envelope(client: AsyncClient) -> None:
    r = await client.post("/v1/check", json={"text": ""})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "invalid_input" and err["message_ar"] and err["message_en"]
    r = await client.post("/v1/check", json={"text": "   "})
    assert r.status_code == 422
    r = await client.post("/v1/check", json={"text": "x" * 5001})
    assert r.status_code == 413 and r.json()["error"]["code"] == "text_too_long"
    r = await client.post("/v1/check", json={"text": "a", "ui_lang": "fr"})
    assert r.status_code == 422


async def test_sources_from_manifest(client: AsyncClient) -> None:
    r = await client.get("/v1/sources")
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert {"tanzil_uthmani", "tanzil_simple_clean", "ohd", "hadeethenc_ar"} <= ids
    for s in r.json():
        assert s["license"] and s["url"] and s["in_repo"] is False


async def test_messages_endpoint(client: AsyncClient) -> None:
    r = await client.get("/v1/messages/ar")
    assert r.status_code == 200 and "status" in r.json() and "$comment" not in r.json()
    r = await client.get("/v1/messages/xx")
    assert r.status_code == 422


PNG_SIG = b"\x89PNG\r\n\x1a\n"


async def test_image_endpoint_mock_ocr(client: AsyncClient) -> None:
    files = {"image": ("q.png", io.BytesIO(PNG_SIG + b"fake body"), "image/png")}
    r = await client.post("/v1/check/image", files=files, data={"ui_lang": "ar"})
    assert r.status_code == 200
    body = r.json()
    assert body["quotes"] and body["quotes"][0]["source_modality"] == "image"
    assert "image_extracted" in body["quotes"][0]["notice_keys"]
    assert body["quotes"][0]["status"] == "needs_review"
    assert "ocr_mock" in body["quotes"][0]["notice_keys"]  # mock vision must say so
    assert body["ocr_text"]  # extracted text is returned so the user can verify it


async def test_image_endpoint_rejects_bad_mime_and_degrades_on_ocr_failure(
    client: AsyncClient, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    r = await client.post(
        "/v1/check/image", files={"image": ("a.pdf", io.BytesIO(b"%PDF"), "application/pdf")}
    )
    assert r.status_code == 422
    monkeypatch.setenv("BASIRA_MOCK_OCR_FAIL", "1")
    r = await client.post("/v1/check/image", files={"image": ("a.png", io.BytesIO(PNG_SIG), "image/png")})
    assert r.status_code == 200 and r.json()["extraction_degraded"] is True and r.json()["quotes"] == []


async def test_image_endpoint_sniffs_bytes_not_only_the_declared_mime(client: AsyncClient) -> None:
    """B12: text bytes labelled image/png are refused; a mislabelled JPEG is refused; real signatures pass."""
    r = await client.post("/v1/check/image", files={"image": ("a.png", io.BytesIO(b"x"), "image/png")})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_input"
    r = await client.post(
        "/v1/check/image", files={"image": ("a.png", io.BytesIO(b"\xff\xd8\xff\xe0JFIF"), "image/png")}
    )
    assert r.status_code == 422
    for sig, mime in (
        (PNG_SIG, "image/png"),
        (b"\xff\xd8\xff\xe0\x00\x10JFIF", "image/jpeg"),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp"),
    ):
        r = await client.post("/v1/check/image", files={"image": ("a", io.BytesIO(sig), mime)})
        assert r.status_code == 200, mime


def test_rate_limiter_window_and_bypass() -> None:
    rl = RateLimiter(3)
    assert all(rl.allow("ip", now=100.0 + i) for i in range(3))
    assert rl.allow("ip", now=104.0) is False
    assert rl.allow("other", now=104.0) is True
    assert rl.allow("ip", now=161.0) is True  # window slid
    assert RateLimiter(0).allow("x") is True


async def test_rate_limit_http_and_eval_key(test_settings) -> None:  # type: ignore[no-untyped-def]
    from dataclasses import replace  # noqa: PLC0415

    app = create_app(replace(test_settings, rate_limit_per_min=2))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c,
    ):
        payload = {"text": "﴿إن الله مع الصابرين﴾"}
        assert (await c.post("/v1/check", json=payload)).status_code == 200
        assert (await c.post("/v1/check", json=payload)).status_code == 200
        r = await c.post("/v1/check", json=payload)
        assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"
        r = await c.post("/v1/check", json=payload, headers={"X-Eval-Key": "test-eval-key"})
        assert r.status_code == 200
        r = await c.post("/v1/check", json=payload, headers={"X-Eval-Key": "wrong"})
        assert r.status_code == 429


def test_client_identity_ignores_forwarded_for_unless_peer_is_a_trusted_proxy() -> None:
    """B12: a client cannot mint rate-limit identities by sending X-Forwarded-For itself."""
    none = parse_trusted_proxies(())
    assert client_identity("203.0.113.9", "10.0.0.1, 198.51.100.7", none) == "203.0.113.9"
    lb = parse_trusted_proxies(("10.0.0.0/8", "127.0.0.1"))
    # peer is the load balancer → right-most untrusted hop is the client (spoofed left-most entries ignored)
    assert client_identity("10.0.0.1", "1.2.3.4, 203.0.113.9", lb) == "203.0.113.9"
    assert client_identity("10.0.0.1", "203.0.113.9, 10.0.0.2", lb) == "203.0.113.9"  # trusted hops skipped
    assert client_identity("10.0.0.1", None, lb) == "10.0.0.1"  # proxy without the header: the proxy
    assert client_identity("203.0.113.9", "1.2.3.4", lb) == "203.0.113.9"  # untrusted peer: header ignored
    assert client_identity("10.0.0.1", "garbage, 203.0.113.9", lb) == "203.0.113.9"
    assert parse_trusted_proxies(("not-an-ip", "10.0.0.0/8")) == parse_trusted_proxies(("10.0.0.0/8",))


async def test_rate_limit_key_is_not_spoofable_by_default(test_settings) -> None:  # type: ignore[no-untyped-def]
    from dataclasses import replace  # noqa: PLC0415

    app = create_app(replace(test_settings, rate_limit_per_min=1))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c,
    ):
        payload = {"text": "﴿إن الله مع الصابرين﴾"}
        assert (await c.post("/v1/check", json=payload)).status_code == 200
        # a rotating X-Forwarded-For no longer buys a fresh quota (B12)
        for i in range(3):
            r = await c.post("/v1/check", json=payload, headers={"X-Forwarded-For": f"203.0.113.{i}"})
            assert r.status_code == 429


async def test_cors_preflight(client: AsyncClient) -> None:
    r = await client.options(
        "/v1/check",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-eval-key",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


async def test_security_headers_present(client) -> None:  # type: ignore[no-untyped-def]
    r = await client.get("/health")
    for h in (
        "x-content-type-options",
        "x-frame-options",
        "referrer-policy",
        "permissions-policy",
        "content-security-policy",
        "cross-origin-opener-policy",
    ):
        assert h in r.headers, h
    assert r.headers["x-frame-options"] == "DENY"
    assert r.json()["index_sha256"]


def test_csp_hashes_cover_only_executable_inline_scripts(tmp_path: Path) -> None:
    """E-041: the theme pre-paint script gets a sha256 token; JSON-LD (data) and external scripts do not."""
    theme = "(function(){try{var t=localStorage.getItem('x')}catch(e){}})();"
    html = (
        "<html><head>"
        '<script type="application/ld+json">{"@context":"https://schema.org"}</script>'
        f"<script>{theme}</script>"
        '<script type="module" src="/assets/index.js"></script>'
        "</head></html>"
    )
    (tmp_path / "index.html").write_text(html, encoding="utf-8")
    hashes = _inline_script_hashes(tmp_path)
    expected = "sha256-" + base64.b64encode(hashlib.sha256(theme.encode()).digest()).decode()
    assert hashes == [expected]
    assert _inline_script_hashes(None) == [] and _inline_script_hashes(tmp_path / "missing") == []
