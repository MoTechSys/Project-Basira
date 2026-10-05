"""Exact phrase matching over the FULL positional index (ADR-002 §2: RRF top-k can drop the exact hit, so exact never goes through it).

Given the loose tokens of a quote, find every global position where the tokens
appear consecutively, inside one stream document (no crossing of surah / record
boundaries). Then apply the STRICT gate: the strict tokens of the quote must
equal the strict tokens of the matched window, otherwise the hit is reported as
``strict_ok=False`` (→ ``needs_review`` with a diff, never ``found``).

Complexity: O(Σ postings of the rarest token) with numpy set intersection.
Measured: <5 ms per quote on the 4.5 M-token corpus.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.store import Record, Store


@dataclass(frozen=True, slots=True)
class ExactHit:
    rec: Record
    tok_start: int  # index of first matched token inside the record's display tokens (or -1 if variant-2)
    tok_end: int  # exclusive
    strict_ok: bool
    gpos: int  # global position of the first token
    variant: int  # 0 = display rasm, 1 = simple rasm (Quran only)


def find_exact(store: Store, loose: list[str], strict: list[str]) -> list[ExactHit]:
    n = len(loose)
    if n == 0:
        return []
    ids = [store.token_id(t) for t in loose]
    if any(i < 0 for i in ids):
        return []
    # start from the rarest token to keep the candidate set small
    sizes = [len(store.postings(i)) for i in ids]
    k = int(np.argmin(sizes))
    cand = store.postings(ids[k]).astype(np.int64) - k  # candidate start positions
    if k > 0:
        cand = cand[cand >= 0]
    for j, tid in enumerate(ids):
        if j == k or cand.size == 0:
            continue
        # postings exclude basmala tokens; for j>0 we allow tokens that sit inside
        # the basmala region? No: a quote cannot legitimately start mid-basmala and
        # continue — but it CAN start before and cross into ayah text only via the
        # basmala itself, which is display-only. So plain equality on G suffices for j>0.
        pos = cand + j
        valid = pos < len(store.G)
        cand = cand[valid]
        pos = pos[valid]
        cand = cand[store.G[pos] == tid]
    if cand.size == 0:
        return []
    # same stream document across the whole window
    last = cand + (n - 1)
    cand = cand[store.g_doc[cand] == store.g_doc[last]]
    if cand.size == 0:
        return []

    sids = np.asarray([store.strict_id(t) for t in strict], dtype=np.int64)
    all_known = bool((sids >= 0).all())
    hits: list[ExactHit] = []
    for g in cand.tolist():
        # E-024: each token passes the strict gate if it equals the record's spelling in EITHER
        # Quran rasm at that position (GS2 == GS outside the Quran, so hadith is unaffected).
        strict_ok = all_known and bool(((store.GS[g : g + n] == sids) | (store.GS2[g : g + n] == sids)).all())
        rec = store.record_of_pos(g)
        if rec.corpus == "tanzil" and rec.g2_start <= g < rec.g2_start + rec.g2_len:
            if g - rec.g2_start < rec.offset:
                continue  # window starts inside the display-only basmala
            hits.append(ExactHit(rec, -1, -1, strict_ok, g, 1))
        else:
            ts = g - rec.g_start
            if ts < rec.offset:
                continue
            hits.append(ExactHit(rec, ts, ts + n, strict_ok, g, 0))
    return hits


def records_covering(store: Store, gpos: int, n: int) -> list[Record]:
    """Records whose token range intersects the global window [gpos, gpos+n) (cross-ayah quotes)."""
    out: list[Record] = []
    seen: set[int] = set()
    for g in range(gpos, gpos + n):
        r = int(store.g_rec[g])
        if r not in seen:
            seen.add(r)
            out.append(store.records[r])
    return out


def dedupe_hits(hits: list[ExactHit]) -> list[ExactHit]:
    """Collapse hits to one per (record, position); the strict gate passes if ANY rasm passes.

    Quran is indexed in two rasms (Uthmani display + simple). A quote written in
    common orthography («شيء») strictly equals the simple rasm while the Uthmani
    display has «شىء»; that is still a byte-faithful quote → strict_ok=True.
    Variant-0 hits carry token offsets for highlighting and are preferred as the
    carrier; a variant-1 hit only upgrades ``strict_ok``.
    """
    by_rec: dict[int, list[ExactHit]] = {}
    for h in hits:
        by_rec.setdefault(h.rec.idx, []).append(h)
    out: list[ExactHit] = []
    for group in by_rec.values():
        v0 = [h for h in group if h.variant == 0]
        v1 = [h for h in group if h.variant == 1]
        any_strict = any(h.strict_ok for h in group)
        if v0:
            seen: set[int] = set()
            for h in sorted(v0, key=lambda h: h.tok_start):
                if h.tok_start in seen:
                    continue
                seen.add(h.tok_start)
                out.append(ExactHit(h.rec, h.tok_start, h.tok_end, h.strict_ok or any_strict, h.gpos, 0))
        else:
            h = v1[0]
            out.append(ExactHit(h.rec, -1, -1, any_strict, h.gpos, 1))
    out.sort(key=lambda h: (not h.strict_ok, h.rec.idx, h.tok_start))
    return out


def mixed_rasm_hit(store: Store, loose: list[str], strict: list[str], gpos: int) -> ExactHit | None:
    """E-024 (loose tier). A quote that mixes Uthmani and simple spellings *of different words*
    («آمنا» simple next to «إسحق» Uthmani) matches neither stream token-for-token, so ``find_exact``
    cannot see it and the fuzzy stage reports a near-miss. Given a candidate window start (from the
    fuzzy stage, same length as the quote), accept the window iff EVERY position equals the quote's
    loose token in one of the two rasms; the strict gate is then applied the same way. Quran only
    (``G2 == G`` elsewhere, so hadith windows can only pass if they were exact already)."""
    n = len(loose)
    if (
        n == 0
        or gpos < 0
        or gpos + n > len(store.G)
        or int(store.g_doc[gpos]) != int(store.g_doc[gpos + n - 1])
    ):
        return None
    rec = store.record_of_pos(gpos)
    ids = np.asarray([store.token_id(t) for t in loose], dtype=np.int64)
    g = store.G[gpos : gpos + n]
    g2 = store.G2[gpos : gpos + n]
    pure = bool((g == ids).all()) or bool((g2 == ids).all())  # find_exact already handles these
    if rec.corpus != "tanzil" or (ids < 0).any() or pure or not bool(((g == ids) | (g2 == ids)).all()):
        return None
    sids = np.asarray([store.strict_id(t) for t in strict], dtype=np.int64)
    strict_ok = bool((sids >= 0).all()) and bool(
        ((store.GS[gpos : gpos + n] == sids) | (store.GS2[gpos : gpos + n] == sids)).all()
    )
    variant2 = rec.g2_start <= gpos < rec.g2_start + rec.g2_len
    ts = gpos - (rec.g2_start if variant2 else rec.g_start)
    if ts < rec.offset:
        return None  # window starts inside the display-only basmala
    return (
        ExactHit(rec, -1, -1, strict_ok, gpos, 1)
        if variant2
        else ExactHit(rec, ts, ts + n, strict_ok, gpos, 0)
    )
