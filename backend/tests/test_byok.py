"""Server-side model configuration (E-051): the Genspark key is saved once on the server, never travels in
request headers, never appears in responses/logs; the deterministic verdict does not depend on the model."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, ClassVar

import httpx
import pytest
from httpx import AsyncClient

from app.byok import (
    CATALOG,
    CATALOG_IDS,
    DEFAULT_MODEL,
    ByokError,
    ModelConfig,
    clear_config,
    load_config,
    save_config,
    validate,
)
from app.messages import scan_forbidden

SECRET = "gsk-" + "S3CRET" * 8


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "model.json"
    monkeypatch.setenv("BASIRA_MODEL_CONFIG", str(p))
    return p


# ----------------------------------------------------------------------------- validation / catalog


def test_default_model_is_best_measured() -> None:
    assert DEFAULT_MODEL in CATALOG_IDS
    best = max(CATALOG, key=lambda m: (m.extract_exact, -m.extract_p50_ms))
    assert best.id == DEFAULT_MODEL


@pytest.mark.parametrize(
    ("key", "model", "base", "code"),
    [
        ("short", DEFAULT_MODEL, None, "byok_key_invalid"),
        ("gsk-" + "a" * 20 + " space", DEFAULT_MODEL, None, "byok_key_invalid"),
        ("gsk-" + "a" * 40, "gpt-4o", None, "byok_model_unknown"),
        ("gsk-" + "a" * 40, DEFAULT_MODEL, "http://evil.example/v1", "byok_base_not_allowed"),
    ],
)
def test_validate_rejects(key: str, model: str, base: str | None, code: str) -> None:
    with pytest.raises(ByokError) as ei:
        validate(key, model, base)
    assert ei.value.code == code


def test_repr_and_mask_never_leak_key() -> None:
    mc = ModelConfig(SECRET, DEFAULT_MODEL)
    assert "S3CRET" not in repr(mc) and "S3CRET" not in str(mc)
    assert mc.masked.startswith("…") and len(mc.masked) == 5


def test_catalog_notes_pass_forbidden_scan() -> None:
    for m in CATALOG:
        assert scan_forbidden(m.note_ar) == [] and scan_forbidden(m.note_en) == [], m.id


# ----------------------------------------------------------------------------- persistence


def test_save_load_clear_roundtrip(_isolated_config: Path) -> None:
    mc = ModelConfig(SECRET, DEFAULT_MODEL)
    save_config(_isolated_config, mc)
    assert oct(_isolated_config.stat().st_mode & 0o777) == "0o600"
    assert load_config(_isolated_config) == mc
    clear_config(_isolated_config)
    assert load_config(_isolated_config) is None
    clear_config(_isolated_config)  # idempotent


def test_load_rejects_corrupt_or_unknown(_isolated_config: Path) -> None:
    _isolated_config.write_text("{not json", encoding="utf-8")
    assert load_config(_isolated_config) is None
    _isolated_config.write_text(json.dumps({"api_key": SECRET, "model": "gpt-99"}), encoding="utf-8")
    assert load_config(_isolated_config) is None


# ----------------------------------------------------------------------------- HTTP surface


class _FakeClient:
    """Stands in for httpx.AsyncClient inside verify_key."""

    status = 200
    payload: ClassVar[Any] = {"choices": [{"message": {"content": "ok"}}]}

    def __init__(self, *a: Any, **k: Any) -> None:
        pass

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *a: Any) -> None:
        return None

    async def post(self, *a: Any, **k: Any) -> httpx.Response:
        return httpx.Response(self.status, json=self.payload)


async def test_models_catalog_and_unconfigured_state(client: AsyncClient) -> None:
    r = await client.get("/v1/models")
    assert r.status_code == 200
    body = r.json()
    assert body["default"] == DEFAULT_MODEL and len(body["models"]) == len(CATALOG)
    assert body["config"] == {"configured": False, "model": None, "key_masked": None, "provider": "mock"}


async def test_put_config_verifies_saves_and_switches_provider(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    _isolated_config: Path,
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    with caplog.at_level(logging.DEBUG):
        r = await client.put("/v1/models/config", json={"api_key": SECRET, "model": DEFAULT_MODEL})
    assert r.status_code == 200
    body = r.json()
    assert body["saved"] is True and body["ok"] is True
    assert body["config"]["configured"] is True and body["config"]["model"] == DEFAULT_MODEL
    assert body["config"]["provider"] == f"openai-compatible:{DEFAULT_MODEL}"
    assert _isolated_config.exists()
    # never leaks: not in the body, not in headers, not in logs
    assert "S3CRET" not in json.dumps(body) + str(dict(r.headers)) + caplog.text
    # /v1/models reflects it, still masked
    m = (await client.get("/v1/models")).json()["config"]
    assert m["configured"] and m["key_masked"].endswith(SECRET[-4:]) and "S3CRET" not in json.dumps(m)
    # /health reports the live provider
    assert (await client.get("/health")).json()["providers"]["llm"] == f"openai-compatible:{DEFAULT_MODEL}"


async def test_put_config_with_bad_key_is_not_saved(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, _isolated_config: Path
) -> None:
    class _Auth(_FakeClient):
        status = 401
        payload: ClassVar[Any] = {}

    monkeypatch.setattr(httpx, "AsyncClient", _Auth)
    r = await client.put("/v1/models/config", json={"api_key": SECRET, "model": DEFAULT_MODEL})
    assert r.status_code == 400
    assert r.json()["saved"] is False and r.json()["reason"] == "auth"
    assert not _isolated_config.exists()
    assert (await client.get("/v1/models")).json()["config"]["configured"] is False


async def test_put_config_model_only_keeps_saved_key(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    assert (
        await client.put("/v1/models/config", json={"api_key": SECRET, "model": DEFAULT_MODEL})
    ).status_code == 200
    r = await client.put("/v1/models/config", json={"model": "gpt-6-sol"})
    assert r.status_code == 200 and r.json()["config"]["model"] == "gpt-6-sol"


async def test_put_config_rejects_unknown_model_with_envelope(client: AsyncClient) -> None:
    r = await client.put("/v1/models/config", json={"api_key": SECRET, "model": "gpt-99"})
    assert r.status_code == 400
    err = r.json()["error"]
    assert err["code"] == "byok_model_unknown" and err["message_ar"] and err["message_en"]


async def test_delete_config_restores_defaults(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, _isolated_config: Path
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    await client.put("/v1/models/config", json={"api_key": SECRET, "model": DEFAULT_MODEL})
    r = await client.delete("/v1/models/config")
    assert r.status_code == 200 and r.json()["config"]["configured"] is False
    assert not _isolated_config.exists()
    assert (await client.get("/health")).json()["providers"]["llm"] == "mock"


async def test_check_headers_are_ignored_and_verdict_is_model_independent(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No per-request key path exists: stray headers change nothing. And a bracketed quote gets the same
    hash whether the live provider is the mock or an (unreachable) configured model."""
    text = "قال تعالى: ﴿إن الله مع الصابرين﴾"
    a = (await client.post("/v1/check", json={"text": text, "ui_lang": "ar"})).json()
    b = (
        await client.post(
            "/v1/check",
            json={"text": text, "ui_lang": "ar"},
            headers={"X-Basira-LLM-Key": SECRET, "X-Basira-LLM-Model": "gpt-6-sol"},
        )
    ).json()
    assert a["determinism_hash"] == b["determinism_hash"] and b["extraction_provider"] == "mock"

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    await client.put("/v1/models/config", json={"api_key": SECRET, "model": DEFAULT_MODEL})
    monkeypatch.undo()
    c = (await client.post("/v1/check", json={"text": text, "ui_lang": "ar"})).json()
    assert c["extraction_provider"] == f"openai-compatible:{DEFAULT_MODEL}"
    assert c["extraction_degraded"] is True  # unreachable in tests → rules carried the answer
    assert c["determinism_hash"] == a["determinism_hash"]
    assert [q["status"] for q in c["quotes"]] == [q["status"] for q in a["quotes"]] == ["found"]
