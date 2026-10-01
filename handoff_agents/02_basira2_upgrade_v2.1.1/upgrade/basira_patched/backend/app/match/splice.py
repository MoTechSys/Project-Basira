"""Composite (spliced) Quran quotes — E-038.

A bracketed «quote» that is NOT one contiguous passage but two (or more) genuine passages glued
together — «إن الله مع الصابرين والعصر إن الإنسان لفي خسر» — fails the exact gate and would be reported
as a bare *not found*. A scholar's eye sees immediately: 2:153 then 103:1–2. This module finds that
decomposition deterministically with the same positional index used for exact matching.

Algorithm (greedy, left-to-right, pure):
  * at position i, find the LONGEST token run quote[i:j] that is an exact hit (loose tier) in the
    Quran stream — binary-search-free: try j from n down to i+MIN;
  * accept the run, move to j; stop when fewer than MIN tokens remain or nothing matches;
  * success ⇔ the runs cover ALL tokens and there are ≥ 2 runs from ≥ 2 distinct ayah ranges.

Reporting is descriptive only: «نصك مركّب من مقطعين: … و…». Status stays what the state machine
decided (not_found / needs_review); the notice + parts let the UI show each part next to its ayah.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.match.exact import ExactHit, dedupe_hits, find_exact, records_covering
from app.store import Store

MIN_PART_TOKENS = 2
MAX_PARTS = 4


@dataclass(frozen=True, slots=True)
class SplicePart:
    tok_start: int  # token indices into the quote
    tok_end: int
    surah: int
    ayah: int
    ayah_to: int  # == ayah unless the part itself crosses an ayah boundary
    strict_ok: bool


def _best_quran_hit(store: Store, loose: list[str], strict: list[str]) -> ExactHit | None:
    hits = [h for h in dedupe_hits(find_exact(store, loose, strict)) if h.rec.corpus == "tanzil"]
    if not hits:
        return None
    # prefer strict, then lowest (surah, ayah) for determinism
    hits.sort(key=lambda h: (not h.strict_ok, h.rec.surah, h.rec.ayah))
    return hits[0]


def find_splice(
    store: Store,
    loose: list[str],
    strict: list[str],
    *,
    min_part: int = MIN_PART_TOKENS,
    max_parts: int = MAX_PARTS,
) -> list[SplicePart]:
    """Return the parts if the whole quote decomposes into ≥2 exact Quran runs, else []."""
    n = len(loose)
    if n < 2 * min_part:
        return []
    parts: list[SplicePart] = []
    i = 0
    while i < n and len(parts) < max_parts:
        found: ExactHit | None = None
        j_found = -1
        for j in range(n, i + min_part - 1, -1):
            h = _best_quran_hit(store, loose[i:j], strict[i:j])
            if h is not None:
                found, j_found = h, j
                break
        if found is None:
            return []
        covered = records_covering(store, found.gpos, j_found - i)
        last = covered[-1] if covered else found.rec
        parts.append(SplicePart(i, j_found, found.rec.surah, found.rec.ayah, last.ayah, found.strict_ok))
        i = j_found
    if i != n or len(parts) < 2:
        return []
    refs = {(p.surah, p.ayah) for p in parts}
    if len(refs) < 2:
        return []  # same ayah repeated — not a splice
    return parts
