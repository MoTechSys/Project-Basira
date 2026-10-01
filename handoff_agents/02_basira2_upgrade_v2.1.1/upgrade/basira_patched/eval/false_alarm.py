"""eval/false_alarm.py — 500 verbatim corpus segments in neutral wrappers; each MUST come back `found`.

Definition (idea deck slide 10, audit §4): a *false alarm* is a verbatim quote that the checker
fails to confirm (anything other than ``found`` with the originating record among the matches; a
``found`` whose shown positions are a prefix of a longer list, or a Quran ``found`` for a hadith
segment that is itself an ayah — invariant I4 — both count as confirmed).
Target < 2 %. Segments are drawn deterministically (seed 20261004) from the loaded store:
50 % Quran (ayah windows of 4–10 tokens, both common and Uthmani surface forms), 50 % hadith
(OHD matn windows of 5–12 tokens). Wrappers are neutral prose. No text is stored; the segment is
re-cut from the store at run time.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.normalize import tokenize  # noqa: E402
from app.pipeline import Pipeline  # noqa: E402
from app.schemas import CheckRequest  # noqa: E402
from app.store import Record  # noqa: E402

WRAPPERS_Q = ["﴿{q}﴾", "قال تعالى: {q}", "تدبر: «{q}»", "{q} — صدق الله العظيم"]
WRAPPERS_H = ["قال رسول الله ﷺ: «{q}»", "عن النبي ﷺ قال: {q}", "«{q}» حديث شريف", "وفي الحديث: {q}"]


def _surface(rec: Record, use_display: bool) -> list[str]:
    base = rec.display if (use_display or rec.corpus != "tanzil") else rec.text_simple
    return [base[t.start : t.end] for t in tokenize(base)]


def sample_segments(store: Any, n: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    quran = [r for r in store.records if r.corpus == "tanzil" and r.g_len - r.offset >= 4]
    hadith = [r for r in store.records if r.corpus == "ohd" and r.matn > 0 and r.g_len - r.matn >= 5]
    out: list[dict[str, Any]] = []
    for i in range(n):
        if i % 2 == 0:
            r = rng.choice(quran)
            toks = _surface(r, use_display=(i % 4 == 2))
            avail = len(toks) - r.offset
            k = rng.randint(4, min(10, avail))
            a = rng.randint(r.offset, len(toks) - k)
            seg = " ".join(toks[a : a + k])
            out.append(
                {
                    "i": i,
                    "text": rng.choice(WRAPPERS_Q).replace("{q}", seg),
                    "seg": seg,
                    "ref": {"surah": r.surah, "ayah": r.ayah},
                    "corpus": "tanzil",
                }
            )
        else:
            r = rng.choice(hadith)
            toks = _surface(r, use_display=True)
            avail = len(toks) - r.matn
            k = rng.randint(5, min(12, avail))
            a = rng.randint(r.matn, len(toks) - k)
            seg = " ".join(toks[a : a + k])
            out.append(
                {
                    "i": i,
                    "text": rng.choice(WRAPPERS_H).replace("{q}", seg),
                    "seg": seg,
                    "ref": {"book": r.book, "num": r.num},
                    "corpus": "ohd",
                }
            )
    return out


async def run_false_alarm(pipeline: Pipeline, n: int = 500, seed: int = 20261004) -> dict[str, Any]:
    from eval.metrics import wilson  # noqa: PLC0415

    segs = sample_segments(pipeline.store, n, seed)
    misses: list[dict[str, Any]] = []
    for s in segs:
        r = await pipeline.check(CheckRequest(text=s["text"]))
        ok = False
        for q in r.quotes:
            if q.status == "found" and any(
                all(str(m.ref.get(k)) == str(v) for k, v in s["ref"].items()) for m in q.matches
            ):
                ok = True
                break
            if q.status == "found" and q.total_positions > len(q.matches):
                # the originating record may be beyond the shown positions (e.g. 31× «فبأي آلاء»): accept
                ok = True
                break
            if q.status == "found" and s["corpus"] == "ohd" and any(m.corpus == "tanzil" for m in q.matches):
                # a hadith segment that is itself an ayah quoted inside the hadith: Quran wins (I4) — correct
                ok = True
                break
        if not ok:
            misses.append(
                {
                    "i": s["i"],
                    "corpus": s["corpus"],
                    "ref": s["ref"],
                    "n_tokens": len(s["seg"].split()),
                    "statuses": [q.status for q in r.quotes],
                    "reasons": [q.review_reason for q in r.quotes],
                }
            )
    lo, hi = wilson(len(misses), n)
    return {
        "n": n,
        "seed": seed,
        "not_found": len(misses),
        "rate": len(misses) / n,
        "ci95": [lo, hi],
        "misses": misses[:50],
    }
