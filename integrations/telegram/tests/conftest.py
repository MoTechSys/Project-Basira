"""Shared fixtures. Every API body under tests/fixtures/ is a real response captured from https://basirapp.site
(build f62b2ba, 2026-10-05) — no religious text in these tests is written by hand."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import httpx
import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]  # repository root
FIXTURES = HERE / "fixtures"
MESSAGES_DIR = ROOT / "messages"

sys.path.insert(0, str(ROOT / "backend"))  # the forbidden-lexicon scanner lives in the backend (V4)


def load(name: str) -> Any:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def messages_ar() -> dict[str, Any]:
    raw: dict[str, Any] = json.loads((MESSAGES_DIR / "ar.json").read_text(encoding="utf-8"))
    raw.pop("$comment", None)
    return raw


def messages_map() -> Mapping[str, Mapping[str, str]]:
    return {k: v for k, v in messages_ar().items() if isinstance(v, dict)}


Handler = Callable[[httpx.Request], httpx.Response]


def api_transport(
    routes: Mapping[str, Any] | None = None, *, log: list[httpx.Request] | None = None
) -> httpx.MockTransport:
    """A fake Basira API: path → fixture name, (status, body) or callable. ``/v1/messages/ar`` is the repo file."""
    table: dict[str, Any] = {
        "/v1/messages/ar": messages_ar(),
        "/health": {"status": "ok", "build_sha": "test"},
    }
    table.update(routes or {})

    def handle(request: httpx.Request) -> httpx.Response:
        if log is not None:
            log.append(request)
        spec = table.get(request.url.path)
        if callable(spec):
            out: httpx.Response = spec(request)
            return out
        if spec is None:
            return httpx.Response(
                404, json={"error": {"code": "not_found", "message_ar": "x", "message_en": "x"}}
            )
        if isinstance(spec, tuple):
            return httpx.Response(spec[0], json=spec[1])
        body = load(spec) if isinstance(spec, str) else spec
        return httpx.Response(200, json=body)

    return httpx.MockTransport(handle)


@pytest.fixture
def m() -> Mapping[str, Mapping[str, str]]:
    return messages_map()
