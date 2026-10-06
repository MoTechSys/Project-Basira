#!/usr/bin/env python3
"""Smoke test on the REAL corpus: the canonical cases every session must re-check.

Run: make smoke   (needs corpus/index built). Exit 1 on any deviation.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import Thresholds
from app.match.exact import dedupe_hits, find_exact
from app.normalize import loose_tokens, strict_tokens
from app.state import Evidence, QuoteFacts, decide
from app.store import load_store

# (text, expected status, expected reason)
CASES = [
    ("إن الله على كل شيء قدير", "found", None),
    (
        "إن الله علي كل شيء قدير",
        "needs_review",
        "orthographic_difference",
    ),  # the adversarial typo — MUST never be `found`
    ("إن الله مع الصابرين", "found", None),  # 2:153 + 8:46
    ("فبأي آلاء ربكما تكذبان", "found", None),  # 31 positions
    ("قل هو الله أحد الله الصمد", "found", None),  # crosses ayah boundary 112:1–2
    ("طلب العلم فريضة على كل مسلم", "found", None),  # Ibn Maja 220 (OHD numbering)
    ("إنما الأعمال بالنيات", "found", None),
    ("الدين المعاملة", "not_found", None),
]
# E-057/E-058 + D-015 — «كما يكتب الناس»: no marker, no hamza. The supervisor's exact input first.
PEOPLE = [
    ("إنما الأعمال بالنيات", "found"),
    ("انما الاعمال بالنيات", "found"),
    ("قل هو الله احد", "found"),
    ("ان الله مع الصابرين", "found"),
    ("لا ضرر ولا ضرار", "found"),
    ("ان الله علي كل شيء قدير", "needs_review"),  # إن/أن both in the Mushaf → never found
    ("ذهبت اليوم إلى السوق واشتريت خبزا", None),  # prose → no quote
]


def main() -> int:
    store = load_store(Path(__file__).resolve().parents[1] / "corpus" / "index")
    th = Thresholds()
    failed = 0
    for text, exp_status, exp_reason in CASES:
        hits = dedupe_hits(find_exact(store, loose_tokens(text), strict_tokens(text)))
        ev = [
            Evidence(h.rec.corpus, h.rec.idx, 1.0, h.strict_ok, book=h.rec.book, is_exact=True) for h in hits
        ]
        d = decide(QuoteFacts(len(loose_tokens(text)), "ar", "unknown", False), ev, th)
        ok = d.status == exp_status and d.review_reason == exp_reason
        failed += 0 if ok else 1
        print(
            f"{'OK ' if ok else 'FAIL'} {text!r:40} → {d.status:13} reason={d.review_reason} winners={len(d.winners)}"
        )
    # whole pipeline (rules + anchors + rasm layer + validator), offline mock provider
    import asyncio  # noqa: PLC0415
    import json  # noqa: PLC0415

    from app.config import Settings  # noqa: PLC0415
    from app.pipeline import CorpusMeta, Pipeline  # noqa: PLC0415
    from app.providers.mock import MockLLM  # noqa: PLC0415
    from app.retrieve.index import Retriever  # noqa: PLC0415
    from app.schemas import CheckRequest  # noqa: PLC0415

    root = Path(__file__).resolve().parents[1]
    settings = Settings(index_dir=root / "corpus" / "index", static_dir=None)
    meta = CorpusMeta.from_manifest(
        json.loads(settings.manifest_path.read_text(encoding="utf-8")), store.meta
    )
    pipe = Pipeline(store, Retriever(store), MockLLM(), settings, meta)
    for text, exp in PEOPLE:
        r = asyncio.run(pipe.check(CheckRequest(text=text, ui_lang="ar")))
        got = r.quotes[0].status if r.quotes else None
        ok = got == exp and (not r.quotes or r.quotes[0].quoted_text == text)
        failed += 0 if ok else 1
        print(f"{'OK ' if ok else 'FAIL'} {text!r:40} → {got!s:13} (unmarked input)")
    print("SMOKE", "OK" if not failed else f"FAILED ({failed})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
