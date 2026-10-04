"""Developer-gate REST contract (docs/API.md): /v1/sources, /v1/rules, /v1/guard, determinism header,
OpenAPI examples for the four states. Uses the shared `client` fixture (fixture index, mock provider)."""

from __future__ import annotations

import json

from httpx import AsyncClient

from app.config import Settings
from app.messages import scan_forbidden
from app.schemas import openapi_examples

HEADER = "x-basira-determinism-hash"


async def test_sources_match_manifest_including_sha256(client: AsyncClient, test_settings: Settings) -> None:
    r = await client.get("/v1/sources")
    assert r.status_code == 200
    body = r.json()
    manifest = json.loads(test_settings.manifest_path.read_text(encoding="utf-8"))
    assert [s["id"] for s in body] == [s["id"] for s in manifest["sources"]]
    by_id = {s["id"]: s for s in body}
    for src in manifest["sources"]:
        got = by_id[src["id"]]
        assert got["sha256"] == str(src.get("sha256") or "")
        assert got["license"] == src["license"] and got["license_url"] == src["license_url"]
        assert got["version"] == str(src.get("version") or src.get("commit") or "")
        assert got["in_repo"] is False
    assert by_id["tanzil_uthmani"]["records"] > 0  # live counts from the loaded store


async def test_determinism_header_equals_body_field(client: AsyncClient) -> None:
    r = await client.post("/v1/check", json={"text": "قال تعالى: ﴿إن الله مع الصابرين﴾", "ui_lang": "ar"})
    assert r.status_code == 200
    assert HEADER in r.headers and r.headers[HEADER] == r.json()["determinism_hash"]
    assert len(r.headers[HEADER]) == 64
    r2 = await client.post("/v1/check", json={"text": "قال تعالى: ﴿إن الله مع الصابرين﴾", "ui_lang": "ar"})
    assert r2.headers[HEADER] == r.headers[HEADER]
    assert r.headers["cache-control"] == "no-store"


async def test_determinism_header_absent_on_errors(client: AsyncClient) -> None:
    r = await client.post("/v1/check", json={"text": "   "})
    assert r.status_code == 422 and HEADER not in r.headers
    assert r.json()["error"]["code"] == "invalid_input"


async def test_rules_endpoint(client: AsyncClient) -> None:
    en = (await client.get("/v1/rules")).json()
    ar = (await client.get("/v1/rules", params={"ui_lang": "ar"})).json()
    assert en["ui_lang"] == "en" and ar["ui_lang"] == "ar"
    assert en["states"] == ["found", "partial_match", "needs_review", "not_found"]
    assert (
        en["source"] == "SAFETY.md"
        and len(en["safety_sha256"]) == 64
        and en["safety_sha256"] == ar["safety_sha256"]
    )
    assert "never a verdict" in en["text"].lower() or "not a verdict" in en["text"].lower()
    assert scan_forbidden(en["text"]) == [] and scan_forbidden(ar["text"]) == []
    other = (await client.get("/v1/rules", params={"ui_lang": "fr"})).json()
    assert other["ui_lang"] == "ar"  # unknown → Arabic default, never an error


