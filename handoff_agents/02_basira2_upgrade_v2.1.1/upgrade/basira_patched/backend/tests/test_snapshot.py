"""E-031 snapshot: round-trip equality, staleness detection, and E-032 determinism hash."""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from app.config import Settings
from app.pipeline import CorpusMeta, Pipeline
from app.providers import MockLLM
from app.retrieve.index import Retriever
from app.schemas import CheckRequest
from app.snapshot import load_or_build, load_snapshot
from app.store import Store

PROBES = [
    "قال تعالى: ﴿قُلْ هُوَ اللَّهُ أَحَدٌ﴾ [البقرة: 5]",
    "قال رسول الله ﷺ: «قل هو الله أحد»",
    "قال النبي ﷺ: إنما الأعمال بالنيات وإنما لكل امرئ ما نوى",
    "قال تعالى: ﴿مَلِكِ يَوْمِ الدِّينِ﴾",
    "توفي اليوم جارنا رحمه الله، إنا لله وإنا إليه راجعون",
    "قال ﷺ: «اطلبوا العلم ولو في الصين»",
    "﴿بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ﴾",
]


@pytest.fixture(scope="module")
def snap_dir(fixture_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("idx")
    for f in ("records.jsonl", "meta.json"):
        shutil.copy(fixture_dir / f, d / f)
    names = fixture_dir.parent / "surah_names.json"
    if names.exists():
        shutil.copy(names, d.parent / "surah_names.json")
    return d


def _pipeline(store: Store, retriever: Retriever, idx: Path, settings: Settings) -> Pipeline:
    cfg = replace(settings, index_dir=idx)
    manifest = json.loads(cfg.manifest_path.read_text(encoding="utf-8"))
    return Pipeline(store, retriever, MockLLM(), cfg, CorpusMeta.from_manifest(manifest, store.meta))


async def _run_all(p: Pipeline) -> list[dict]:
    out = []
    for t in PROBES:
        r = await p.check(CheckRequest(text=t))
        d = r.model_dump()
        d.pop("request_id")
        d.pop("timings_ms")
        out.append(d)
    return out


async def test_snapshot_roundtrip_is_byte_identical(snap_dir: Path, test_settings: Settings) -> None:
    assert load_snapshot(snap_dir) is None  # nothing yet
    store, retriever = load_or_build(snap_dir, write=True)
    assert (snap_dir / "snapshot" / "manifest.json").exists()
    built = await _run_all(_pipeline(store, retriever, snap_dir, test_settings))

    snap = load_snapshot(snap_dir)
    assert snap is not None
    s2, r2 = snap
    assert len(s2.records) == len(store.records)
    assert np.array_equal(np.asarray(s2.G), store.G)
    assert np.array_equal(np.asarray(s2.post_positions), store.post_positions)
    assert s2.vocab == store.vocab and s2.svocab == store.svocab
    assert s2.trigram_vocab == store.trigram_vocab
    loaded = await _run_all(_pipeline(s2, r2, snap_dir, test_settings))
    assert loaded == built
    # determinism hash is identical across boot modes and non-empty
    assert all(d["determinism_hash"] for d in loaded)
    assert [d["determinism_hash"] for d in loaded] == [d["determinism_hash"] for d in built]


async def test_snapshot_is_rejected_when_records_change(snap_dir: Path) -> None:
    assert load_snapshot(snap_dir) is not None
    # duplicate the last line (a valid record) → records.jsonl changes → sha mismatch
    lines = (snap_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()
    (snap_dir / "records.jsonl").write_text("\n".join([*lines, lines[-1]]) + "\n", encoding="utf-8")
    assert load_snapshot(snap_dir) is None
    # rebuild path still works and rewrites
    store, _ = load_or_build(snap_dir, write=True)
    assert load_snapshot(snap_dir) is not None
    assert len(store.records) > 0


async def test_determinism_hash_changes_with_input_and_is_stable(pipeline: Pipeline) -> None:
    a1 = await pipeline.check(CheckRequest(text=PROBES[0]))
    a2 = await pipeline.check(CheckRequest(text=PROBES[0]))
    b = await pipeline.check(CheckRequest(text=PROBES[1]))
    assert a1.determinism_hash == a2.determinism_hash
    assert a1.determinism_hash != b.determinism_hash
    assert len(a1.determinism_hash) == 64


def test_snapshot_write_failure_is_non_fatal(fixture_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.snapshot as snapmod  # noqa: PLC0415

    def boom(*_a: object, **_k: object) -> Path:
        raise OSError("read-only")

    monkeypatch.setattr(snapmod, "save_snapshot", boom)
    monkeypatch.setattr(snapmod, "load_snapshot", lambda _d: None)
    store, retriever = load_or_build(fixture_dir, write=True)
    assert store.records and retriever.quran is not None
