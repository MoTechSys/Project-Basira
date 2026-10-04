"""MCP server contract (docs/INTEGRATIONS.md §3.1): tools, verdicts, determinism, limits, opt-in flag.

Runs the real MCP client (`mcp.client`) against the FastAPI app in-process over httpx's ASGI transport —
the same wire protocol a Claude/ChatGPT/IDE client speaks. Uses the fixture index (conftest).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app
from app.mcp_server import TOOL_NAMES
from app.messages import scan_forbidden

pytest.importorskip("mcp.client.session", reason="optional extra: pip install -e 'backend[mcp]'")
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

SessionFactory = Callable[[], AbstractAsyncContextManager[ClientSession]]
AppFactory = Callable[[], AbstractAsyncContextManager[tuple[Any, AsyncClient]]]


@asynccontextmanager
async def running_app(test_settings: Settings) -> AsyncIterator[tuple[Any, AsyncClient]]:
    """App with BASIRA_MCP=1, lifespan entered in the *calling task* (anyio cancel scopes are task-bound,
    so this cannot be a pytest-asyncio async fixture)."""
    cfg = replace(test_settings, mcp_enabled=True)
    app = create_app(cfg)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as hc,
    ):
        yield app, hc


@asynccontextmanager
async def mcp_session(hc: AsyncClient) -> AsyncIterator[ClientSession]:
    async with (
        streamable_http_client("http://test/mcp", http_client=hc) as (r, w, *_),
        ClientSession(r, w) as s,
    ):
        await s.initialize()
        yield s


@asynccontextmanager
async def running_session(test_settings: Settings) -> AsyncIterator[ClientSession]:
    async with running_app(test_settings) as (_, hc), mcp_session(hc) as s:
        yield s


@pytest.fixture
def mcp_app(test_settings: Settings) -> AppFactory:
    return lambda: running_app(test_settings)


@pytest.fixture
def session(test_settings: Settings) -> SessionFactory:
    return lambda: running_session(test_settings)


async def _call(s: ClientSession, name: str, args: dict[str, Any]) -> dict[str, Any]:
    res = await s.call_tool(name, args)
    assert not res.is_error, res.content
    assert isinstance(res.structured_content, dict)
    return res.structured_content


async def _call_err(s: ClientSession, name: str, args: dict[str, Any]) -> dict[str, Any]:
    res = await s.call_tool(name, args)
    assert res.is_error
    text = res.content[0].text  # type: ignore[union-attr]
    start = text.find("{")
    body: dict[str, Any] = json.loads(text[start:])
    return body


# --------------------------------------------------------------------------- discovery


async def test_tools_list_has_the_six_tools(session: SessionFactory) -> None:
    async with session() as s:
        tools = await s.list_tools()
        names = [t.name for t in tools.tools]
        assert names == list(TOOL_NAMES) and len(names) == 6 and "issue_receipt" in names
        for t in tools.tools:
            assert t.description and len(t.description) > 80, t.name
            assert scan_forbidden(t.description) == [], (t.name, scan_forbidden(t.description))


async def test_server_instructions_are_grounding_rules(mcp_app: AppFactory) -> None:
    async with (
        mcp_app() as (_, hc),
        streamable_http_client("http://test/mcp", http_client=hc) as (r, w, *_),
        ClientSession(r, w) as s,
    ):
        init = await s.initialize()
        assert init.server_info.name == "basira"
        assert init.instructions and "found" in init.instructions and "not_found" in init.instructions
        assert scan_forbidden(init.instructions) == []


# --------------------------------------------------------------------------- verify_text


async def test_verify_text_found_2_153(session: SessionFactory) -> None:
    async with session() as s:
        out = await _call(s, "verify_text", {"text": "قال تعالى: إن الله مع الصابرين", "ui_lang": "ar"})
        assert len(out["quotes"]) == 1
        q = out["quotes"][0]
        assert q["status"] == "found" and q["kind"] == "quran"
        m = q["matches"][0]
        assert m["corpus"] == "tanzil" and m["ref"] == {"surah": 2, "ayah": 153}
        assert m["source_text"] and m["source_url"].startswith("https://")
        assert "البقرة" in m["ref_label"]
        assert isinstance(out["determinism_hash"], str) and len(out["determinism_hash"]) == 64
        assert out["disclaimer"] and out["transparency"]


async def test_verify_text_foreign_material_needs_review(session: SessionFactory) -> None:
    async with session() as s:
        out = await _call(s, "verify_text", {"text": "قال تعالى: ﴿قل هو HELLO الله أحد﴾.", "ui_lang": "en"})
        q = out["quotes"][0]
        assert q["status"] == "needs_review" and q["review_reason"] == "foreign_material"
        assert "foreign_material" in q["notice_keys"]
        assert any("not" in n.lower() or "remove" in n.lower() for n in q["notices"]), q["notices"]
        assert "Al-Ikhlas" in q["matches"][0]["ref_label"]


async def test_verify_text_only_source_text_is_religious(session: SessionFactory) -> None:
    async with session() as s:
        """Every string we author (status_message, notices, disclaimer) is forbidden-lexicon clean."""
        out = await _call(
            s, "verify_text", {"text": "قال ﷺ: «إنما الأعمال بالنيات» رواه مسلم", "ui_lang": "ar"}
        )
        q = out["quotes"][0]
        assert q["claimed_source_mismatch"] is True
        for authored in [q["status_message"], *q["notices"], out["disclaimer"], out["transparency"]]:
            assert scan_forbidden(authored) == [], authored


async def test_verify_text_determinism_hash_stable(session: SessionFactory) -> None:
    async with session() as s:
        a = await _call(s, "verify_text", {"text": "قال تعالى: ﴿إن الله مع الصابرين﴾"})
        b = await _call(s, "verify_text", {"text": "قال تعالى: ﴿إن الله مع الصابرين﴾"})
        assert a["determinism_hash"] == b["determinism_hash"]
        assert a["quotes"] == b["quotes"]
        c = await _call(s, "verify_text", {"text": "قال تعالى: ﴿إن الله مع الصابرين﴾ [البقرة: 255]"})
        assert c["determinism_hash"] != a["determinism_hash"]  # a different input → a different hash
        assert c["quotes"][0]["claimed_source_mismatch"] is True


async def test_verify_text_too_long_is_a_clean_error(
    session: SessionFactory, test_settings: Settings
) -> None:
    async with session() as s:
        body = await _call_err(s, "verify_text", {"text": "ا" * (test_settings.max_text_chars + 1)})
        assert body["code"] == "text_too_long"
        assert str(test_settings.max_text_chars) in body["message_en"] and body["message_ar"]
        assert "Traceback" not in json.dumps(body)


async def test_verify_text_blank_is_invalid_input(session: SessionFactory) -> None:
    async with session() as s:
        body = await _call_err(s, "verify_text", {"text": "   "})
        assert body["code"] == "invalid_input"


# --------------------------------------------------------------------------- verify_quote


async def test_verify_quote_matching_claim(session: SessionFactory) -> None:
    async with session() as s:
        out = await _call(s, "verify_quote", {"text": "إن الله مع الصابرين", "claimed_ref": "2:153"})
        assert out["status"] == "found" and out["claimed_source_mismatch"] is False
        assert out["quote"]["matches"][0]["ref"] == {"surah": 2, "ayah": 153}


async def test_verify_quote_mismatching_claim(session: SessionFactory) -> None:
    async with session() as s:
        out = await _call(s, "verify_quote", {"text": "إن الله مع الصابرين", "claimed_ref": "2:255"})
        assert out["status"] == "found" and out["claimed_source_mismatch"] is True  # status unaffected (I8)
        assert "claimed_ayah_mismatch" in out["quote"]["notice_keys"]


async def test_verify_quote_hadith_book_claim(session: SessionFactory) -> None:
    async with session() as s:
        ok = await _call(s, "verify_quote", {"text": "إنما الأعمال بالنيات", "claimed_ref": "البخاري 1"})
        assert ok["status"] == "found" and ok["claimed_source_mismatch"] is False
        bad = await _call(s, "verify_quote", {"text": "إنما الأعمال بالنيات", "claimed_ref": "رواه مسلم"})
        assert bad["status"] == "found" and bad["claimed_source_mismatch"] is True


async def test_verify_quote_without_claim_and_not_found(session: SessionFactory) -> None:
    async with session() as s:
        out = await _call(s, "verify_quote", {"text": "الدين المعاملة"})
        assert out["status"] == "not_found" and out["claimed_ref"] is None
        body = await _call_err(s, "verify_quote", {"text": "إن الله مع الصابرين", "claimed_ref": "<script>"})
        assert body["code"] == "invalid_input"


# --------------------------------------------------------------------------- guard / sources / rules


async def test_guard_answer_tool(session: SessionFactory) -> None:
    async with session() as s:
        out = await _call(s, "guard_answer", {"answer": "اليوم طقس جميل", "ui_lang": "en"})
        assert out["verdict"] == "no_quotes" and out["counts"]["quotes"] == 0
        out = await _call(
            s, "guard_answer", {"answer": "قال تعالى: ﴿إن الله مع الصابرين﴾ وقال ﷺ: «الدين المعاملة»"}
        )
        assert out["verdict"] == "flagged" and out["counts"] == {
            "quotes": 2,
            "found": 1,
            "flagged": 1,
            "by_status": {"found": 1, "not_found": 1},
        }


async def test_list_sources_matches_manifest(session: SessionFactory, test_settings: Settings) -> None:
    async with session() as s:
        out = await _call(s, "list_sources", {})
        manifest = json.loads(test_settings.manifest_path.read_text(encoding="utf-8"))
        assert [s["id"] for s in out["sources"]] == [s["id"] for s in manifest["sources"]]
        by_id = {s["id"]: s for s in out["sources"]}
        assert by_id["tanzil_uthmani"]["sha256"] == manifest["sources"][0]["sha256"]
        assert by_id["tanzil_uthmani"]["license"].startswith("CC BY")
        assert by_id["ohd"]["books"] and by_id["ohd"]["books"][0]["key"] == "sahih_al-bukhari"


async def test_grounding_rules_tool(session: SessionFactory) -> None:
    async with session() as s:
        en = await _call(s, "grounding_rules", {"ui_lang": "en"})
        ar = await _call(s, "grounding_rules", {"ui_lang": "ar"})
        assert en["states"] == ar["states"] == ["found", "partial_match", "needs_review", "not_found"]
        assert en["source"] == "SAFETY.md" and len(en["safety_sha256"]) == 64
        assert "not_found" in en["text"] and "لم يوجد" in ar["text"]
        assert scan_forbidden(en["text"]) == [] and scan_forbidden(ar["text"]) == []


# --------------------------------------------------------------------------- opt-in & isolation


async def test_mcp_disabled_by_default_404(client: AsyncClient) -> None:
    r = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 404
    r = await client.get("/mcp")
    assert r.status_code == 404


async def test_mcp_enabled_rest_still_works(mcp_app: AppFactory) -> None:
    async with mcp_app() as (app, hc):
        r = await hc.get("/health")
        assert r.status_code == 200
        r = await hc.post("/v1/check", json={"text": "قال تعالى: ﴿إن الله مع الصابرين﴾"})
        assert r.status_code == 200 and r.headers["x-basira-determinism-hash"] == r.json()["determinism_hash"]
        assert app.state.pipeline is not None  # one pipeline object shared by REST and MCP


async def test_mcp_and_rest_give_byte_equal_verdicts(mcp_app: AppFactory) -> None:
    text = "قال تعالى: ﴿قل هو HELLO الله أحد﴾."
    async with mcp_app() as (_, hc):
        rest = (await hc.post("/v1/check", json={"text": text, "ui_lang": "ar"})).json()
        async with mcp_session(hc) as s:
            mcp = await _call(s, "verify_text", {"text": text, "ui_lang": "ar"})
    assert mcp["determinism_hash"] == rest["determinism_hash"]
    assert [q["status"] for q in mcp["quotes"]] == [q["status"] for q in rest["quotes"]]
    assert mcp["quotes"][0]["matches"][0]["source_text"] == rest["quotes"][0]["matches"][0]["source_text"]


async def test_mcp_does_not_shadow_spa_fallback(test_settings: Settings, tmp_path: Path) -> None:
    """Regression (2026-10-03): ``app.mount("/", mcp_app)`` swallowed the SPA catch-all, so with
    BASIRA_MCP=1 the site root and every client route answered 404. MCP and the static frontend must coexist."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html><body>spa</body></html>", encoding="utf-8")
    cfg = replace(test_settings, mcp_enabled=True, static_dir=tmp_path)
    app = create_app(cfg)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as hc,
    ):
        for path in ("/", "/settings", "/check", "/trust"):
            r = await hc.get(path)
            assert r.status_code == 200 and "spa" in r.text, path
        r = await hc.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"accept": "application/json, text/event-stream", "content-type": "application/json"},
        )
        assert r.status_code == 200
        assert {t["name"] for t in r.json()["result"]["tools"]} == set(TOOL_NAMES)
        assert (await hc.get("/v1/models")).status_code == 200


