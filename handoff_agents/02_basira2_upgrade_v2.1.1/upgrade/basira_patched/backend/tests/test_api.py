"""HTTP contract (BUILD_SPEC §4): envelopes, limits, health gate, sources, rate limit + bypass."""

from __future__ import annotations

import io
from dataclasses import replace

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.csp import stamp_nonce
from app.main import RateLimiter, create_app


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


async def test_image_endpoint_mock_ocr(client: AsyncClient) -> None:
    files = {"image": ("q.png", io.BytesIO(b"\x89PNG fake"), "image/png")}
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
    r = await client.post("/v1/check/image", files={"image": ("a.png", io.BytesIO(b"x"), "image/png")})
    assert r.status_code == 200 and r.json()["extraction_degraded"] is True and r.json()["quotes"] == []


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


# ---------------------------------------------------------------- CSP nonce for inline scripts (E-036)


def test_stamp_nonce_only_inline_scripts() -> None:
    html = (
        "<script>document.documentElement.dataset.theme='dark'</script>"
        '<script type="application/ld+json">{}</script>'
        '<script type="module" src="/assets/index.js"></script>'
        '<script nonce="keep">x()</script>'
        "<p>script</p>"
    )
    out = stamp_nonce(html, "N0NCE")
    assert out.count('nonce="N0NCE"') == 2, out
    assert '<script type="module" src="/assets/index.js">' in out  # external untouched
    assert 'nonce="keep"' in out and out.count("nonce=") == 3
    assert stamp_nonce(html, "") == html


async def test_spa_index_served_with_matching_nonce(test_settings, tmp_path) -> None:  # type: ignore[no-untyped-def]
    static = tmp_path / "dist"
    (static / "assets").mkdir(parents=True)
    (static / "assets" / "a.js").write_text("1")
    (static / "index.html").write_text(
        '<!doctype html><html><head><script>theme()</script><script type="application/ld+json">{}</script>'
        '</head><body><div id="root"></div><script type="module" src="/assets/a.js"></script></body></html>',
        encoding="utf-8",
    )
    app: FastAPI = create_app(replace(test_settings, static_dir=static))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/")
        assert r.status_code == 200 and "text/html" in r.headers["content-type"]
        csp = r.headers["content-security-policy"]
        nonce = csp.split("'nonce-", 1)[1].split("'", 1)[0]
        assert len(nonce) >= 16 and "'unsafe-inline'" not in csp.split("script-src", 1)[1].split(";", 1)[0]
        assert r.text.count(f'nonce="{nonce}"') == 2  # both inline scripts, external one untouched
        r2 = await c.get("/some/client/route")
        assert r2.status_code == 200 and "nonce=" in r2.text
        n2 = r2.headers["content-security-policy"].split("'nonce-", 1)[1].split("'", 1)[0]
        assert n2 != nonce  # fresh nonce per request
        r3 = await c.get("/assets/a.js")
        assert r3.status_code == 200 and r3.text == "1"  # StaticFiles mount, no HTML/nonce
