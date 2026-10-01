"""Binary snapshot of the Store + Retriever (E-031): startup 23 s → ~1 s, RSS 1 GB → ~300 MB.

Why: ``load_store`` and ``Retriever`` rebuild ~4.5 M positions and two CSR indexes from
``records.jsonl`` with pure-Python loops on every boot. The *result* is only ~130 MB of numpy
arrays + ~70 MB of display strings, but the build peaks near 1 GB (Python ``array`` growth,
argsort copies, trigram rows). A single-process, single-file deploy (Fly/Oracle free tier,
Cloud Run cold start) pays that on every restart — and the judging window is 15 days.

What: after the first full build we write ``<index_dir>/snapshot/`` containing
  * every numpy array as ``.npy`` (loaded back with ``mmap_mode="r"`` → pages are shared with the
    OS page cache and only touched pages are resident);
  * ``vocab.json`` / ``svocab.json`` / ``trigram_vocab.json`` (token → id);
  * ``records.pkl`` (the ``Record`` dataclasses incl. verbatim display strings);
  * ``manifest.json`` with the ``records_sha256`` of the index it was built from.
On the next boot ``load_or_build`` checks that sha and, if it matches, loads the snapshot.
Any mismatch (new corpus build) → rebuild + rewrite. Nothing user-derived is ever stored.

Determinism: the snapshot is a pure function of ``records.jsonl``; ``/health`` exposes the
same ``records_sha256`` either way, so an eval run is reproducible with or without it.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
import time
from pathlib import Path
from typing import Any

import numpy as np

from app.retrieve.index import ChannelIndex, Csr, Retriever
from app.store import Store, load_store

log = logging.getLogger(__name__)

SNAPSHOT_VERSION = 2
_STORE_ARRAYS = ("G", "GS", "span_start", "span_end", "g_rec", "g_doc", "post_offsets", "post_positions")
_CSR_ARRAYS = ("offsets", "docs", "tfs", "idf")


def records_sha256(index_dir: Path) -> str:
    h = hashlib.sha256()
    with (index_dir / "records.jsonl").open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------------------------- save


def _save_csr(d: Path, prefix: str, csr: Csr) -> dict[str, int]:
    for a in _CSR_ARRAYS:
        np.save(d / f"{prefix}.{a}.npy", getattr(csr, a))
    return {"n_terms": csr.n_terms}


def _save_channel(d: Path, ch: ChannelIndex) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "name": ch.name,
        "avg_len": ch.avg_len,
        "avg_gram_len": ch.avg_gram_len,
        "docs": [(x.rec, x.g_start, x.g_len) for x in ch.docs],
    }
    meta["words"] = _save_csr(d, f"{ch.name}.words", ch.words)
    meta["grams"] = _save_csr(d, f"{ch.name}.grams", ch.grams)
    np.save(d / f"{ch.name}.doc_len.npy", ch.doc_len)
    np.save(d / f"{ch.name}.gram_len.npy", ch.gram_len)
    return meta


def save_snapshot(index_dir: Path, store: Store, retriever: Retriever) -> Path:
    t0 = time.time()
    d = index_dir / "snapshot"
    d.mkdir(parents=True, exist_ok=True)
    for a in _STORE_ARRAYS:
        np.save(d / f"store.{a}.npy", getattr(store, a))
    (d / "vocab.json").write_text(json.dumps(list(store.vocab.keys()), ensure_ascii=False), encoding="utf-8")
    (d / "svocab.json").write_text(
        json.dumps(list(store.svocab.keys()), ensure_ascii=False), encoding="utf-8"
    )
    tg = sorted(store.trigram_vocab.items(), key=lambda kv: kv[1])
    (d / "trigram_vocab.json").write_text(
        json.dumps([k for k, _ in tg], ensure_ascii=False), encoding="utf-8"
    )
    with (d / "records.pkl").open("wb") as fh:
        pickle.dump(store.records, fh, protocol=pickle.HIGHEST_PROTOCOL)
    manifest = {
        "snapshot_version": SNAPSHOT_VERSION,
        "records_sha256": records_sha256(index_dir),
        "store_meta": store.meta,
        "rdocs_quran": [(x.rec, x.g_start, x.g_len) for x in store.rdocs_quran],
        "rdocs_hadith": [(x.rec, x.g_start, x.g_len) for x in store.rdocs_hadith],
        "channels": {
            "quran": _save_channel(d, retriever.quran),
            "hadith": _save_channel(d, retriever.hadith),
        },
    }
    (d / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    log.info("snapshot written to %s in %.1fs", d, time.time() - t0)
    return d


# ------------------------------------------------------------------------------------- load


def _load_csr(d: Path, prefix: str, meta: dict[str, int]) -> Csr:
    arrs = {a: np.load(d / f"{prefix}.{a}.npy", mmap_mode="r") for a in _CSR_ARRAYS}
    return Csr(arrs["offsets"], arrs["docs"], arrs["tfs"], arrs["idf"], int(meta["n_terms"]))


def _load_channel(d: Path, meta: dict[str, Any]) -> ChannelIndex:
    from app.store import RetrievalDoc  # noqa: PLC0415

    name = str(meta["name"])
    docs = [RetrievalDoc(int(r), int(s), int(n)) for r, s, n in meta["docs"]]
    return ChannelIndex.from_arrays(
        docs=docs,
        name=name,
        words=_load_csr(d, f"{name}.words", meta["words"]),
        grams=_load_csr(d, f"{name}.grams", meta["grams"]),
        doc_len=np.load(d / f"{name}.doc_len.npy", mmap_mode="r"),
        gram_len=np.load(d / f"{name}.gram_len.npy", mmap_mode="r"),
        avg_len=float(meta["avg_len"]),
        avg_gram_len=float(meta["avg_gram_len"]),
    )


def load_snapshot(index_dir: Path) -> tuple[Store, Retriever] | None:
    d = index_dir / "snapshot"
    mp = d / "manifest.json"
    if not mp.exists():
        return None
    try:
        manifest = json.loads(mp.read_text(encoding="utf-8"))
        if manifest.get("snapshot_version") != SNAPSHOT_VERSION:
            return None
        if manifest.get("records_sha256") != records_sha256(index_dir):
            log.info("snapshot stale (records.jsonl changed) — rebuilding")
            return None
        t0 = time.time()
        from app.store import RetrievalDoc  # noqa: PLC0415

        arrs = {a: np.load(d / f"store.{a}.npy", mmap_mode="r") for a in _STORE_ARRAYS}
        vocab = {k: i for i, k in enumerate(json.loads((d / "vocab.json").read_text(encoding="utf-8")))}
        svocab = {k: i for i, k in enumerate(json.loads((d / "svocab.json").read_text(encoding="utf-8")))}
        with (d / "records.pkl").open("rb") as fh:
            records = pickle.load(fh)
        store = Store(
            records=records,
            vocab=vocab,
            svocab=svocab,
            G=arrs["G"],
            GS=arrs["GS"],
            span_start=arrs["span_start"],
            span_end=arrs["span_end"],
            g_rec=arrs["g_rec"],
            g_doc=arrs["g_doc"],
            post_offsets=arrs["post_offsets"],
            post_positions=arrs["post_positions"],
            rdocs_quran=[RetrievalDoc(*x) for x in manifest["rdocs_quran"]],
            rdocs_hadith=[RetrievalDoc(*x) for x in manifest["rdocs_hadith"]],
            meta=manifest["store_meta"],
        )
        store.trigram_vocab = {
            k: i for i, k in enumerate(json.loads((d / "trigram_vocab.json").read_text(encoding="utf-8")))
        }
        from app.store import _load_surah_names  # noqa: PLC0415

        store.surah_names = _load_surah_names(index_dir)
        retriever = Retriever.from_channels(
            _load_channel(d, manifest["channels"]["quran"]), _load_channel(d, manifest["channels"]["hadith"])
        )
        log.info("snapshot loaded from %s in %.2fs (%d records)", d, time.time() - t0, len(records))
        return store, retriever
    except Exception:
        log.exception("snapshot unreadable — rebuilding")
        return None


LAST_BOOT: dict[str, Any] = {"mode": "", "seconds": 0.0, "index_sha256": ""}


def load_or_build(index_dir: Path, *, write: bool = True) -> tuple[Store, Retriever]:
    t0 = time.time()
    snap = load_snapshot(index_dir)
    if snap is not None:
        LAST_BOOT.update(
            mode="snapshot", seconds=round(time.time() - t0, 2), index_sha256=records_sha256(index_dir)
        )
        return snap
    store = load_store(index_dir)
    retriever = Retriever(store)
    LAST_BOOT.update(mode="build", seconds=round(time.time() - t0, 2), index_sha256=records_sha256(index_dir))
    if write:
        try:
            save_snapshot(index_dir, store, retriever)
        except OSError:
            log.warning("could not write snapshot (read-only index dir?) — continuing without it")
    return store, retriever
