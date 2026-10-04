"""MCP server — Basira's verification tools over Streamable HTTP at ``/mcp`` (docs/INTEGRATIONS.md §3.1).

Enabled with ``BASIRA_MCP=1``. Mounted inside the FastAPI process; every tool calls the **same**
``Pipeline`` instance the REST routes use (``app.state.pipeline``) — no second index load (E-038).

Tools (names are a contract; descriptions are written for models):
    verify_text(text, ui_lang)            every quotation in a text → compact verdicts + determinism_hash
    verify_quote(text, claimed_ref, ui_lang) one quotation with an optional claimed reference
    guard_answer(answer, ui_lang)         chatbot answer → clear | flagged | no_quotes + fixed summaries
    list_sources()                        provenance: sources, versions, licences, sha256
    grounding_rules(ui_lang)              fixed instructions (the four states, the red lines)
    issue_receipt(text, ui_lang)          stateless verification receipt: verdicts + token (= the input)

Errors: inputs are validated by the shared core; a problem becomes a tool error with the API's own
``{code, message_ar, message_en}`` envelope as text — no stack traces, no internals, no user text.
Complements retrieval MCP servers (mcp.islamiccontent.org): they fetch text; Basira checks text.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from mcp.server.mcpserver.exceptions import ToolError
from starlette.applications import Starlette
from starlette.routing import Route

from app import __version__
from app.config import Settings
from app.devgate import DevGateError, grounding_rules, sources_info
from app.devgate import issue_receipt as _issue_receipt
from app.devgate import verify_quote as _verify_quote
from app.devgate import verify_text as _verify_text
from app.guard import guard_answer as _guard_answer
from app.messages import load_messages
from app.pipeline import Pipeline
from app.snapshot import LAST_BOOT

log = logging.getLogger("basira.mcp")
MCP_PATH = "/mcp"
TOOL_NAMES: tuple[str, ...] = (
    "verify_text",
    "verify_quote",
    "guard_answer",
    "list_sources",
    "grounding_rules",
    "issue_receipt",
)


class ToolInputError(ToolError):
    """Deliberate tool error: the SDK forwards its message to the client as ``isError=true``."""


def _envelope(code: str, settings: Settings, **vars: Any) -> str:
    ar = load_messages(settings.messages_dir, "ar")
    en = load_messages(settings.messages_dir, "en")
    key = code if ar.has("errors", code) else "internal"
    return json.dumps(
        {
            "code": code,
            "message_ar": ar.get("errors", key, **vars),
            "message_en": en.get("errors", key, **vars),
        },
        ensure_ascii=False,
    )


def _pipeline_of(app: FastAPI, settings: Settings) -> Pipeline:
    if not getattr(app.state, "ready", False) or app.state.pipeline is None:
        raise ToolInputError(_envelope("degraded", settings))
    pipeline: Pipeline = app.state.pipeline
    return pipeline


async def _run[T](settings: Settings, fn: Callable[[], Awaitable[T]]) -> T:
    try:
        return await fn()
    except DevGateError as exc:
        raise ToolInputError(_envelope(exc.code, settings, **exc.vars)) from None
    except ToolInputError:
        raise
    except Exception as exc:  # class only — never the text (ADR-004)
        log.exception("mcp tool failed: %s", exc.__class__.__name__)
        raise ToolInputError(_envelope("internal", settings)) from None


def build_mcp_app(app: FastAPI, settings: Settings) -> Starlette:
    """Create the MCP ASGI app bound to ``app.state`` (lazy: the pipeline is read per call)."""
    from mcp.server.mcpserver import MCPServer  # noqa: PLC0415  (optional extra "mcp")

    server = MCPServer(
        name="basira",
        title="Basira — deterministic Quran/Hadith quotation checker",
        version=__version__,
        instructions=grounding_rules("en")["text"],
        website_url="https://github.com/alabasi2025/Project-Basira",
    )

    @server.tool(
        name="verify_text",
        title="Verify every Quran/Hadith quotation in a text",
        description=(
            "Deterministically locate every Quran or Hadith quotation inside `text` and compare each one "
            "byte-for-byte with licensed sources (Tanzil Hafs Quran; Open-Hadith-Data nine books; HadeethEnc). "
            "Returns one entry per quotation with status ∈ {found, partial_match, needs_review, not_found}, kind, "
            "quoted_text, review_reason, matches[{ref, ref_label, source_text (verbatim corpus record), source_url, "
            "diff_kinds}], notices rendered as sentences, and a determinism_hash (same text + same corpus build ⇒ "
            "same hash). `not_found` means not in Basira's sources — never a verdict on the text. Basira never "
            "generates religious text and never grades. Max length: the server's max_text_chars (default 5000)."
        ),
        structured_output=True,
    )
    async def verify_text(text: str, ui_lang: str = "ar") -> dict[str, Any]:
        p = _pipeline_of(app, settings)
        return await _run(settings, lambda: _verify_text(p, settings, text, ui_lang))

    @server.tool(
        name="verify_quote",
        title="Verify one quotation against an optional claimed reference",
        description=(
            "Check a single quotation (`text`, Arabic) and, optionally, the reference the author claimed for it "
            '(`claimed_ref`, e.g. "2:255", "البقرة: 255", "البخاري 1", "رواه مسلم"). Returns the status of the '
            "quotation and `claimed_source_mismatch` = true when the text was found somewhere other than the claimed "
            "reference (the status itself is unaffected). The matched record is returned verbatim in quote.matches."
        ),
        structured_output=True,
    )
    async def verify_quote(text: str, claimed_ref: str | None = None, ui_lang: str = "ar") -> dict[str, Any]:
        p = _pipeline_of(app, settings)
        return await _run(settings, lambda: _verify_quote(p, settings, text, claimed_ref, ui_lang))

    @server.tool(
        name="guard_answer",
        title="Guard: check a chatbot answer before showing it",
        description=(
            "Run Basira over a full chatbot `answer` and return a verdict about its quotations: `clear` (every "
            "quotation found verbatim), `flagged` (at least one quotation is partial_match / needs_review / "
            "not_found → review before publishing) or `no_quotes`. Includes counts, the per-quotation detail, and "
            "fixed-template summaries `summary_ar` / `summary_en` that contain no religious text and no judgment."
        ),
        structured_output=True,
    )
    async def guard_answer(answer: str, ui_lang: str = "ar") -> dict[str, Any]:
        p = _pipeline_of(app, settings)
        return await _run(settings, lambda: _guard_answer(p, settings, answer, ui_lang))

    @server.tool(
        name="list_sources",
        title="List Basira's sources (provenance)",
        description=(
            "The licensed corpora Basira verifies against, from corpus/manifest.json: id, name, type, version/commit, "
            "licence and licence URL, purpose, pinned sha256, record count. Use it to cite provenance."
        ),
        structured_output=True,
    )
    async def list_sources() -> dict[str, Any]:
        manifest = getattr(app.state, "manifest", None) or json.loads(
            settings.manifest_path.read_text(encoding="utf-8")
        )
        counts = app.state.store.counts if getattr(app.state, "ready", False) else {}
        return {"sources": sources_info(manifest, counts)}

    @server.tool(
        name="grounding_rules",
        title="Grounding rules for presenting Basira results",
        description=(
            "Fixed instructions drawn from SAFETY.md: what the four states mean, the red lines (no generated religious "
            "text, no grading or rulings, no storage), what `not_found` does and does not mean, and how Basira "
            "complements retrieval tools such as get_quran_verses. Call once per session; `ui_lang` = ar | en."
        ),
        structured_output=True,
    )
    async def grounding_rules_tool(ui_lang: str = "en") -> dict[str, Any]:
        return grounding_rules(ui_lang)

    @server.tool(
        name="issue_receipt",
        title="Issue a stateless verification receipt",
        description=(
            "Run the same check as verify_text and return a verification receipt: receipt_id, determinism_hash, "
            "corpus versions, index_sha256, build_sha, issued_at (UTC), summary{quotes, by_status}, the compact "
            "quotes, and `token` — base64url(zlib(json{v:1,t:text,l:ui_lang})). The token IS the input; nothing is "
            "stored. Anyone can re-run it later at GET /v/{token}?h=<determinism_hash>: `verified_now` when the fresh "
            "hash still equals it, `stale` when the corpus build or a verdict changed."
        ),
        structured_output=True,
    )
    async def issue_receipt(text: str, ui_lang: str = "ar") -> dict[str, Any]:
        p = _pipeline_of(app, settings)
        return await _run(
            settings,
            lambda: _issue_receipt(
                p,
                settings,
                text,
                ui_lang,
                index_sha256=str(LAST_BOOT["index_sha256"]),
                build_sha=settings.build_sha,
            ),
        )

    return server.streamable_http_app(
        streamable_http_path=MCP_PATH,
        stateless_http=True,  # no sessions, nothing kept between calls (ADR-004)
        json_response=True,
        host="0.0.0.0",
        max_request_body_size=256 * 1024,
    )


def mount_mcp(app: FastAPI, settings: Settings) -> Starlette:
    """Mount the MCP app on ``app`` and chain its lifespan into FastAPI's. Returns the mounted ASGI app."""
    mcp_app = build_mcp_app(app, settings)
    outer = app.router.lifespan_context

    @asynccontextmanager
    async def chained(fast: FastAPI) -> AsyncIterator[Any]:
        async with outer(fast) as state, mcp_app.router.lifespan_context(mcp_app):
            yield state

    app.router.lifespan_context = chained

    # Exact-path route instead of ``app.mount("/", …)``: a root mount would swallow every URL the FastAPI
    # router does not own — i.e. the SPA fallback ``/{full_path:path}`` (E-034): ``/`` and every client route
    # 404'd whenever BASIRA_MCP=1. ``Route`` with a raw ASGI app endpoint matches MCP_PATH only (GET/POST/
    # DELETE per the Streamable HTTP spec); the sub-app sees the same path so its own router still matches.
    app.router.routes.insert(0, Route(MCP_PATH, endpoint=mcp_app, methods=["GET", "POST", "DELETE"]))
    return mcp_app
