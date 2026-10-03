"""Corpus-anchored quote detector (seed-and-extend, as BLAST does for sequences).

Rules find quotes that are *marked* (brackets, «قال تعالى», «رواه»…). Real posts and LLM answers also
quote scripture with no mark at all. This detector asks the index directly: every run of ≥ ``seed``
consecutive tokens of the input that occurs verbatim (loose tier) somewhere in the corpus is a seed;
seeds are extended token by token while the corpus continues to agree, merged, and emitted as
spans. Because it only fires on text that literally exists in the Mushaf / hadith books, it cannot
invent a quote; the normal pipeline then decides the status as for any other span.

Cost: one posting-list intersection per seed window (numpy, the same primitive as the exact matcher);
≈ 2–6 ms for a 5 000-char post.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.normalize import Token, tokenize
from app.store import Store

# very common function words: a seed made only of these is meaningless («قال الله إن», «من الذين»)
_STOP = frozenset(
    [
        "من",
        "في",
        "على",
        "علي",
        "الي",
        "إلى",
        "الى",
        "عن",
        "ان",
        "إن",
        "أن",
        "و",
        "او",
        "أو",
        "ما",
        "لا",
        "لم",
        "لن",
        "قد",
        "ثم",
        "هو",
        "هي",
        "هم",
        "الله",
        "قال",
        "كان",
        "الذي",
        "التي",
        "الذين",
        "ذلك",
        "هذا",
        "هذه",
        "به",
        "له",
        "لهم",
        "بها",
        "كل",
        "يا",
        "اذا",
        "إذا",
    ]
)


# honorific / formulaic words that occur verbatim in thousands of records and are never a quote on their own
_HONOR = frozenset(
    [
        "صلي",
        "عليه",
        "وسلم",
        "السلام",
        "رضي",
        "عنه",
        "عنها",
        "عنهما",
        "تعالي",
        "سبحانه",
        "وتعالي",
        "عز",
        "وجل",
        "رسول",
        "النبي",
        "ورحمه",
        "وبركاته",
        "عليكم",
        "محمد",
        "الرحمن",
        "الرحيم",
        "بسم",
    ]
)


@dataclass(slots=True)
class AnchorSpan:
    start: int  # char offsets into the original text
    end: int
    corpus: str  # tanzil | ohd | hadeethenc  (corpus of the longest supporting run)
    n_tokens: int


def _occurs(store: Store, ids: list[int]) -> np.ndarray:
    """Start positions where the id sequence occurs contiguously in the global stream."""
    if any(i < 0 for i in ids):
        return np.empty(0, dtype=np.int64)
    sizes = [len(store.postings(i)) for i in ids]
    k = int(np.argmin(sizes))
    cand = store.postings(ids[k]).astype(np.int64) - k
    cand = cand[cand >= 0]
    for j, tid in enumerate(ids):
        if j == k or cand.size == 0:
            continue
        pos = cand + j
        ok = pos < len(store.G)
        cand, pos = cand[ok], pos[ok]
        cand = cand[store.G[pos] == tid]
    if cand.size:
        last = cand + (len(ids) - 1)
        cand = cand[store.g_doc[cand] == store.g_doc[last]]
    return cand


def detect(store: Store, text: str, *, seed: int = 4, max_cand: int = 4000) -> list[AnchorSpan]:
    toks: list[Token] = tokenize(text)
    ids = [store.token_id(t.loose) for t in toks]
    n = len(toks)
    out: list[AnchorSpan] = []
    i = 0
    while i + seed <= n:
        win = ids[i : i + seed]
        if any(x < 0 for x in win) or all(toks[i + k].loose in _STOP for k in range(seed)):
            i += 1
            continue
        cand = _occurs(store, win)
        if cand.size == 0 or cand.size > max_cand:
            i += 1
            continue
        # extend while at least one occurrence continues to agree
        j = i + seed
        live = cand
        while j < n and ids[j] >= 0 and live.size:
            nxt = live + (j - i)
            ok = nxt < len(store.G)
            live2 = live[ok][store.G[nxt[ok]] == ids[j]]
            if live2.size == 0:
                break
            # stay inside the same stream document (an ayah run / one hadith)
            live2 = live2[store.g_doc[live2] == store.g_doc[live2 + (j - i)]]
            if live2.size == 0:
                break
            live = live2
            j += 1
        g = int(live[0])
        corpus = store.record_of_pos(g).corpus
        content = [t.loose for t in toks[i:j] if t.loose not in _STOP and t.loose not in _HONOR]
        need = 4 if corpus == "tanzil" else 6  # hadith prose is far more formulaic → longer seed
        if j - i >= need and len(content) >= 3:
            out.append(AnchorSpan(toks[i].start, toks[j - 1].end, corpus, j - i))
        i = j
    return _merge(out, text)


def _merge(spans: list[AnchorSpan], text: str) -> list[AnchorSpan]:
    """Join anchors separated only by punctuation/space (an ayah quoted across a comma)."""
    if not spans:
        return []
    merged = [spans[0]]
    for s in spans[1:]:
        last = merged[-1]
        gap = text[last.end : s.start]
        if len(gap) <= 3 and all(not ("\u0621" <= c <= "\u064a") for c in gap) and s.corpus == last.corpus:
            merged[-1] = AnchorSpan(last.start, s.end, last.corpus, last.n_tokens + s.n_tokens)
        else:
            merged.append(s)
    return merged