# --------------------------------------------------------------------------- issue_receipt (E-052)


async def test_issue_receipt_tool_equals_rest_receipt_and_reverifies(mcp_app: AppFactory) -> None:
    text = "قال تعالى: ﴿إن الله مع الصابرين﴾"
    async with mcp_app() as (_, hc):
        rest = (await hc.post("/v1/receipt", json={"text": text, "ui_lang": "ar"})).json()
        async with mcp_session(hc) as s:
            out = await _call(s, "issue_receipt", {"text": text, "ui_lang": "ar"})
        # same core → same token, same hash, same receipt_id (issued_at may differ by a second)
        assert out["token"] == rest["token"] and out["determinism_hash"] == rest["determinism_hash"]
        assert out["receipt_id"] == rest["receipt_id"] == out["determinism_hash"][:16]
        assert out["summary"] == rest["summary"] and out["index_sha256"] == rest["index_sha256"]
        again = await hc.get(f"/v/{out['token']}", params={"h": out["determinism_hash"]})
        assert again.status_code == 200 and again.json()["verified_now"] is True


async def test_issue_receipt_tool_errors_use_the_envelope(session: SessionFactory) -> None:
    async with session() as s:
        body = await _call_err(s, "issue_receipt", {"text": "   "})
        assert body["code"] == "invalid_input" and body["message_ar"] and body["message_en"]
