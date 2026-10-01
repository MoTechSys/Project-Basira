"""Basira HTTP API (BUILD_SPEC §4, ADR-001/004).

* lifespan loads the Store + Retriever once; ``/health`` answers 503 ``loading`` until ready (E-011);
* ``POST /v1/check`` — the only mutating-looking endpoint; stores NOTHING (ADR-004);
* ``POST /v1/check/image`` — OCR via ``VisionClient`` then the same pipeline with ``source_modality=image``;
* ``GET /v1/sources`` — straight from ``corpus/manifest.json``;
* ``GET /v1/messages/{lang}`` — the UI strings (single source of truth, E-009);
* every error is ``{"error":{"code","message_ar","message_en"}}`` (audit §5);
* in-memory fixed-window rate limit per client IP (30/min default) with ``X-Eval-Key`` bypass (T5).

No request body or user text is ever logged. Access logs are left to the ASGI server and
contain only method/path/status.
"""

from __future__ import annotations

import json
import logging
import os
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
from app.config import Settings
from app.config import settings as default_settings
from app.messages import load_messages, self_check_templates
from app.pipeline import CorpusMeta, Pipeline
from app.providers import ProviderError, make_llm, make_vision
from app.retrieve.index import Retriever
from app.schemas import (
    CheckRequest,
    CheckResponse,
    ErrorBody,
    ErrorResponse,
    HealthResponse,
    SourceInfo,
)
from app.store import load_store

log = logging.getLogger("basira")

MAX_IMAGE_BYTES = 6 * 1024 * 1024
ALLOWED_IMAGE_MIME = frozenset({"image/png", "image/jpeg", "image/webp"})


class ApiError(Exception):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code


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


def _rss_mb() -> int:
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024)


def _error(status: int, code: str, messages_dir: Path) -> JSONResponse:
    ar = load_messages(messages_dir, "ar")
    en = load_messages(messages_dir, "en")
    key = code if ar.has("errors", code) else "internal"
    body = ErrorResponse(
        error=ErrorBody(code=code, message_ar=ar.get("errors", key), message_en=en.get("errors", key))
    )
    return JSONResponse(status_code=status, content=body.model_dump())


def create_app(cfg: Settings | None = None) -> FastAPI:
    cfg = cfg or default_settings
    limiter = RateLimiter(cfg.rate_limit_per_min)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.ready = False
        app.state.pipeline = None
        problems = self_check_templates(cfg.messages_dir)
        if problems:
            raise RuntimeError(f"forbidden lexicon in message templates: {problems}")
        t0 = time.time()
        store = load_store(cfg.index_dir)
        retriever = Retriever(store)
        manifest = json.loads(cfg.manifest_path.read_text(encoding="utf-8"))
        meta = CorpusMeta.from_manifest(manifest, store.meta)
        app.state.llm = make_llm(cfg.llm_provider)
        app.state.vision = make_vision(cfg.vision_provider)
        app.state.pipeline = Pipeline(store, retriever, app.state.llm, cfg, meta)
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
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Eval-Key"],
        max_age=600,
    )

    # ------------------------------------------------------------- error envelope

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _error(exc.status, exc.code, cfg.messages_dir)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        for e in exc.errors():
            if e.get("type") in {"string_too_long"}:
                return _error(413, "text_too_long", cfg.messages_dir)
        return _error(422, "invalid_input", cfg.messages_dir)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled: %s", exc.__class__.__name__)  # class only — never the text
        return _error(500, "internal", cfg.messages_dir)

    # ------------------------------------------------------------- guards

    def _client_key(request: Request) -> str:
        fwd = request.headers.get("x-forwarded-for")
        ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")
        return ip

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
    async def check(req: CheckRequest, request: Request) -> CheckResponse:
        pipeline = _guard(request)
        if len(req.text) > cfg.max_text_chars:
            raise ApiError(413, "text_too_long")
        if not req.text.strip():
            raise ApiError(422, "invalid_input")
        return await pipeline.check(req)

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
            raise ApiError(413, "text_too_long")
        try:
            ocr = await request.app.state.vision.ocr(data, mime=mime)
        except ProviderError:
            # OCR unavailable → honest empty result, flagged (never a guess)
            resp = await pipeline.check(
                CheckRequest(text=" ", ui_lang="ar" if ui_lang != "en" else "en", source_modality="image")
            )
            resp.extraction_degraded = True
            return resp
        text = ocr.text.strip()[: cfg.max_text_chars] or " "
        req = CheckRequest(text=text, ui_lang="ar" if ui_lang != "en" else "en", source_modality="image")
        return await pipeline.check(req, extra_notices=["image_extracted"])

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
                )
            )
        return out

    @app.get("/v1/messages/{lang}")
    async def messages(lang: str) -> dict[str, Any]:
        if lang not in ("ar", "en"):
            raise ApiError(422, "invalid_input")
        raw = json.loads((cfg.messages_dir / f"{lang}.json").read_text(encoding="utf-8"))
        raw.pop("$comment", None)
        return dict(raw)

    return app


app = create_app()
