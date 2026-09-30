"""Sparse retrieval channels (BM25 over loose words; TF over char 3-grams) + RRF fusion.

Built once at startup from ``Store.rdocs_*`` (BUILD_SPEC §3.3, values marked
«initial»). Both channels are CSR inverted indexes in numpy; scoring one query
is a handful of vectorised gathers + ``np.add.at``.

Vectors channel is intentionally absent (ADR-002 §7, ``RETRIEVAL_VECTORS=off``).
"""

from __future__ import annotations

import logging
import time
from array import array
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from app.normalize import char_trigrams
from app.store import RetrievalDoc, Store

log = logging.getLogger(__name__)
F32 = npt.NDArray[np.float32]
I32 = npt.NDArray[np.int32]

K1 = 1.2
B = 0.75
WORD_DF_CUTOFF = 0.20  # ignore words in >20 % of docs
GRAM_DF_CUTOFF = 0.30  # ignore trigrams in >30 % of docs
RRF_K = 60


@dataclass(slots=True)
class Csr:
    """term → (doc, tf) postings in CSR layout."""

    offsets: I32
    docs: I32
    tfs: F32
    idf: F32
    n_terms: int


class _CsrBuilder:
    """Streams (doc, term-array) pairs into compact buffers; no per-doc Python int lists kept."""

    def __init__(self, n_terms: int) -> None:
        self.n_terms = n_terms
        self.terms = array("i")
        self.docs = array("i")
        self.tfs = array("f")
        self.n_docs = 0
        self.lengths = array("f")

    def add(self, doc: int, term_ids: I32) -> None:
        self.n_docs += 1
        self.lengths.append(float(len(term_ids)))
        if len(term_ids) == 0:
            return
        uniq, cnt = np.unique(term_ids, return_counts=True)
        self.terms.frombytes(uniq.astype(np.int32).tobytes())
        self.docs.frombytes(np.full(len(uniq), doc, dtype=np.int32).tobytes())
        self.tfs.frombytes(cnt.astype(np.float32).tobytes())

    def build(self, df_cutoff: float) -> tuple[Csr, F32]:
        t = np.frombuffer(self.terms, dtype=np.int32)
        d_arr = np.frombuffer(self.docs, dtype=np.int32)
        tf_arr = np.frombuffer(self.tfs, dtype=np.float32)
        order = np.argsort(t, kind="stable")
        t, d_arr, tf_arr = t[order], d_arr[order], tf_arr[order]
        df = np.bincount(t, minlength=self.n_terms).astype(np.float32)
        offsets = np.zeros(self.n_terms + 1, dtype=np.int32)
        np.cumsum(df.astype(np.int32), out=offsets[1:])
        idf = np.log1p((self.n_docs - df + 0.5) / (df + 0.5)).astype(np.float32)
        idf[df > df_cutoff * self.n_docs] = 0.0  # stop-terms contribute nothing
        return Csr(offsets, d_arr, tf_arr, idf, self.n_terms), np.frombuffer(
            self.lengths, dtype=np.float32
        ).copy()


class ChannelIndex:
    """One corpus half (Quran or hadith): word BM25 + trigram BM25 over the same doc list."""

    def __init__(self, store: Store, docs: list[RetrievalDoc], name: str) -> None:
        t0 = time.time()
        self.docs = docs
        self.name = name
        inv = store._inv_vocab
        # token id → trigram id array, built lazily (vocab ≈ 89 k)
        gram_cache: dict[int, I32] = {}

        def grams_of(tid: int) -> I32:
            g = gram_cache.get(tid)
            if g is None:
                ids = [
                    store.trigram_vocab.setdefault(x, len(store.trigram_vocab))
                    for x in char_trigrams(inv[tid])
                ]
                g = np.asarray(ids, dtype=np.int32)
                gram_cache[tid] = g
            return g

        words = _CsrBuilder(len(store.vocab))
        gram_rows: list[I32] = []
        for i, d in enumerate(docs):
            ids = store.G[d.g_start : d.g_start + d.g_len]
            words.add(i, ids)
            gram_rows.append(
                np.concatenate([grams_of(t) for t in ids.tolist()]) if d.g_len else np.empty(0, np.int32)
            )
        grams = _CsrBuilder(len(store.trigram_vocab) + 1)
        for i, row in enumerate(gram_rows):
            grams.add(i, row)
        del gram_rows
        self.words, self.doc_len = words.build(WORD_DF_CUTOFF)
        self.grams, self.gram_len = grams.build(GRAM_DF_CUTOFF)
        self.avg_len = float(self.doc_len.mean()) if len(docs) else 1.0
        self.avg_gram_len = float(self.gram_len.mean()) if len(docs) else 1.0
        log.info("index %s: %d docs, built in %.1fs", name, len(docs), time.time() - t0)

    # ------------------------------------------------------------------ scoring

    def _bm25(self, csr: Csr, q_terms: list[int], doc_len: F32, avg_len: float, n_docs: int) -> F32:
        scores = np.zeros(n_docs, dtype=np.float32)
        norm = K1 * (1.0 - B + B * doc_len / avg_len)
        for t in set(q_terms):
            if t < 0 or t >= csr.n_terms:
                continue
            a, b = csr.offsets[t], csr.offsets[t + 1]
            if a == b or csr.idf[t] == 0.0:
                continue
            d = csr.docs[a:b]
            tf = csr.tfs[a:b]
            contrib = csr.idf[t] * tf * (K1 + 1.0) / (tf + norm[d])
            np.add.at(scores, d, contrib)
        return scores

    def search(self, store: Store, loose: list[str], top_k: int = 50) -> list[tuple[int, float]]:
        """RRF-fused ranking; returns [(doc_index, fused_score)] sorted desc, length ≤ 2*top_k."""
        n_docs = len(self.docs)
        if n_docs == 0 or not loose:
            return []
        word_ids = [store.token_id(t) for t in loose]
        gram_ids: list[int] = []
        for t in loose:
            gram_ids.extend(store.trigram_vocab.get(g, -1) for g in char_trigrams(t))
        s_words = self._bm25(self.words, word_ids, self.doc_len, self.avg_len, n_docs)
        s_grams = self._bm25(self.grams, gram_ids, self.gram_len, self.avg_gram_len, n_docs)
        fused: dict[int, float] = {}
        for scores in (s_words, s_grams):
            k = min(top_k, n_docs)
            top = np.argpartition(-scores, k - 1)[:k]
            top = top[np.argsort(-scores[top], kind="stable")]
            for rank, d in enumerate(top.tolist()):
                if scores[d] <= 0.0:
                    break
                fused[d] = fused.get(d, 0.0) + 1.0 / (RRF_K + rank + 1)
        return sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))


class Retriever:
    def __init__(self, store: Store) -> None:
        self.quran = ChannelIndex(store, store.rdocs_quran, "quran")
        self.hadith = ChannelIndex(store, store.rdocs_hadith, "hadith")
