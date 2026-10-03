"""English gate — deterministic BM25 retrieval over approved English translations.

Scope (docs/ENGLISH_GATE.md): **data + retrieval only.** Given an English quotation such as
«There is no compulsion in religion» return a short list of *candidates* (ayah or hadith) from the
translations fetched by ``corpus/fetch_translations.py``. A later stage (a language model or a
human) picks one candidate or rejects them all. This module never decides, never grades, never
generates text: every ``translation_text`` is the upstream string byte-for-byte.

Design
------
* Documents: one per (translation key, ayah) for the Quran — ``english_saheeh`` (priority 1) and
  ``english_rwwad`` (priority 2) — and one per HadeethEnc hadith with an English text
  (``title + hadeeth``). Footnote bodies are not indexed (commentary, not translation).
* Normalisation (``normalize_en``): NFKD → strip combining marks (``Allāh``→``allah``,
  ``ṭāghūt``→``taghut``), casefold, drop apostrophes inside words (``Qur’an``→``quran``), remove
  footnote markers ``[12]``, keep brackets' words (``[acceptance of]`` is part of the translation),
  split on anything that is not a letter or digit, then Harman's conservative *S-stemmer*
  (``ies→y``, ``es``/``s`` plural stripping with the usual guards) — no dictionary, no model.
* Two BM25 channels (k1 = 1.2, b = 0.75) over unigrams and over word bigrams, each normalised by
  the query's own idf mass so that ≈1.0 means «every query term occurs once in an average-length
  document». Final score = (1 − w)·unigram + w·bigram, w = ``BIGRAM_WEIGHT`` (measured, see docs).
* Candidates are collapsed per (kind, ref): the best-scoring translation of an ayah represents it,
  ties broken by translation priority, so the top-k never spends two slots on the same ayah.
* Determinism: pure functions of the pickle + the query; sorting is total
  (score rounded to 6 dp, then kind, then natural ref order, then priority, then doc id).
  No randomness, no time, no network, no LLM.

Build with ``corpus/build_index.py`` (writes ``corpus/index/translations.pkl``); query with
``TranslationIndex.load(path).candidates(text, k)`` or the module-level ``candidates`` helper.
"""

from __future__ import annotations

import json
import pickle
import re
import unicodedata
from array import array
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal

import numpy as np
import numpy.typing as npt

F32 = npt.NDArray[np.float32]
I32 = npt.NDArray[np.int32]
Kind = Literal["quran", "hadith"]

INDEX_VERSION = 1
K1 = 1.2
B = 0.75
BIGRAM_WEIGHT = 0.2
SCORE_DECIMALS = 6
_POOL_MIN = 64
QURAN_SOURCE_PRIORITY: dict[str, int] = {"english_saheeh": 1, "english_rwwad": 2}
HADITH_SOURCE_KEY = "hadeethenc_en"
_KIND_ORDER: dict[str, int] = {"quran": 0, "hadith": 1}

_FOOTNOTE_MARK = re.compile(r"\[\d+\]")
_APOSTROPHES = "'\u2019\u2018\u02bb\u02bc\u02be\u02bf\u0060\u00b4"
_SPLIT = re.compile(r"[^a-z0-9]+")


# --------------------------------------------------------------------------- normalisation


def _s_stem(w: str) -> str:
    """Harman (1991) S-stemmer: conservative plural stripping, no dictionary."""
    if len(w) <= 3:
        return w
    if w.endswith("ies") and not w.endswith(("eies", "aies")):
        return w[:-3] + "y"
    if w.endswith("es") and not w.endswith(("aes", "ees", "oes")):
        return w[:-1]
    if w.endswith("s") and not w.endswith(("us", "ss", "is")):
        return w[:-1]
    return w


def normalize_en(text: str) -> list[str]:
    """English tokens for indexing and querying (identical on both sides)."""
    t = _FOOTNOTE_MARK.sub(" ", text)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.casefold()
    for ch in _APOSTROPHES:
        t = t.replace(ch, "")
    return [_s_stem(w) for w in _SPLIT.split(t) if w]


def _bigrams(tokens: Sequence[str]) -> list[str]:
    return [f"{a} {b}" for a, b in pairwise(tokens)]


