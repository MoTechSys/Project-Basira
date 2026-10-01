"""Shared fixtures. Corpus-backed tests use the small fixture index (corpus/fixture); they are
SKIPPED when neither the fixture nor the full index exists (CI without corpus download)."""

from __future__ import annotations

import json
import subprocess
import sys
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
    return replace(Settings(), index_dir=fixture_dir, rate_limit_per_min=1000, eval_key="test-eval-key")


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
