"""Windowed token-Levenshtein similarity over retrieval candidates (BUILD_SPEC §3.4-ب).

For each candidate doc, slide windows of length {round(0.8n), n, round(1.2n)}
over its loose tokens and compute::

    sim = 1 − Levenshtein_tokens(quote, window) / max(len(quote), len(window))

Ties prefer the shorter document (a single ayah over a multi-ayah window). The
returned window is expressed in *record token indices* so the diff/highlight
works on the record's display text; for Quran, the window is mapped back to the
ayah(s) it actually falls in (never to a retrieval-window id).
"""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz.distance import Levenshtein

from app.store import Record, RetrievalDoc, Store


@dataclass(frozen=True, slots=True)
class WindowHit:
    rec: Record
    tok_start: int  # inside the record's display tokens (variant 0) — or -1 if variant 1 (simple rasm)
    tok_end: int
    score: float
    gpos: int  # global position of window start
    win_len: int


def _window_lengths(n: int) -> list[int]:
    ls = sorted({max(1, round(0.8 * n)), n, max(1, round(1.2 * n))})
    return ls


def best_window(
    store: Store, doc: RetrievalDoc, q_ids: list[int], budget: int
) -> tuple[float, int, int] | None:
    """Return (score, gpos, win_len) of the best window in ``doc`` or None if doc is empty."""
    n = len(q_ids)
    if doc.g_len == 0 or n == 0:
        return None
    d_ids = store.G[doc.g_start : doc.g_start + doc.g_len].tolist()
    best: tuple[float, int, int] | None = None
    steps = 0
    for w in _window_lengths(n):
        if w > len(d_ids):
            # doc shorter than window: compare whole doc once
            w_eff = len(d_ids)
            dist = Levenshtein.distance(q_ids, d_ids)
            score = 1.0 - dist / max(n, w_eff)
            cand = (score, doc.g_start, w_eff)
            if best is None or cand[0] > best[0]:
                best = cand
            continue
        # cutoff prunes hopeless windows early (rapidfuzz stops when distance exceeds cutoff)
        cutoff = int(max(n, w) * 0.45)
        for i in range(0, len(d_ids) - w + 1):
            steps += 1
            if steps > budget:
                return best
            dist = Levenshtein.distance(q_ids, d_ids[i : i + w], score_cutoff=cutoff)
            if dist > cutoff:
                continue
            score = 1.0 - dist / max(n, w)
            if best is None or score > best[0] or (score == best[0] and w < best[2]):
                best = (score, doc.g_start + i, w)
    return best


def fuzzy_search(
    store: Store,
    docs: list[RetrievalDoc],
    ranked: list[tuple[int, float]],
    q_loose: list[str],
    *,
    max_docs: int = 100,
    budget: int = 400_000,
) -> list[WindowHit]:
    """Score the top ``max_docs`` retrieval candidates; return hits sorted by score desc.

    ``budget`` caps total window comparisons per quote (deterministic compute bound).
    """
    q_ids = [store.token_id(t) if store.token_id(t) >= 0 else -1_000_000 - i for i, t in enumerate(q_loose)]
    hits: list[WindowHit] = []
    used = 0
    for d_index, _ in ranked[:max_docs]:
        doc = docs[d_index]
        res = best_window(store, doc, q_ids, budget - used)
        used += doc.g_len
        if res is None:
            continue
        score, gpos, w = res
        rec = store.records[doc.rec]
        if rec.corpus == "tanzil" and gpos >= rec.g2_start and rec.g2_start >= 0:
            # simple-rasm variant: no display spans; refer to the ayah, tok offsets unknown
            hits.append(WindowHit(rec, -1, -1, round(score, 4), gpos, w))
        else:
            ts = gpos - rec.g_start
            hits.append(WindowHit(rec, ts, ts + w, round(score, 4), gpos, w))
        if used >= budget:
            break
    # one hit per record: best score, then variant 0 preferred, then shorter window
    best_by_rec: dict[int, WindowHit] = {}
    for h in hits:
        cur = best_by_rec.get(h.rec.idx)
        if (
            cur is None
            or h.score > cur.score
            or (h.score == cur.score and cur.tok_start < 0 <= h.tok_start)
            or (h.score == cur.score and h.win_len < cur.win_len)
        ):
            best_by_rec[h.rec.idx] = h
    out = list(best_by_rec.values())
    out.sort(key=lambda h: (-h.score, h.rec.g_len, h.rec.idx))
    return out


def fuzzy_search_surah_stream(
    store: Store,
    seeds: list[WindowHit],
    q_loose: list[str],
    *,
    max_seeds: int = 5,
    budget: int = 400_000,
) -> list[WindowHit]:
    """Multi-ayah quotes (E-025). Ayah-level docs cannot score a quote that runs over several ayat
    («… الْمَشْحُونِ * ثُمَّ أَغْرَقْنَا …»): each ayah alone covers only part of it. Around each seed
    ayah (best per-ayah hits) we open a window in the *surah stream* — the same stream ``find_exact``
    uses for cross-ayah exact hits — of ±(len(quote)) tokens, and slide windows there. The hit is
    attributed to the ayah where the window starts; ``gpos``/``win_len`` let the renderer compute the
    covered ayah range exactly as for exact cross-ayah hits. Never crosses a surah boundary.
    """
    n = len(q_loose)
    if n < 2 or not seeds:
        return []
    q_ids = [store.token_id(t) if store.token_id(t) >= 0 else -1_000_000 - i for i, t in enumerate(q_loose)]
    hits: list[WindowHit] = []
    seen_docs: set[tuple[int, int]] = set()
    used = 0
    for seed in seeds[:max_seeds]:
        rec = seed.rec
        if rec.corpus != "tanzil":
            continue
        doc_id = int(store.g_doc[seed.gpos])
        lo = max(0, seed.gpos - n)
        hi = min(len(store.G), seed.gpos + seed.win_len + n)
        # clamp to the surah stream document
        while lo < seed.gpos and int(store.g_doc[lo]) != doc_id:
            lo += 1
        while hi > seed.gpos and int(store.g_doc[hi - 1]) != doc_id:
            hi -= 1
        key = (lo, hi)
        if key in seen_docs or hi - lo <= 0:
            continue
        seen_docs.add(key)
        region = RetrievalDoc(rec.idx, lo, hi - lo)
        res = best_window(store, region, q_ids, budget - used)
        used += hi - lo
        if res is None:
            continue
        score, gpos, w = res
        start_rec = store.record_of_pos(gpos)
        # basmala tokens of ayah 1 are display-only: a window may not start inside them
        if gpos - start_rec.g_start < start_rec.offset and gpos < start_rec.g2_start:
            continue
        if start_rec.g2_start >= 0 and gpos >= start_rec.g2_start:
            hits.append(WindowHit(start_rec, -1, -1, round(score, 4), gpos, w))
        else:
            ts = gpos - start_rec.g_start
            hits.append(WindowHit(start_rec, ts, ts + w, round(score, 4), gpos, w))
        if used >= budget:
            break
    hits.sort(key=lambda h: (-h.score, h.win_len, h.rec.idx))
    return hits