# --------------------------------------------------------------------------- data structures


@dataclass(frozen=True, slots=True)
class Candidate:
    kind: Kind
    ref: str  # "2:256" for Quran, HadeethEnc id (e.g. "4717") for hadith
    source_key: str  # english_saheeh | english_rwwad | hadeethenc_en
    score: float
    translation_text: str  # verbatim upstream text

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "ref": self.ref,
            "source_key": self.source_key,
            "score": self.score,
            "translation_text": self.translation_text,
        }


@dataclass(frozen=True, slots=True)
class _Doc:
    kind: Kind
    ref: str
    source_key: str
    priority: int
    text: str  # returned verbatim as Candidate.translation_text
    index_text: str  # what BM25 sees (Quran: == text; hadith: title + hadeeth)


@dataclass(slots=True)
class _Csr:
    offsets: I32
    docs: I32
    tfs: F32
    idf: F32
    doc_len: F32
    avg_len: float

    def to_state(self) -> dict[str, Any]:
        return {
            "offsets": self.offsets,
            "docs": self.docs,
            "tfs": self.tfs,
            "idf": self.idf,
            "doc_len": self.doc_len,
            "avg_len": self.avg_len,
        }

    @classmethod
    def from_state(cls, s: dict[str, Any]) -> _Csr:
        return cls(s["offsets"], s["docs"], s["tfs"], s["idf"], s["doc_len"], float(s["avg_len"]))


def _build_csr(rows: list[list[int]], n_terms: int) -> _Csr:
    terms = array("i")
    docs = array("i")
    tfs = array("f")
    lengths = array("f")
    for d, ids in enumerate(rows):
        lengths.append(float(len(ids)))
        if not ids:
            continue
        uniq, cnt = np.unique(np.asarray(ids, dtype=np.int32), return_counts=True)
        terms.frombytes(uniq.astype(np.int32).tobytes())
        docs.frombytes(np.full(len(uniq), d, dtype=np.int32).tobytes())
        tfs.frombytes(cnt.astype(np.float32).tobytes())
    t = np.frombuffer(terms, dtype=np.int32)
    d_arr = np.frombuffer(docs, dtype=np.int32)
    tf_arr = np.frombuffer(tfs, dtype=np.float32)
    order = np.argsort(t, kind="stable")
    t, d_arr, tf_arr = t[order], d_arr[order], tf_arr[order]
    n_docs = len(rows)
    df = np.bincount(t, minlength=n_terms).astype(np.float32)
    offsets = np.zeros(n_terms + 1, dtype=np.int32)
    np.cumsum(df.astype(np.int32), out=offsets[1:])
    idf = np.log1p((n_docs - df + 0.5) / (df + 0.5)).astype(np.float32)
    doc_len = np.frombuffer(lengths, dtype=np.float32).copy()
    avg_len = float(doc_len.mean()) if n_docs else 1.0
    return _Csr(offsets, d_arr.copy(), tf_arr.copy(), idf, doc_len, avg_len)


# --------------------------------------------------------------------------- index


