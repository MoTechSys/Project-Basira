#!/usr/bin/env python3
"""Smoke test on the REAL corpus: the canonical cases every session must re-check.

Run: make smoke   (needs corpus/index built). Exit 1 on any deviation.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import Thresholds  # noqa: E402
from app.match.exact import dedupe_hits, find_exact  # noqa: E402
from app.normalize import loose_tokens, strict_tokens  # noqa: E402
from app.state import Evidence, QuoteFacts, decide  # noqa: E402
from app.store import load_store  # noqa: E402

# (text, expected status, expected reason)
CASES = [
    ("إن الله على كل شيء قدير", "found", None),
    ("إن الله علي كل شيء قدير", "needs_review", "orthographic_difference"),  # the adversarial typo — MUST never be `found`
    ("إن الله مع الصابرين", "found", None),  # 2:153 + 8:46
    ("فبأي آلاء ربكما تكذبان", "found", None),  # 31 positions
    ("قل هو الله أحد الله الصمد", "found", None),  # crosses ayah boundary 112:1–2
    ("طلب العلم فريضة على كل مسلم", "found", None),  # Ibn Maja 220 (OHD numbering)
    ("إنما الأعمال بالنيات", "found", None),
    ("الدين المعاملة", "not_found", None),
]


def main() -> int:
    store = load_store(Path(__file__).resolve().parents[1] / "corpus" / "index")
    th = Thresholds()
    failed = 0
    for text, exp_status, exp_reason in CASES:
        hits = dedupe_hits(find_exact(store, loose_tokens(text), strict_tokens(text)))
        ev = [Evidence(h.rec.corpus, h.rec.idx, 1.0, h.strict_ok, book=h.rec.book, is_exact=True) for h in hits]
        d = decide(QuoteFacts(len(loose_tokens(text)), "ar", "unknown", False), ev, th)
        ok = d.status == exp_status and d.review_reason == exp_reason
        failed += 0 if ok else 1
        print(f"{'OK ' if ok else 'FAIL'} {text!r:40} → {d.status:13} reason={d.review_reason} winners={len(d.winners)}")
    print("SMOKE", "OK" if not failed else f"FAILED ({failed})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
