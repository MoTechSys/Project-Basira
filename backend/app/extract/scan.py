"""Deterministic whole-text Quran scan (E-030, G-5).

Problem: da'wah posts quote ayat with **no introducer and no brackets** («اللهم ربنا آتنا في
الدنيا حسنة …», «وما توفيقي إلا بالله»). The rule extractor and the LLM extractor both key on
markers, so such ayat were silently skipped — contradicting the project promise of a
*deterministic Quran sweep*.

Method (pure index arithmetic, no model, O(tokens · k)):
  1. tokenize the whole text (loose tier);
  2. slide a window of ``min_tokens`` loose tokens; for each window ask the positional index
     whether the sequence occurs **inside a Quran stream document** (surah-local, so an
     accidental cross-surah run never counts);
  3. when a seed window hits, extend greedily to the right while the longer sequence still hits;
  4. emit a ``RuleSpan(kind="quran", marked=False)`` over the maximal run, skipping anything
     already covered by an existing span.

Why ``min_tokens`` = 4 by default: on the 77k-token Quran, 4-gram collisions with ordinary Arabic
prose are rare (common religious formulae such as «بسم الله الرحمن الرحيم» are *real* ayat and
are meant to surface). 3-grams («الحمد لله رب», «إن الله مع») collide with everyday speech and
would flood posts with found-cards — tunable via ``QURAN_SCAN_MIN_TOKENS``.

Determinism: output depends only on the index build and the input string.
"""

from __future__ import annotations

import numpy as np

from app.extract.rules import RuleSpan
from app.normalize import tokenize
from app.store import Store


def _positions(store: Store, ids: list[int]) -> np.ndarray:
    """Global start positions where the loose-id sequence occurs inside one stream doc."""
    if not ids or any(i < 0 for i in ids):
        return np.empty(0, dtype=np.int64)
    sizes = [len(store.postings(i)) for i in ids]
    k = int(np.argmin(sizes))
    cand = store.postings(ids[k]).astype(np.int64) - k
    if k > 0:
        cand = cand[cand >= 0]
    n = len(ids)
    for j, tid in enumerate(ids):
        if j == k or cand.size == 0:
            continue
        pos = cand + j
        ok = pos < len(store.G)
        cand = cand[ok]
        pos = pos[ok]
        cand = cand[store.G[pos] == tid]
    if cand.size == 0:
        return cand
    last = cand + (n - 1)
    last = np.minimum(last, len(store.G) - 1)
    cand = cand[store.g_doc[cand] == store.g_doc[last]]
    # Quran only
    if cand.size:
        recs = store.g_rec[cand]
        keep = np.fromiter(
            (store.records[int(r)].corpus == "tanzil" for r in recs), dtype=bool, count=len(recs)
        )
        cand = cand[keep]
    return np.asarray(cand, dtype=np.int64)


def scan_quran_unmarked(
    store: Store, text: str, existing: list[RuleSpan], *, min_tokens: int = 4, max_hits: int = 12
) -> list[RuleSpan]:
    toks = tokenize(text)
    if len(toks) < min_tokens:
        return []
    ids = [store.token_id(t.loose) for t in toks]
    out: list[RuleSpan] = []

    def covered(a: int, b: int) -> bool:
        return any(sp.start < b and a < sp.end for sp in existing + out)

    i = 0
    n = len(toks)
    while i + min_tokens <= n and len(out) < max_hits:
        seed = ids[i : i + min_tokens]
        if any(x < 0 for x in seed) or _positions(store, seed).size == 0:
            i += 1
            continue
        # extend right while still a Quran run
        j = i + min_tokens
        while j < n and ids[j] >= 0 and _positions(store, ids[i : j + 1]).size > 0:
            j += 1
        a, b = toks[i].start, toks[j - 1].end
        if not covered(a, b):
            out.append(RuleSpan(a, b, "quran", False, extras={"via": "quran_scan"}))
        i = j
    return out