class TranslationIndex:
    """BM25 (unigram + bigram) over English translation documents. Immutable after build/load."""

    def __init__(
        self,
        docs: list[_Doc],
        uni_vocab: dict[str, int],
        bi_vocab: dict[str, int],
        uni: _Csr,
        bi: _Csr,
        meta: dict[str, Any],
    ) -> None:
        self.docs = docs
        self.uni_vocab = uni_vocab
        self.bi_vocab = bi_vocab
        self.uni = uni
        self.bi = bi
        self.meta = meta
        self._ref_sort_keys: list[tuple[int, tuple[int, ...], int, int]] = [
            (_KIND_ORDER[d.kind], _ref_key(d.ref), d.priority, i) for i, d in enumerate(docs)
        ]

    # ------------------------------------------------------------------ build / io

    @classmethod
    def build(cls, docs: Iterable[_Doc], *, meta: dict[str, Any] | None = None) -> TranslationIndex:
        doc_list = list(docs)
        uni_vocab: dict[str, int] = {}
        bi_vocab: dict[str, int] = {}
        uni_rows: list[list[int]] = []
        bi_rows: list[list[int]] = []
        for d in doc_list:
            toks = normalize_en(d.index_text)
            uni_rows.append([uni_vocab.setdefault(t, len(uni_vocab)) for t in toks])
            bi_rows.append([bi_vocab.setdefault(g, len(bi_vocab)) for g in _bigrams(toks)])
        uni = _build_csr(uni_rows, len(uni_vocab))
        bi = _build_csr(bi_rows, len(bi_vocab))
        m: dict[str, Any] = {
            "index_version": INDEX_VERSION,
            "k1": K1,
            "b": B,
            "bigram_weight": BIGRAM_WEIGHT,
            "n_docs": len(doc_list),
            "n_quran_docs": sum(1 for d in doc_list if d.kind == "quran"),
            "n_hadith_docs": sum(1 for d in doc_list if d.kind == "hadith"),
            "n_unigrams": len(uni_vocab),
            "n_bigrams": len(bi_vocab),
        }
        if meta:
            m.update(meta)
        return cls(doc_list, uni_vocab, bi_vocab, uni, bi, m)

    def save(self, path: Path) -> None:
        state = {
            "index_version": INDEX_VERSION,
            "docs": [(d.kind, d.ref, d.source_key, d.priority, d.text, d.index_text) for d in self.docs],
            "uni_vocab": self.uni_vocab,
            "bi_vocab": self.bi_vocab,
            "uni": self.uni.to_state(),
            "bi": self.bi.to_state(),
            "meta": self.meta,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        with tmp.open("wb") as fh:
            pickle.dump(state, fh, protocol=5)
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path) -> TranslationIndex:
        with path.open("rb") as fh:
            state = pickle.load(fh)  # produced locally by corpus/build_index.py
        if state.get("index_version") != INDEX_VERSION:
            raise ValueError(
                f"{path}: index_version {state.get('index_version')} != {INDEX_VERSION}; rebuild"
            )
        docs = [_Doc(k, r, s, p, t, it) for (k, r, s, p, t, it) in state["docs"]]
        return cls(
            docs,
            state["uni_vocab"],
            state["bi_vocab"],
            _Csr.from_state(state["uni"]),
            _Csr.from_state(state["bi"]),
            state["meta"],
        )

    # ------------------------------------------------------------------ scoring

    def _channel(self, csr: _Csr, vocab: dict[str, int], terms: Sequence[str]) -> F32 | None:
        """Normalised BM25 for one channel; ``None`` when no query term is in the vocabulary."""
        ids = sorted({vocab[t] for t in terms if t in vocab})
        if not ids:
            return None
        n_docs = len(csr.doc_len)
        scores = np.zeros(n_docs, dtype=np.float64)
        norm = K1 * (1.0 - B + B * csr.doc_len / csr.avg_len)
        idf_mass = 0.0
        for t in ids:
            a, b = int(csr.offsets[t]), int(csr.offsets[t + 1])
            idf = float(csr.idf[t])
            idf_mass += idf
            if a == b:
                continue
            d = csr.docs[a:b]
            tf = csr.tfs[a:b]
            contrib = idf * tf * (K1 + 1.0) / (tf + norm[d])
            scores += np.bincount(d, weights=contrib, minlength=n_docs)
        if idf_mass <= 0.0:
            return None
        return (scores / idf_mass).astype(np.float32)

    def scores(self, text: str) -> F32:
        """Per-document fused score (0 for documents sharing nothing with the query)."""
        toks = normalize_en(text)
        n = len(self.docs)
        if not toks:
            return np.zeros(n, dtype=np.float32)
        s_uni = self._channel(self.uni, self.uni_vocab, toks)
        s_bi = self._channel(self.bi, self.bi_vocab, _bigrams(toks)) if len(toks) > 1 else None
        fused = np.zeros(n, dtype=np.float32)
        if s_uni is not None:
            fused += np.float32(1.0 - BIGRAM_WEIGHT) * s_uni
        if s_bi is not None:
            fused += np.float32(BIGRAM_WEIGHT) * s_bi
        return fused

    def candidates(self, text: str, k: int = 5, *, kinds: Iterable[Kind] | None = None) -> list[Candidate]:
        """Top-``k`` candidates, one per (kind, ref), deterministic order. Empty when nothing overlaps."""
        if k <= 0:
            return []
        fused = self.scores(text)
        allowed = set(kinds) if kinds is not None else {"quran", "hadith"}
        nz = np.flatnonzero(fused > 0.0)
        if nz.size == 0:
            return []
        # Pool = every doc whose score ties or beats the m-th best (m = k × translations-per-ref + margin),
        # so the total order below is computed on ≤ a few hundred docs instead of the whole corpus and
        # the result is identical to sorting everything (ties are included, never cut).
        pool_size = min(nz.size, max(_POOL_MIN, k * (len(QURAN_SOURCE_PRIORITY) + 1) * 4))
        if pool_size < nz.size:
            part = nz[np.argpartition(-fused[nz], pool_size - 1)[:pool_size]]
            threshold = round(float(fused[part].min()), SCORE_DECIMALS)
            pool = nz[np.round(fused[nz], SCORE_DECIMALS) >= threshold]
        else:
            pool = nz
        ranked = sorted(
            pool.tolist(),
            key=lambda i: (-round(float(fused[i]), SCORE_DECIMALS), self._ref_sort_keys[i]),
        )
        out: list[Candidate] = []
        seen: set[tuple[str, str]] = set()
        for i in ranked:
            d = self.docs[i]
            if d.kind not in allowed:
                continue
            key = (d.kind, d.ref)
            if key in seen:
                continue
            seen.add(key)
            out.append(Candidate(d.kind, d.ref, d.source_key, round(float(fused[i]), SCORE_DECIMALS), d.text))
            if len(out) >= k:
                break
        return out


