"""In-memory corpus store: records + one global token stream + positional index.

Design (ADR-002 §2/§3):

* All indexed text lives in ONE global token stream ``G`` (loose ids) with a
  parallel strict stream ``GS`` and per-position ``g_rec`` (record index) and
  ``g_doc`` (stream-document id). Quran is streamed **per surah per rasm** so an
  exact phrase may cross ayah boundaries but never surah boundaries. Every
  hadith record is its own stream document.
* ``postings[token_id]`` = sorted global positions of that loose token,
  **excluding** basmala tokens of ayah 1 (offset ``o``). This lets
  ``match.exact`` verify a phrase for *all* candidates at once with numpy.
* Retrieval documents (for BM25 / trigrams) are ayah-level for Quran and
  record-level for hadith; ``rdoc_*`` arrays describe them.

Memory: ≈ 4.7 M tokens → ~40 B/token in numpy ≈ 190 MB + display strings.
Load time from records.jsonl ≈ 6–8 s (pure Python tokenization is done at build).
"""

from __future__ import annotations

import json
import logging
import time
from array import array
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
import numpy.typing as npt

from app.normalize import char_trigrams

log = logging.getLogger(__name__)

Corpus = Literal["tanzil", "ohd", "hadeethenc"]
I32 = npt.NDArray[np.int32]


@dataclass(slots=True)
class Record:
    idx: int
    corpus: Corpus
    display: str  # verbatim corpus field shown to users
    g_start: int  # first global position of the display-variant tokens
    g_len: int
    offset: int  # tokens at the head that are display-only (basmala)
    # Quran
    surah: int = 0
    ayah: int = 0
    text_simple: str = ""
    g2_start: int = -1  # simple-rasm variant tokens (no spans)
    g2_len: int = 0
    # OHD
    book: str = ""
    num: int = 0
    matn: int = 0
    # HadeethEnc
    henc_id: int = 0
    title: str = ""
    hadith_text: str = ""
    grade: str = ""
    takhrij: str = ""
    link: str = ""

    @property
    def ref(self) -> dict[str, Any]:
        if self.corpus == "tanzil":
            return {"surah": self.surah, "ayah": self.ayah}
        if self.corpus == "ohd":
            return {"book": self.book, "num": self.num, "numbering": "ohd"}
        return {"id": self.henc_id}


@dataclass(slots=True)
class RetrievalDoc:
    rec: int
    g_start: int  # already past the basmala offset
    g_len: int


@dataclass
class Store:
    records: list[Record]
    vocab: dict[str, int]  # loose token → id
    svocab: dict[str, int]  # strict token → id
    G: I32  # loose ids per global position
    GS: I32  # strict ids per global position
    GS2: I32  # strict id of the SAME word in the other Quran rasm (E-024); == GS outside Quran
    G2: I32  # loose id of the same word in the other Quran rasm (E-024); == G outside Quran
    span_start: I32  # char offsets into the record display text (−1 for variant-2 tokens)
    span_end: I32
    g_rec: I32
    g_doc: I32
    post_offsets: I32  # CSR offsets into post_positions by token id (len = |vocab|+1)
    post_positions: I32
    rdocs_quran: list[RetrievalDoc]
    rdocs_hadith: list[RetrievalDoc]
    meta: dict[str, Any]
    by_key: dict[tuple[Any, ...], int] = field(default_factory=dict)
    surah_names: dict[int, tuple[str, str]] = field(default_factory=dict)

    # ---------------------------------------------------------------- helpers

    def token_id(self, loose: str) -> int:
        return self.vocab.get(loose, -1)

    def strict_id(self, strict: str) -> int:
        return self.svocab.get(strict, -1)

    def postings(self, token_id: int) -> I32:
        if token_id < 0:
            return np.empty(0, dtype=np.int32)
        a, b = self.post_offsets[token_id], self.post_offsets[token_id + 1]
        return self.post_positions[a:b]

    def record_of_pos(self, gpos: int) -> Record:
        return self.records[int(self.g_rec[gpos])]

    def loose_tokens_of(self, rec: Record) -> list[str]:
        inv = self._inv_vocab
        return [inv[int(t)] for t in self.G[rec.g_start : rec.g_start + rec.g_len]]

    def strict_tokens_of(self, rec: Record) -> list[str]:
        inv = self._inv_svocab
        return [inv[int(t)] for t in self.GS[rec.g_start : rec.g_start + rec.g_len]]

    def strict_alt_tokens_of(self, rec: Record) -> list[str]:
        """Strict tokens of the record's twin rasm, word-aligned (E-024). Equals ``strict_tokens_of``
        for hadith and for the 363 ayat whose rasms are not word-aligned."""
        inv = self._inv_svocab
        return [inv[int(t)] for t in self.GS2[rec.g_start : rec.g_start + rec.g_len]]

    def strict_tokens_range(self, gpos: int, n: int) -> list[str]:
        """Strict tokens of an arbitrary global window (may span several ayat of one surah)."""
        inv = self._inv_svocab
        return [inv[int(t)] for t in self.GS[gpos : gpos + n]]

    def strict_alt_tokens_range(self, gpos: int, n: int) -> list[str]:
        inv = self._inv_svocab
        return [inv[int(t)] for t in self.GS2[gpos : gpos + n]]

    def spans_range(self, rec: Record, gpos: int, n: int) -> list[tuple[int, int]]:
        """Char spans into ``rec.display`` for the window; positions outside ``rec`` → (-1, -1)."""
        out: list[tuple[int, int]] = []
        for g in range(gpos, gpos + n):
            if rec.g_start <= g < rec.g_start + rec.g_len:
                out.append((int(self.span_start[g]), int(self.span_end[g])))
            else:
                out.append((-1, -1))
        return out

    def spans_of(self, rec: Record) -> list[tuple[int, int]]:
        s = self.span_start[rec.g_start : rec.g_start + rec.g_len]
        e = self.span_end[rec.g_start : rec.g_start + rec.g_len]
        return list(zip(s.tolist(), e.tolist(), strict=True))

    def lookup(self, corpus: Corpus, **ref: Any) -> Record | None:
        if corpus == "tanzil":
            key: tuple[Any, ...] = ("tanzil", ref["surah"], ref["ayah"])
        elif corpus == "ohd":
            key = ("ohd", ref["book"], ref["num"])
        else:
            key = ("hadeethenc", ref["id"])
        i = self.by_key.get(key)
        return self.records[i] if i is not None else None

    @property
    def counts(self) -> dict[str, int]:
        return dict(self.meta.get("counts", {}))

    def __post_init__(self) -> None:
        self._inv_vocab = [""] * len(self.vocab)
        for k, v in self.vocab.items():
            self._inv_vocab[v] = k
        self._inv_svocab = [""] * len(self.svocab)
        for k, v in self.svocab.items():
            self._inv_svocab[v] = k
        for r in self.records:
            if r.corpus == "tanzil":
                self.by_key[("tanzil", r.surah, r.ayah)] = r.idx
            elif r.corpus == "ohd":
                self.by_key[("ohd", r.book, r.num)] = r.idx
            else:
                self.by_key[("hadeethenc", r.henc_id)] = r.idx
        # token → trigram ids (lazily built by the trigram index)
        self.trigram_vocab: dict[str, int] = {}

    def trigram_ids(self, loose: str) -> list[int]:
        out = []
        for g in char_trigrams(loose):
            i = self.trigram_vocab.get(g)
            if i is None:
                i = len(self.trigram_vocab)
                self.trigram_vocab[g] = i
            out.append(i)
        return out


