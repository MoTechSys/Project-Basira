"""Fixtures مشتركة لاختبارات الـ backend.

الاختبارات التي تحتاج ذخيرة فعلية (corpus-backed) تستخدم `fixture index` المصغّر
الموجود في `corpus/fixture/`. إذا لم يتوفر لا الـ fixture ولا الـ full index
(مثلاً CI بدون تنزيل مسبق للمصادر) → يتم SKIP تلقائياً بدون كسر CI.
"""

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

# جذر المستودع — نحتاجه لمعرفة أين corpus/fixture و corpus/index
REPO = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# عزل الاختبارات: لا يجب أن تلتقط الاختبارات أي مفتاح حقيقي محفوظ عبر /settings
# على هذه الآلة (E-051). نُشير إلى مسار مؤقت قابل للتنظيف قبل أي إنشاء للـ app.
# ---------------------------------------------------------------------------
os.environ.setdefault(
    "BASIRA_MODEL_CONFIG",
    str(Path(tempfile.gettempdir()) / "basira-test-model.json"),
)
Path(os.environ["BASIRA_MODEL_CONFIG"]).unlink(missing_ok=True)

# ---------------------------------------------------------------------------
# File descriptor limit: كل client fixture يُنشئ app يُبقي ~15 ملف npy
# مفتوحاً mmap. مع 270+ اختبار نصل للـ default soft limit (1024) ويظهر ENFILE
# في test_snapshot. نرفع الـ soft إلى الـ hard (max 65536) — عملية اختبار فقط،
# لا تغيير في المنتج.
# ---------------------------------------------------------------------------
with contextlib.suppress(ValueError, OSError):
    _soft, _hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (min(_hard, 65536), _hard))

FIXTURE = REPO / "corpus" / "fixture"
FULL = REPO / "corpus" / "index"


# ---------------------------------------------------------------------------
# منطق توفير الـ fixture — نُحاول:
#  1. إذا موجود مُسبقاً → استخدم
#  2. إذا الـ full index موجود → ابنِ fixture منه عبر build_fixture.py
#  3. وإلا → None (الاختبارات ذات الصلة تُسكّت)
# ---------------------------------------------------------------------------
def _ensure_fixture() -> Path | None:
    if (FIXTURE / "records.jsonl").exists():
        return FIXTURE
    if (FULL / "records.jsonl").exists():
        subprocess.run(
            [sys.executable, str(REPO / "corpus" / "build_fixture.py")],
            check=True,
        )
        if (FIXTURE / "records.jsonl").exists():
            return FIXTURE
    return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def fixture_dir() -> Path:
    """مسار الذخيرة المصغّرة — يُسكّت الاختبار إذا لم يُبنى بعد."""
    d = _ensure_fixture()
    if d is None:
        pytest.skip("no corpus index available (run scripts/bootstrap.sh)")
    return d


@pytest.fixture(scope="session")
def test_settings(fixture_dir: Path) -> Settings:
    """Settings مُعدّلة للاختبار:
    - index_dir يشير للـ fixture المصغّر
    - rate_limit_per_min=1000 لتجنّب 429 في الـ bursts
    - eval_key مُثبّت للـ bypass
    - static_dir=None لمنع تداخل SPA catch-all مع 404 المتوقّعة
    """
    return replace(
        Settings(),
        index_dir=fixture_dir,
        rate_limit_per_min=1000,
        eval_key="test-eval-key",
        static_dir=None,
    )


@pytest.fixture(scope="session")
def store(fixture_dir: Path) -> Store:
    """الـ Store المُحمّل من الـ fixture — session scope لتجنّب reload مكلف."""
    return load_store(fixture_dir)


@pytest.fixture(scope="session")
def retriever(store: Store) -> Retriever:
    """الـ Retriever الهجين (BM25 + fuzzy) على الـ fixture."""
    return Retriever(store)


@pytest.fixture(scope="session")
def pipeline(
    store: Store, retriever: Retriever, test_settings: Settings
) -> Pipeline:
    """Pipeline كامل مع MockLLM — session scope، آمن لأنه stateless على مستوى الـ request."""
    manifest = json.loads(test_settings.manifest_path.read_text(encoding="utf-8"))
    return Pipeline(
        store,
        retriever,
        MockLLM(),
        test_settings,
        CorpusMeta.from_manifest(manifest, store.meta),
    )


@pytest.fixture
async def client(test_settings: Settings) -> AsyncIterator[AsyncClient]:
    """HTTP client للـ API — scope=function لعزل حالة بين الاختبارات."""
    from app.main import create_app  # noqa: PLC0415

    app = create_app(test_settings)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