async def test_guard_endpoint_flagged(client: AsyncClient) -> None:
    r = await client.post(
        "/v1/guard",
        json={"answer": "قال تعالى: ﴿إن الله مع الصابرين﴾ وقال ﷺ: «الدين المعاملة»", "ui_lang": "ar"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "flagged"
    assert body["counts"] == {
        "quotes": 2,
        "found": 1,
        "flagged": 1,
        "by_status": {"found": 1, "not_found": 1},
    }
    assert len(body["flagged_quote_ids"]) == 1
    assert body["summary_ar"] and body["summary_en"]
    assert scan_forbidden(body["summary_ar"]) == [] and scan_forbidden(body["summary_en"]) == []
    assert r.headers[HEADER] == body["determinism_hash"]


async def test_guard_endpoint_clear_and_no_quotes(client: AsyncClient) -> None:
    clear = (await client.post("/v1/guard", json={"answer": "قال تعالى: ﴿إن الله مع الصابرين﴾"})).json()
    assert clear["verdict"] == "clear" and clear["counts"]["flagged"] == 0
    none = (await client.post("/v1/guard", json={"answer": "اليوم طقس جميل", "ui_lang": "en"})).json()
    assert none["verdict"] == "no_quotes" and none["quotes"] == []


async def test_guard_endpoint_errors_use_envelope(client: AsyncClient, test_settings: Settings) -> None:
    r = await client.post("/v1/guard", json={"answer": "   "})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_input"
    r = await client.post("/v1/guard", json={"answer": "ا" * 5001})
    assert r.status_code == 413 and r.json()["error"]["code"] == "text_too_long"
    assert str(test_settings.max_text_chars) in r.json()["error"]["message_en"]
    r = await client.post("/v1/guard", json={})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_input"


async def test_openapi_has_real_examples_for_four_states(client: AsyncClient) -> None:
    ex = openapi_examples()
    assert set(ex) == {"found", "partial_match", "needs_review", "not_found"}
    for state, pair in ex.items():
        resp = pair["response"]
        assert resp["quotes"][0]["status"] == state
        assert len(resp["determinism_hash"]) == 64
        for q in resp["quotes"]:
            for m in q["matches"]:
                assert m["source_text"] and "…" not in m["source_text"]  # verbatim, never trimmed
    spec = (await client.get("/openapi.json")).json()
    req_schema = spec["components"]["schemas"]["CheckRequest"]
    resp_schema = spec["components"]["schemas"]["CheckResponse"]
    assert len(req_schema["examples"]) == 4 and len(resp_schema["examples"]) == 4
    assert [e["quotes"][0]["status"] for e in resp_schema["examples"]] == [
        "found",
        "partial_match",
        "needs_review",
        "not_found",
    ]
    paths = spec["paths"]
    assert {
        "/v1/check",
        "/v1/guard",
        "/v1/rules",
        "/v1/sources",
        "/v1/receipt",
        "/v/{token}",
        "/v1/messages/{lang}",
        "/health",
    } <= set(paths)
    assert "examples" in spec["components"]["schemas"]["GuardRequest"]


async def test_openapi_examples_are_lexicon_clean() -> None:
    """Everything we author inside the examples (message keys render later; here: labels/notices) is clean."""
    for pair in openapi_examples().values():
        for q in pair["response"]["quotes"]:
            for m in q["matches"]:
                assert scan_forbidden(m["ref_label_ar"]) == [] and scan_forbidden(m["ref_label_en"]) == []


# --------------------------------------------------------------------------- verification receipt (E-052)

RECEIPT_TEXT = "قال تعالى: ﴿إن الله مع الصابرين﴾ وقال ﷺ: «طلب العلم فريضة على كل مسلم ومسلمة»"


async def test_receipt_round_trip_verified_now_then_stale(client: AsyncClient) -> None:
    issued = await client.post("/v1/receipt", json={"text": RECEIPT_TEXT, "ui_lang": "ar"})
    assert issued.status_code == 200
    assert issued.headers["cache-control"] == "no-store"
    body = issued.json()
    h = body["determinism_hash"]
    assert issued.headers[HEADER] == h and len(h) == 64
    assert body["receipt_id"] == h[:16]
    assert body["summary"]["quotes"] == 2 and sum(body["summary"]["by_status"].values()) == 2
    assert body["summary"]["by_status"]["found"] == 1 and len(body["summary"]["by_status"]) == 2
    assert body["index_sha256"] and body["corpus"] and body["issued_at"].endswith("Z")
    assert body["verified_now"] is None and body["stale"] is None  # issue-time: nothing presented yet
    token = body["token"]
    assert token and all(c.isalnum() or c in "-_" for c in token)  # base64url, no padding, URL-safe

    again = await client.get(f"/v/{token}", params={"h": h})
    assert again.status_code == 200
    assert again.headers["cache-control"] == "no-store" and again.headers[HEADER] == h
    v = again.json()
    assert v["verified_now"] is True and v["stale"] is False and v["presented_hash"] == h
    assert v["determinism_hash"] == h and v["receipt_id"] == body["receipt_id"] and v["token"] == token
    assert [q["status"] for q in v["quotes"]] == [q["status"] for q in body["quotes"]]

    wrong = await client.get(f"/v/{token}", params={"h": "0" * 64})
    assert wrong.status_code == 200
    w = wrong.json()
    assert w["stale"] is True and w["verified_now"] is False and w["determinism_hash"] == h

    bare = await client.get(f"/v/{token}")  # no hash presented: a plain re-run, neither claim is made
    assert bare.status_code == 200
    assert bare.json()["verified_now"] is False and bare.json()["stale"] is False


async def test_receipt_token_is_the_input_and_nothing_else(client: AsyncClient) -> None:
    import base64  # noqa: PLC0415
    import zlib  # noqa: PLC0415

    body = (await client.post("/v1/receipt", json={"text": RECEIPT_TEXT, "ui_lang": "en"})).json()
    token = body["token"]
    raw = zlib.decompress(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
    assert json.loads(raw) == {"v": 1, "t": RECEIPT_TEXT, "l": "en"}


async def test_receipt_invalid_tokens_are_a_clean_400(client: AsyncClient) -> None:
    import base64  # noqa: PLC0415
    import zlib  # noqa: PLC0415

    for bad in ("not-a-token", "AAAA", base64.urlsafe_b64encode(zlib.compress(b"[1,2]")).decode()):
        r = await client.get(f"/v/{bad}")
        assert r.status_code == 400, bad
        err = r.json()["error"]
        assert err["code"] == "receipt_invalid"
        assert scan_forbidden(err["message_ar"]) == [] and scan_forbidden(err["message_en"]) == []
    # a well-formed token whose text is blank is invalid input, not a receipt problem
    blank = base64.urlsafe_b64encode(
        zlib.compress(json.dumps({"v": 1, "t": "  ", "l": "ar"}).encode())
    ).decode()
    assert (await client.get(f"/v/{blank}")).status_code == 422
    # version mismatch
    v2 = base64.urlsafe_b64encode(zlib.compress(json.dumps({"v": 2, "t": "x", "l": "ar"}).encode())).decode()
    assert (await client.get(f"/v/{v2}")).json()["error"]["code"] == "receipt_invalid"


async def test_receipt_oversized_is_413_before_decoding(client: AsyncClient, test_settings: Settings) -> None:
    from app.devgate import encode_receipt_token  # noqa: PLC0415

    r = await client.post("/v1/receipt", json={"text": "ا" * (test_settings.max_text_chars + 1)})
    assert r.status_code == 413 and r.json()["error"]["code"] == "text_too_long"
    # a token that decodes to too much text (compresses well → short token) is still refused: bounded inflate
    bomb = encode_receipt_token("ا" * (test_settings.max_text_chars * 8), "ar")
    r = await client.get(f"/v/{bomb}")
    assert r.status_code in (400, 413) and r.json()["error"]["code"] in ("receipt_invalid", "text_too_long")
    # a token longer than any legitimate one → 413 without touching zlib
    r = await client.get("/v/" + "A" * (test_settings.max_text_chars * 6))
    assert r.status_code == 413


async def test_receipt_matches_check_byte_for_byte(client: AsyncClient) -> None:
    check = (await client.post("/v1/check", json={"text": RECEIPT_TEXT, "ui_lang": "ar"})).json()
    rec = (await client.post("/v1/receipt", json={"text": RECEIPT_TEXT, "ui_lang": "ar"})).json()
    assert rec["determinism_hash"] == check["determinism_hash"]
    assert [q["status"] for q in rec["quotes"]] == [q["status"] for q in check["quotes"]]
    assert rec["quotes"][0]["matches"][0]["source_text"] == check["quotes"][0]["matches"][0]["source_text"]
