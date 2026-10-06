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


# E-062 — phrase-rarity acceptance for short unmarked runs. A run of ≥ RARE_MIN_TOKENS tokens that occurs
# verbatim at most RARE_MAX_OCC times in the whole corpus is a quotation, however common its words are
# taken one by one: «إنما الأعمال بالنيات» occurs 7×, «إن الله مع الصابرين» 2×, «لا ضرر ولا ضرار» 9× — while
# formulaic prose is three orders of magnitude more frequent («صلى الله عليه وسلم» 92 083×, «حدثنا عبد الله بن»
# 3 248×, «لا إله إلا الله» 1 191×, «يا أيها الذين آمنوا» 250×, «بسم الله الرحمن الرحيم» 117×). Measured 2026-10-06 on the
# full index; the band between the two populations is wide (27 ↔ 105). One content word is still required
# so that a rare run made only of particles can never anchor. Guarded by eval-full false-alarm 0/500.
RARE_MIN_TOKENS = 3
RARE_MAX_OCC = 60
# isnad vocabulary: a rare run made of chain words («نافع عن ابن عمر») is a narrator list, not a matn. Such
# runs stay with the main rule (6 content tokens) so B05 wording decides what to say about them.
_ISNAD = frozenset(
    [
        "عن",
        "وعن",
        "بن",
        "ابن",
        "ابي",
        "أبي",
        "ابو",
        "أبو",
        "حدثنا",
        "حدثني",
        "اخبرنا",
        "أخبرنا",
        "اخبرني",
        "أخبرني",
        "قال",
        "قالت",
        "سمعت",
        "ان",
        "أن",
        "إن",
        "انه",
        "أنه",
    ]
)


def detect(store: Store, text: str, *, seed: int = 4, max_cand: int = 4000) -> list[AnchorSpan]:
    toks: list[Token] = tokenize(text)
    ids = [store.token_id(t.loose) for t in toks]
    n = len(toks)
    out: list[AnchorSpan] = []
    i = 0
    min_seed = min(seed, RARE_MIN_TOKENS)
    while i + min_seed <= n:
        # the seed window is `seed` tokens when available, else the shorter rare-phrase seed (E-062)
        s = seed if i + seed <= n else min_seed
        win = ids[i : i + s]
        if any(x < 0 for x in win) or all(toks[i + k].loose in _STOP for k in range(s)):
            i += 1
            continue
        cand = _occurs(store, win)
        if cand.size == 0 or cand.size > max_cand:
            i += 1
            continue
        # extend while at least one occurrence continues to agree
        j = i + s
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
        # extend BACKWARDS as well: the seed may have started one or more tokens late because the
        # leading words were all stop-words («ان الله علي كل …» seeds at «الله»); the quote still
        # begins where the corpus agreement begins, and a verdict on a truncated quote is a worse
        # verdict (E-062).
        i0 = i
        while i0 > 0 and ids[i0 - 1] >= 0 and live.size:
            prev = live - 1
            ok = prev >= 0
            live2 = live[ok][store.G[prev[ok]] == ids[i0 - 1]]
            if live2.size == 0:
                break
            live2 = live2[store.g_doc[live2 - 1] == store.g_doc[live2]]
            if live2.size == 0:
                break
            live = live2 - 1
            i0 -= 1
        i = i0
        g = int(live[0])
        corpus = store.record_of_pos(g).corpus
        content = [t.loose for t in toks[i:j] if t.loose not in _STOP and t.loose not in _HONOR]
        need = 4 if corpus == "tanzil" else 6  # hadith prose is far more formulaic → longer seed
        if (
            (j - i >= need and len(content) >= 3)
            # E-061: a run that IS a complete ayah («قل هو الله أحد») is a quote however common its
            # words are — the Mushaf's own ayah boundary is the evidence, not word rarity.
            or _covers_whole_ayah(store, live, j - i)
            # E-062: a short run that is RARE as a phrase («إنما الأعمال بالنيات», «لا ضرر ولا ضرار») and not isnad-shaped
            or (
                j - i >= RARE_MIN_TOKENS
                and len(content) >= 1
                and live.size <= RARE_MAX_OCC
                and not _isnad_shaped(toks[i:j])
            )
        ):
            out.append(AnchorSpan(toks[i].start, toks[j - 1].end, corpus, j - i))
        i = j
    return _merge(out, text)


def _isnad_shaped(run: list[Token]) -> bool:
    """True when the run reads like a narrator chain: half or more of its tokens are chain words
    («عن / بن / حدثنا / قال») or it contains «عن … عن». Names between them are not a matn."""
    words = [t.loose for t in run]
    chain = sum(w in _ISNAD for w in words)
    return chain * 2 >= len(words) or words.count("عن") >= 2


def _covers_whole_ayah(store: Store, starts: np.ndarray, n: int) -> bool:
    """True iff some occurrence of the run spans an entire Quran ayah (after the basmala offset),
    i.e. the run starts at the ayah's first indexed token and ends at its last. Quran only: a
    complete ayah is a self-delimiting unit; a hadith matn has no such boundary."""
    for g in starts.tolist()[:64]:  # the run is short by construction; cap the scan
        rec = store.record_of_pos(g)
        if rec.corpus != "tanzil":
            continue
        for base, length in ((rec.g_start, rec.g_len), (rec.g2_start, rec.g2_len)):
            if length > 0 and g == base + rec.offset and n == length - rec.offset:
                return True
    return False


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