# ------------------------------------------------------------------------ loader

_PLACEHOLDER = Record(-1, "tanzil", "", 0, 0, 0)


def load_store(index_dir: Path) -> Store:
    t0 = time.time()
    meta = json.loads((index_dir / "meta.json").read_text(encoding="utf-8"))
    records: list[Record] = []
    vocab: dict[str, int] = {}
    svocab: dict[str, int] = {}
    G = array("i")
    GS = array("i")
    GS2 = array("i")
    G2 = array("i")
    ss = array("i")
    se = array("i")
    g_rec = array("i")
    g_doc = array("i")
    post_pairs_tok = array("i")
    post_pairs_pos = array("i")
    rdocs_quran: list[RetrievalDoc] = []
    rdocs_hadith: list[RetrievalDoc] = []
    doc_id = -1

    def push_tokens(
        loose: list[str], strict: list[str], spans: list[int] | None, rec_idx: int, doc: int, offset: int
    ) -> tuple[int, int]:
        start = len(G)
        for i, (lo, st) in enumerate(zip(loose, strict, strict=True)):
            tid = vocab.setdefault(lo, len(vocab))
            sid = svocab.setdefault(st, len(svocab))
            G.append(tid)
            GS.append(sid)
            GS2.append(sid)
            G2.append(tid)
            if spans is not None:
                ss.append(spans[2 * i])
                se.append(spans[2 * i + 1])
            else:
                ss.append(-1)
                se.append(-1)
            g_rec.append(rec_idx)
            g_doc.append(doc)
            if i >= offset:
                post_pairs_tok.append(tid)
                post_pairs_pos.append(start + i)
        return start, len(loose)

    pending_surah: list[dict[str, Any]] = []

    def flush_surah() -> None:
        """Push one surah: all ayat in the display rasm first, then all ayat in the simple rasm.

        Each rasm forms ONE contiguous stream document, so exact phrases may cross ayah
        boundaries (never surah boundaries) — required for multi-ayah quotes.
        """
        nonlocal doc_id
        if not pending_surah:
            return
        doc_id += 1
        starts0: list[tuple[int, int]] = []
        for d in pending_surah:
            loose = d["L"].split(" ") if d["L"] else []
            strict = d["S"].split(" ") if d["S"] else []
            starts0.append(push_tokens(loose, strict, d["P"], d["_idx"], doc_id, int(d["o"])))
        doc_id += 1
        starts1: list[tuple[int, int]] = []
        for d in pending_surah:
            loose2 = d["L2"].split(" ") if d["L2"] else []
            strict2 = d["S2"].split(" ") if d["S2"] else []
            starts1.append(push_tokens(loose2, strict2, None, d["_idx"], doc_id, int(d["o"])))
        for d, (g_start, g_len), (g2_start, g2_len) in zip(pending_surah, starts0, starts1, strict=True):
            offset = int(d["o"])
            if g_len == g2_len:
                # E-024: word-aligned rasms → each position also knows its twin's strict form, so a quote
                # mixing Uthmani and simple spellings («وأوحى … كما») still passes the strict gate.
                # Ayat whose word counts differ («يأيها» vs «يا أيها», 363 of 6236) keep GS2 == GS.
                for k in range(g_len):
                    GS2[g_start + k] = GS[g2_start + k]
                    GS2[g2_start + k] = GS[g_start + k]
                    G2[g_start + k] = G[g2_start + k]
                    G2[g2_start + k] = G[g_start + k]
            rec = Record(
                d["_idx"],
                "tanzil",
                d["tu"],
                g_start,
                g_len,
                offset,
                surah=int(d["s"]),
                ayah=int(d["a"]),
                text_simple=d["ts"],
                g2_start=g2_start,
                g2_len=g2_len,
            )
            records[d["_idx"]] = rec
            rdocs_quran.append(RetrievalDoc(d["_idx"], g_start + offset, g_len - offset))
            rdocs_quran.append(RetrievalDoc(d["_idx"], g2_start + offset, g2_len - offset))
        pending_surah.clear()

    with (index_dir / "records.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            idx = len(records)
            c = d["c"]
            if c == "tanzil":
                if pending_surah and pending_surah[-1]["s"] != d["s"]:
                    flush_surah()
                d["_idx"] = idx
                pending_surah.append(d)
                records.append(_PLACEHOLDER)
                continue
            flush_surah()
            loose = d["L"].split(" ") if d["L"] else []
            strict = d["S"].split(" ") if d["S"] else []
            if c == "ohd":
                doc_id += 1
                g_start, g_len = push_tokens(loose, strict, d["P"], idx, doc_id, 0)
                matn = int(d["m"])
                rec = Record(idx, "ohd", d["td"], g_start, g_len, 0, book=d["b"], num=int(d["n"]), matn=matn)
                rdocs_hadith.append(RetrievalDoc(idx, g_start, g_len))
                if matn > 0:  # R2: matn-only retrieval doc so sanad tokens do not dilute BM25
                    rdocs_hadith.append(RetrievalDoc(idx, g_start + matn, g_len - matn))
            else:
                doc_id += 1
                g_start, g_len = push_tokens(loose, strict, d["P"], idx, doc_id, 0)
                rec = Record(
                    idx,
                    "hadeethenc",
                    d["td"],
                    g_start,
                    g_len,
                    0,
                    henc_id=int(d["id"]),
                    title=d["title"],
                    hadith_text=d["ht"],
                    grade=d["g"],
                    takhrij=d["tk"],
                    link=d["u"],
                )
                rdocs_hadith.append(RetrievalDoc(idx, g_start, g_len))
            records.append(rec)
        flush_surah()
    if any(r is _PLACEHOLDER for r in records):
        raise RuntimeError("store: unresolved placeholder record")

    # CSR postings sorted by (token, position)
    tok_arr = np.frombuffer(post_pairs_tok, dtype=np.int32)
    pos_arr = np.frombuffer(post_pairs_pos, dtype=np.int32)
    order = np.lexsort((pos_arr, tok_arr))
    tok_sorted = tok_arr[order]
    post_positions = pos_arr[order]
    counts = np.bincount(tok_sorted, minlength=len(vocab)).astype(np.int32)
    post_offsets = np.zeros(len(vocab) + 1, dtype=np.int32)
    np.cumsum(counts, out=post_offsets[1:])

    store = Store(
        records=records,
        vocab=vocab,
        svocab=svocab,
        G=np.frombuffer(G, dtype=np.int32).copy(),
        GS=np.frombuffer(GS, dtype=np.int32).copy(),
        GS2=np.frombuffer(GS2, dtype=np.int32).copy(),
        G2=np.frombuffer(G2, dtype=np.int32).copy(),
        span_start=np.frombuffer(ss, dtype=np.int32).copy(),
        span_end=np.frombuffer(se, dtype=np.int32).copy(),
        g_rec=np.frombuffer(g_rec, dtype=np.int32).copy(),
        g_doc=np.frombuffer(g_doc, dtype=np.int32).copy(),
        post_offsets=post_offsets,
        post_positions=post_positions,
        rdocs_quran=rdocs_quran,
        rdocs_hadith=rdocs_hadith,
        meta=meta,
    )
    store.surah_names = _load_surah_names(index_dir)
    log.info(
        "store loaded: %d records, %d tokens, |vocab|=%d in %.1fs",
        len(records),
        len(G),
        len(vocab),
        time.time() - t0,
    )
    return store


def _load_surah_names(index_dir: Path) -> dict[int, tuple[str, str]]:
    p = index_dir.parent / "surah_names.json"
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    return {int(k): (v["ar"], v["en"]) for k, v in raw.items()}
