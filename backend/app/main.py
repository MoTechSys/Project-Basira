"""Basira HTTP API (docs/API.md, ADR-001/004).

* lifespan loads the Store + Retriever once; ``/health`` answers 503 ``loading`` until ready (E-011);
* ``POST /v1/check`` — the only mutating-looking endpoint; stores NOTHING (ADR-004);
* ``POST /v1/check/image`` — OCR via ``VisionClient`` then the same pipeline with ``source_modality=image``;
* ``GET /v1/sources`` — straight from ``corpus/manifest.json``;
* ``GET /v1/messages/{lang}`` — the UI strings (single source of truth, E-009);
* developer gate (docs/API.md): ``GET /v1/rules``, ``POST /v1/guard``, ``X-Basira-Determinism-Hash``
  on ``/v1/check``, and the MCP server at ``/mcp`` when ``BASIRA_MCP=1`` (docs/INTEGRATIONS.md §3.1);
* every error is ``{"error":{"code","message_ar","message_en"}}`` (docs/API.md §Errors);
* in-memory fixed-window rate limit per client IP (30/min default) with ``X-Eval-Key`` bypass for evaluation runs.

No request body or user text is ever logged. Access logs are left to the ASGI server and
contain only method/path/status.
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import logging
import os
import re
import resource
import time
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.byok import DEFAULT_MODEL as DEFAULT_MODEL_ID
from app.byok import (
    ByokError,
    ModelConfig,
    build_providers,
    catalog_payload,
    clear_config,
    config_path,
    load_config,
    save_config,
    validate,
    verify_key,
)
from app.config import REPO_ROOT, Settings
from app.config import settings as default_settings
from app.devgate import DevGateError, grounding_rules, issue_receipt, verify_receipt
from app.english_gate import EnglishGate
from app.guard import guard_answer
from app.messages import load_messages, self_check_templates
from app.pipeline import CorpusMeta, Pipeline
from app.providers import ProviderError, make_llm, make_picker, make_vision
from app.schemas import (
    CheckRequest,
    CheckResponse,
    ErrorBody,
    ErrorResponse,
    GuardRequest,
    GuardResponse,
    HealthResponse,
    ReceiptRequest,
    ReceiptResponse,
    RulesResponse,
    SourceInfo,
)
from app.snapshot import LAST_BOOT, load_or_build

log = logging.getLogger("basira")

MAX_IMAGE_BYTES = 6 * 1024 * 1024
ALLOWED_IMAGE_MIME = frozenset({"image/png", "image/jpeg", "image/webp"})


class ApiError(Exception):
    def __init__(self, status: int, code: str, **vars: Any) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.vars = vars


class RateLimiter:
    """Fixed 60 s window per key, in memory (single process). Enough for a demo; documented limit."""

    def __init__(self, per_min: int) -> None:
        self.per_min = per_min
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, now: float | None = None) -> bool:
        if self.per_min <= 0:
            return True
        now = time.monotonic() if now is None else now
        dq = self._hits.setdefault(key, deque())
        while dq and now - dq[0] >= 60.0:
            dq.popleft()
        if len(dq) >= self.per_min:
            return False
        dq.append(now)
        if len(self._hits) > 10_000:  # bounded memory
            for k in [k for k, v in self._hits.items() if not v or now - v[-1] >= 60.0]:
                self._hits.pop(k, None)
        return True


_IMAGE_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)


def sniff_image_mime(data: bytes) -> str | None:
    """Content sniffing for the three accepted types (B12): PNG / JPEG signatures, WebP = RIFF….WEBP."""
    for magic, mime in _IMAGE_MAGIC:
        if data.startswith(magic):
            return mime
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


Networks = tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]


def client_identity(peer: str, forwarded_for: str | None, trusted: Networks) -> str:
    """B12: walk `X-Forwarded-For` from the right, skipping trusted hops; the first untrusted address is the
    client. Without trusted proxies, or when the peer is not trusted, the peer itself is the identity."""
    if not _is_trusted(peer, trusted):
        return peer
    hops = [h.strip() for h in (forwarded_for or "").split(",") if h.strip()]
    for hop in reversed(hops):
        if not _is_trusted(hop, trusted):
            return hop
    return hops[0] if hops else peer


def _is_trusted(addr: str, trusted: Networks) -> bool:
    if not trusted:
        return False
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return any(ip in net for net in trusted)


def parse_trusted_proxies(items: tuple[str, ...]) -> Networks:
    out: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for it in items:
        try:
            out.append(ipaddress.ip_network(it, strict=False))
        except ValueError:
            log.warning("ignoring invalid BASIRA_TRUSTED_PROXIES entry")
    return tuple(out)


def _inline_script_hashes(static_dir: Path | None) -> list[str]:
    """CSP `sha256-…` tokens for every executable inline <script> in the built index.html."""
    if static_dir is None:
        return []
    html_path = static_dir / "index.html"
    if not html_path.exists():
        return []
    html = html_path.read_text(encoding="utf-8")
    out: list[str] = []
    for m in re.finditer(r"<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>", html, flags=re.S):
        attrs, body = m.group("attrs"), m.group("body")
        if "src=" in attrs or not body.strip():
            continue  # external or empty
        t = re.search(r'type\s*=\s*["\']([^"\']+)', attrs)
        if t and t.group(1) not in ("module", "text/javascript", "application/javascript"):
            continue  # application/ld+json etc. — data blocks are not executed
        digest = hashlib.sha256(body.encode("utf-8")).digest()
        out.append("sha256-" + base64.b64encode(digest).decode("ascii"))
    return out


def _rss_mb() -> int:
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024)


def _error(status: int, code: str, messages_dir: Path, **vars: Any) -> JSONResponse:
    ar = load_messages(messages_dir, "ar")
    en = load_messages(messages_dir, "en")
    key = code if ar.has("errors", code) else "internal"
    body = ErrorResponse(
        error=ErrorBody(
            code=code, message_ar=ar.get("errors", key, **vars), message_en=en.get("errors", key, **vars)
        )
    )
    return JSONResponse(status_code=status, content=body.model_dump())


def create_app(cfg: Settings | None = None) -> FastAPI:
    cfg = cfg or default_settings
    limiter = RateLimiter(cfg.rate_limit_per_min)
    trusted = parse_trusted_proxies(cfg.trusted_proxies)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.ready = False
        app.state.pipeline = None
        problems = self_check_templates(cfg.messages_dir)
        if problems:
            raise RuntimeError(f"forbidden lexicon in message templates: {problems}")
        t0 = time.time()
        # E-031: binary snapshot (mmap) → ~1 s boot, ~300 MB RSS; falls back to a full build + writes it
        store, retriever = load_or_build(cfg.index_dir, write=cfg.snapshot_write)
        manifest = json.loads(cfg.manifest_path.read_text(encoding="utf-8"))
        meta = CorpusMeta.from_manifest(manifest, store.meta)
        app.state.llm = make_llm(cfg.llm_provider)
        app.state.vision = make_vision(cfg.vision_provider)
        picker = make_picker(cfg.llm_provider)
        # E-051: a key saved once from /settings lives on the server and wins over env defaults.
        app.state.model_config = load_config(config_path(REPO_ROOT))
        if app.state.model_config is not None:
            app.state.llm, app.state.vision, picker = build_providers(app.state.model_config)
            log.info("model config loaded: %s", app.state.model_config.model)  # never the key
        english = EnglishGate.from_path(
            store,
            cfg.index_dir / "translations.pkl",
            picker,
            hadeethenc_link_only=(cfg.hadeethenc_mode == "link"),
        )
        app.state.pipeline = Pipeline(store, retriever, app.state.llm, cfg, meta, english=english)
        app.state.manifest = manifest
        app.state.store = store
        app.state.ready = True
        log.info("ready in %.1fs rss=%d MB", time.time() - t0, _rss_mb())
        yield
        app.state.ready = False

    app = FastAPI(
        title="Basira API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if os.environ.get("BASIRA_DOCS", "1") == "1" else None,
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cfg.cors_origins),
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-Eval-Key"],
        max_age=600,
    )

    # ------------------------------------------------------------- security headers (E-033)
    # OWASP Secure Headers baseline. CSP allows only same-origin assets + inline styles (Vite
    # injects none at runtime, but the brand tokens use CSS custom properties inline in preview).
    # `script-src` stays strict: the only inline <script> that *executes* is the theme pre-paint in
    # frontend/index.html (JSON-LD is data, not executed). Its sha256 is computed from the built
    # index.html at startup so the hash can never drift from the shipped markup; when no build is
    # present (dev / tests) only 'self' is allowed and Vite's dev server is never behind this CSP.
    _script_src = "'self'" + "".join(f" '{h}'" for h in _inline_script_hashes(cfg.static_dir))
    _CSP = (
        "default-src 'self'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        f"script-src {_script_src}; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "object-src 'none'; "
        "upgrade-insecure-requests"
    )

    # Frontend need (WP-v3, E-050): the built bundle is served by this process (BASIRA_STATIC_DIR); without
    # compression the browser downloads ~340 kB of JS instead of ~106 kB. Responses carry no secrets/cookies.
    from starlette.middleware.gzip import GZipMiddleware  # noqa: PLC0415

    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Any) -> Any:
        resp = await call_next(request)
        h = resp.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        h.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        h.setdefault("Content-Security-Policy", _CSP)
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.url.path.startswith("/v1/"):
            h.setdefault("Cache-Control", "no-store")
        return resp

    # ------------------------------------------------------------- error envelope

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _error(exc.status, exc.code, cfg.messages_dir, **exc.vars)

    @app.exception_handler(ByokError)
    async def _byok_error(_: Request, exc: ByokError) -> JSONResponse:
        return _error(400, exc.code, cfg.messages_dir)

    @app.exception_handler(DevGateError)
    async def _devgate_error(_: Request, exc: DevGateError) -> JSONResponse:
        status = {"text_too_long": 413, "invalid_input": 422}.get(exc.code, 400)
        return _error(status, exc.code, cfg.messages_dir, **exc.vars)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        for e in exc.errors():
            if e.get("type") in {"string_too_long"}:
                return _error(413, "text_too_long", cfg.messages_dir, max=cfg.max_text_chars)
        return _error(422, "invalid_input", cfg.messages_dir)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled: %s", exc.__class__.__name__)  # class only — never the text
        return _error(500, "internal", cfg.messages_dir)

    # ------------------------------------------------------------- guards

    def _client_key(request: Request) -> str:
        """Rate-limit identity (B12): the TCP peer, unless the peer is a configured trusted proxy — only then
        the right-most *untrusted* hop of `X-Forwarded-For` is used (a client cannot mint identities by
        sending the header itself)."""
        peer = request.client.host if request.client else "?"
        return client_identity(peer, request.headers.get("x-forwarded-for"), trusted)

    def _guard(request: Request) -> Pipeline:
        if not getattr(request.app.state, "ready", False) or request.app.state.pipeline is None:
            raise ApiError(503, "degraded")
        eval_key = request.headers.get("x-eval-key", "")
        if not (cfg.eval_key and eval_key == cfg.eval_key) and not limiter.allow(_client_key(request)):
            raise ApiError(429, "rate_limited")
        pipeline: Pipeline = request.app.state.pipeline
        return pipeline

    # ------------------------------------------------------------- routes

    @app.get("/health", response_model=HealthResponse, responses={503: {"model": ErrorResponse}})
    async def health(request: Request) -> Any:
        ready = getattr(request.app.state, "ready", False)
        if not ready:
            return JSONResponse(
                status_code=503,
                content=HealthResponse(
                    status="loading",
                    build_sha=cfg.build_sha,
                    corpus={},
                    corpus_loaded=False,
                    counts={},
                    rss_mb=_rss_mb(),
                    providers={"llm": cfg.llm_provider, "vision": cfg.vision_provider},
                ).model_dump(),
            )
        store = request.app.state.store
        pipeline: Pipeline = request.app.state.pipeline
        return HealthResponse(
            status="ok",
            build_sha=cfg.build_sha,
            corpus=pipeline.meta.versions(),
            corpus_loaded=True,
            counts=store.counts,
            rss_mb=_rss_mb(),
            providers={"llm": request.app.state.llm.name, "vision": request.app.state.vision.name},
            index_sha256=str(LAST_BOOT["index_sha256"]),
            boot=LAST_BOOT["mode"],
            boot_seconds=float(LAST_BOOT["seconds"]),
        )

    @app.post(
        "/v1/check",
        response_model=CheckResponse,
        responses={
            413: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
        },
    )
    async def check(req: CheckRequest, request: Request) -> JSONResponse:
        pipeline = _guard(request)
        if len(req.text) > cfg.max_text_chars:
            raise ApiError(413, "text_too_long", max=cfg.max_text_chars)
        if not req.text.strip():
            raise ApiError(422, "invalid_input")
        resp = await pipeline.check(req)
        # Developer gate: the reproducibility contract is also a header, so proxies/log pipelines can
        # record it without parsing the body (docs/API.md §Determinism).
        return JSONResponse(
            content=resp.model_dump(), headers={"X-Basira-Determinism-Hash": resp.determinism_hash}
        )

    @app.post(
        "/v1/check/image",
        response_model=CheckResponse,
        responses={
            413: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
        },
    )
    async def check_image(
        request: Request,
        image: UploadFile = File(...),  # noqa: B008
        ui_lang: str = Form("ar"),
    ) -> CheckResponse:
        pipeline = _guard(request)
        mime = (image.content_type or "").lower()
        if mime not in ALLOWED_IMAGE_MIME:
            raise ApiError(422, "invalid_input")
        data = await image.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            raise ApiError(413, "image_too_large", max_mb=MAX_IMAGE_BYTES // (1024 * 1024))
        if sniff_image_mime(data) != mime:  # B12: the bytes must BE the declared image type
            raise ApiError(422, "invalid_input")
        vision = request.app.state.vision
        try:
            ocr = await vision.ocr(data, mime=mime)
        except ProviderError:
            # OCR unavailable → honest empty result, flagged (never a guess)
            resp = await pipeline.check(
                CheckRequest(text=" ", ui_lang="ar" if ui_lang != "en" else "en", source_modality="image")
            )
            resp.extraction_degraded = True
            return resp
        full_text = ocr.text.strip()
        text = full_text[: cfg.max_text_chars] or " "
        req = CheckRequest(text=text, ui_lang="ar" if ui_lang != "en" else "en", source_modality="image")
        notices: list[str] = []
        if vision.name == "mock":
            notices.append("ocr_mock")  # never present fixture text as if it were read from the image
        if len(full_text) > cfg.max_text_chars:
            notices.append("ocr_truncated")  # B10: the image held more text than one request checks — say so
        resp = await pipeline.check(req, extra_notices=notices)
        resp.ocr_text = text.strip() or None
        resp.ocr_truncated = len(full_text) > cfg.max_text_chars
        return resp

    # ------------------------------------------------------------- model config (E-051, docs/MODELS.md)
    def _apply_model_config(mc: ModelConfig | None) -> None:
        """Swap the live providers in-process (same pipeline object; the deterministic core is untouched)."""
        request_app = app
        if mc is None:
            request_app.state.llm = make_llm(cfg.llm_provider)
            request_app.state.vision = make_vision(cfg.vision_provider)
            picker = make_picker(cfg.llm_provider)
        else:
            request_app.state.llm, request_app.state.vision, picker = build_providers(mc)
        request_app.state.model_config = mc
        pipeline: Pipeline | None = getattr(request_app.state, "pipeline", None)
        if pipeline is not None:
            pipeline.llm = request_app.state.llm
            pipeline.english.picker = picker

    def _config_payload(mc: ModelConfig | None) -> dict[str, Any]:
        return {
            "configured": mc is not None,
            "model": mc.model if mc else None,
            "key_masked": mc.masked if mc else None,
            "provider": app.state.llm.name if getattr(app.state, "llm", None) else cfg.llm_provider,
        }

    @app.get("/v1/models")
    async def models() -> Any:
        """Curated catalog with measured numbers + the current server-side configuration (key masked)."""
        mc: ModelConfig | None = getattr(app.state, "model_config", None)
        return {"default": DEFAULT_MODEL_ID, "models": catalog_payload(), "config": _config_payload(mc)}

    @app.put("/v1/models/config", responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}})
    async def models_config_put(body: dict[str, Any], request: Request) -> Any:
        """Save the Genspark key + model on the server (once). Verifies the pair with one 5-token call first;
        a key that fails is not saved. The response never echoes the key."""
        _guard(request)
        api_key = str(body.get("api_key", "") or "")
        model = str(body.get("model", "") or "")
        current: ModelConfig | None = getattr(app.state, "model_config", None)
        if not api_key and current is not None:
            api_key = current.api_key  # model change only; keep the saved key
        mc = validate(api_key, model)
        check = await verify_key(mc)
        if not check.get("ok"):
            return JSONResponse(
                status_code=400, content={"saved": False, **check, "config": _config_payload(current)}
            )
        save_config(config_path(REPO_ROOT), mc)
        _apply_model_config(mc)
        return {"saved": True, **check, "config": _config_payload(mc)}

    @app.delete("/v1/models/config")
    async def models_config_delete(request: Request) -> Any:
        _guard(request)
        clear_config(config_path(REPO_ROOT))
        _apply_model_config(None)
        return {"saved": False, "config": _config_payload(None)}

    @app.get("/v1/sources", response_model=list[SourceInfo])
    async def sources(request: Request) -> list[SourceInfo]:
        manifest = getattr(request.app.state, "manifest", None) or json.loads(
            cfg.manifest_path.read_text(encoding="utf-8")
        )
        counts = request.app.state.store.counts if getattr(request.app.state, "ready", False) else {}
        out: list[SourceInfo] = []
        for s in manifest.get("sources", []):
            sid = str(s["id"])
            records = counts.get(
                "tanzil"
                if sid.startswith("tanzil")
                else ("hadeethenc" if sid.startswith("hadeethenc") else sid),
                0,
            )
            out.append(
                SourceInfo(
                    id=sid,
                    name=str(s.get("name", sid)),
                    type=str(s.get("type", "")),
                    url=str(s.get("url") or s.get("repo") or ""),
                    version=str(s.get("version") or s.get("commit") or ""),
                    license=str(s.get("license", "")),
                    license_url=str(s.get("license_url", "")),
                    purpose=str(s.get("purpose", "")),
                    in_repo=False,  # data files are never committed; only the manifest is
                    records=int(records),
                    downloaded_at=s.get("downloaded_at"),
                    sha256=str(s.get("sha256") or ""),
                )
            )
        return out

    # ------------------------------------------------------------- developer gate (docs/API.md, docs/GUARD.md)

    @app.get("/v1/rules", response_model=RulesResponse)
    async def rules(ui_lang: str = "en") -> RulesResponse:
        """Fixed grounding rules for models/integrators (same text as the MCP `grounding_rules` tool)."""
        return RulesResponse(**grounding_rules(ui_lang))

    @app.post(
        "/v1/guard",
        response_model=GuardResponse,
        responses={
            413: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
        },
    )
    async def guard(req: GuardRequest, request: Request) -> JSONResponse:
        """Check a chatbot answer before it reaches the user: clear | flagged | no_quotes (docs/GUARD.md)."""
        pipeline = _guard(request)
        result = await guard_answer(pipeline, cfg, req.answer, req.ui_lang)
        return JSONResponse(
            content=GuardResponse(**result).model_dump(),
            headers={"X-Basira-Determinism-Hash": str(result["determinism_hash"])},
        )

    @app.post(
        "/v1/receipt",
        response_model=ReceiptResponse,
        responses={
            413: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
        },
    )
    async def receipt(req: ReceiptRequest, request: Request) -> JSONResponse:
        """Stateless verification receipt: run the check, return the verdicts + a token that *is* the input
        (base64url(zlib(json))). Nothing is stored (ADR-004); `GET /v/{token}` re-runs it (docs/API.md)."""
        pipeline = _guard(request)
        result = await issue_receipt(
            pipeline,
            cfg,
            req.text,
            req.ui_lang,
            index_sha256=str(LAST_BOOT["index_sha256"]),
            build_sha=cfg.build_sha,
        )
        return JSONResponse(
            content=ReceiptResponse(**result).model_dump(),
            headers={
                "X-Basira-Determinism-Hash": str(result["determinism_hash"]),
                "Cache-Control": "no-store",
            },
        )

    @app.get(
        "/v/{token}",
        response_model=ReceiptResponse,
        responses={
            400: {"model": ErrorResponse},
            413: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
        },
    )
    async def verify_receipt_route(token: str, request: Request, h: str | None = None) -> JSONResponse:
        """Re-run a receipt in full. `verified_now` = the fresh hash equals `?h=`; `stale` = it differs (the corpus
        build or a verdict changed — stated, never hidden). JSON only; the UI renders it."""
        pipeline = _guard(request)
        result = await verify_receipt(
            pipeline, cfg, token, h, index_sha256=str(LAST_BOOT["index_sha256"]), build_sha=cfg.build_sha
        )
        return JSONResponse(
            content=ReceiptResponse(**result).model_dump(),
            headers={
                "X-Basira-Determinism-Hash": str(result["determinism_hash"]),
                "Cache-Control": "no-store",
            },
        )

    @app.get("/v1/messages/{lang}")
    async def messages(lang: str) -> dict[str, Any]:
        if lang not in ("ar", "en"):
            raise ApiError(422, "invalid_input")
        raw = json.loads((cfg.messages_dir / f"{lang}.json").read_text(encoding="utf-8"))
        raw.pop("$comment", None)
        return dict(raw)

    # ------------------------------------------------------------- MCP server (docs/INTEGRATIONS.md §3.1)
    # Opt-in (BASIRA_MCP=1). Same process, same pipeline object; without the flag /mcp is a plain 404.
    if cfg.mcp_enabled:
        from app.mcp_server import mount_mcp  # noqa: PLC0415  (optional extra "mcp")

        mount_mcp(app, cfg)

    # ------------------------------------------------------------- static frontend (E-034)
    # When `frontend/dist` exists (Docker image), serve it from the same origin: no CORS, one URL,
    # SPA fallback to index.html for client routes. API/health keep priority (registered first).
    static_dir = cfg.static_dir
    if static_dir is not None and (static_dir / "index.html").exists():
        from fastapi.responses import FileResponse  # noqa: PLC0415
        from fastapi.staticfiles import StaticFiles  # noqa: PLC0415

        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")
        if (static_dir / "brand").exists():
            app.mount("/brand", StaticFiles(directory=static_dir / "brand"), name="brand")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str) -> Any:
            candidate = (static_dir / full_path).resolve()
            if full_path and candidate.is_file() and static_dir.resolve() in candidate.parents:
                headers = {"Cache-Control": "public, max-age=31536000, immutable"} if "." in full_path else {}
                return FileResponse(candidate, headers=headers)
            return FileResponse(static_dir / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
