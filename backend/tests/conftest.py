"""Shared fixtures. Corpus-backed tests use the small fixture index (corpus/fixture); they are
SKIPPED when neither the fixture nor the full index exists (CI without corpus download)."""

from __future__ import annotations

import contextlib
import json
import os
import resource
import subprocess
import sys
import tempfile
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.pipeline import CorpusMeta, Pipeline
from app.providers import MockLLM
from app.retrieve.index import Retriever
from app.store import Store, load_store

REPO = Path(__file__).resolve().parents[2]

# Tests must never pick up a real key saved from /settings on this machine (E-051): point the
# server-side model config at a throwaway path before any app is created.
os.environ.setdefault("BASIRA_MODEL_CONFIG", str(Path(tempfile.gettempdir()) / "basira-test-model.json"))
Path(os.environ["BASIRA_MODEL_CONFIG"]).unlink(missing_ok=True)

# Every `client` fixture boots an app whose snapshot keeps ~15 mmap'd .npy files open for the app's
# lifetime; with 270+ tests the default soft limit of 1024 fds is reached (ENFILE in test_snapshot).
# Raise the soft limit to the hard limit — a test-process concern only, nothing in the product changes.
with contextlib.suppress(ValueError, OSError):
    _soft, _hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (min(_hard, 65536), _hard))
FIXTURE = REPO / "corpus" / "fixture"
FULL = REPO / "corpus" / "index"


def _ensure_fixture() -> Path | None:
    if (FIXTURE / "records.jsonl").exists():
        return FIXTURE
    if (FULL / "records.jsonl").exists():
        subprocess.run([sys.executable, str(REPO / "corpus" / "build_fixture.py")], check=True)
        if (FIXTURE / "records.jsonl").exists():
            return FIXTURE
    return None


@pytest.fixture(scope="session")
def fixture_dir() -> Path:
    d = _ensure_fixture()
    if d is None:
        pytest.skip("no corpus index available (run scripts/bootstrap.sh)")
    return d


@pytest.fixture(scope="session")
def test_settings(fixture_dir: Path) -> Settings:
    # static_dir=None: tests must not depend on whether `frontend/dist` happens to be built
    # (the SPA catch-all would turn an expected 404 into 405 on POST).
    return replace(
        Settings(), index_dir=fixture_dir, rate_limit_per_min=1000, eval_key="test-eval-key", static_dir=None
    )


@pytest.fixture(scope="session")
def store(fixture_dir: Path) -> Store:
    return load_store(fixture_dir)


@pytest.fixture(scope="session")
def retriever(store: Store) -> Retriever:
    return Retriever(store)


@pytest.fixture(scope="session")
def pipeline(store: Store, retriever: Retriever, test_settings: Settings) -> Pipeline:
    manifest = json.loads(test_settings.manifest_path.read_text(encoding="utf-8"))
    return Pipeline(
        store, retriever, MockLLM(), test_settings, CorpusMeta.from_manifest(manifest, store.meta)
    )


@pytest.fixture
async def client(test_settings: Settings) -> AsyncIterator[AsyncClient]:
    from app.main import create_app  # noqa: PLC0415

    app = create_app(test_settings)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