def _ref_key(ref: str) -> tuple[int, ...]:
    return tuple(int(p) for p in ref.split(":"))


# --------------------------------------------------------------------------- loading the corpus files


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def docs_from_data(translations_dir: Path) -> tuple[list[_Doc], dict[str, Any]]:
    """Read the files written by ``corpus/fetch_translations.py`` into index documents.

    Quran: text = index_text = the ayah translation verbatim. Hadith: text = ``hadeeth`` verbatim;
    index_text additionally carries HadeethEnc's own ``title`` line (usually the famous short matn),
    which helps recall but is never returned as translation text.
    """
    docs: list[_Doc] = []
    counts: dict[str, int] = {}
    for key, prio in sorted(QURAN_SOURCE_PRIORITY.items(), key=lambda kv: kv[1]):
        p = translations_dir / f"quranenc_{key}.jsonl"
        if not p.exists():
            continue
        rows = _read_jsonl(p)
        for r in rows:
            text = str(r["translation"])
            docs.append(_Doc("quran", f"{int(r['sura'])}:{int(r['aya'])}", key, prio, text, text))
        counts[key] = len(rows)
    p = translations_dir / "hadeethenc_en.jsonl"
    if p.exists():
        rows = _read_jsonl(p)
        for r in rows:
            hadeeth = str(r["hadeeth"])
            title = str(r.get("title") or "")
            docs.append(
                _Doc("hadith", str(int(r["id"])), HADITH_SOURCE_KEY, 1, hadeeth, f"{title}\n{hadeeth}")
            )
        counts[HADITH_SOURCE_KEY] = len(rows)
    if not docs:
        raise FileNotFoundError(
            f"no translation files in {translations_dir} (run corpus/fetch_translations.py)"
        )
    return docs, {"source_counts": counts}


# --------------------------------------------------------------------------- module-level convenience


def default_index_path() -> Path:
    return Path(__file__).resolve().parents[3] / "corpus" / "index" / "translations.pkl"


@lru_cache(maxsize=2)
def _cached(path: Path) -> TranslationIndex:
    return TranslationIndex.load(path)


def load_default(path: Path | None = None) -> TranslationIndex:
    """Process-wide cached index (loaded once per path; ~15 k docs, ≈0.1 s)."""
    return _cached(path or default_index_path())


def candidates(text: str, k: int = 5) -> list[Candidate]:
    """``TranslationIndex.load(corpus/index/translations.pkl).candidates(text, k)`` with caching."""
    return load_default().candidates(text, k)
