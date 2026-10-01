"""Post-validator: tampered/forbidden output must never leave the server (SAFETY §2.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from app.schemas import CheckResponse, Flags, Grade, Match, QuoteResult, Span, Timings
from app.store import Record, Store
from app.verify import validate_response

MESSAGES = Path(__file__).resolve().parents[2] / "messages"


def tiny_store() -> Store:
    """A Store with two hand-made records; no corpus files needed."""
    recs = [
        Record(
            0, "tanzil", "إِنَّ ٱللَّهَ مَعَ ٱلصَّـٰبِرِينَ", 0, 4, 0, surah=2, ayah=153, text_simple="إن الله مع الصابرين"
        ),
        Record(
            1,
            "hadeethenc",
            "t\nh",
            4,
            2,
            0,
            henc_id=7,
            title="t",
            hadith_text="h",
            grade="صحيح",
            takhrij="متفق عليه",
            link="https://hadeethenc.com/ar/browse/hadith/7",
        ),
    ]
    z = np.zeros(6, dtype=np.int32)
    return Store(
        records=recs, vocab={}, svocab={}, G=z, GS=z, GS2=z, G2=z, span_start=z, span_end=z, g_rec=z, g_doc=z,
        post_offsets=np.zeros(1, dtype=np.int32), post_positions=np.zeros(0, dtype=np.int32),
        rdocs_quran=[], rdocs_hadith=[], meta={},
    )  # fmt: skip


def match(**kw: Any) -> Match:
    base: dict[str, Any] = {
        "corpus": "tanzil",
        "ref": {"surah": 2, "ayah": 153},
        "ref_label_ar": "سورة البقرة، الآية 153",
        "ref_label_en": "Surah Al-Baqarah (2:153)",
        "collection_tier": "quran",
        "source_text": "إِنَّ ٱللَّهَ مَعَ ٱلصَّـٰبِرِينَ",
        "source_url": "https://tanzil.net/#2:153",
        "score": 1.0,
    }
    base.update(kw)
    return Match(**base)


def quote(
    status: str = "found", key: str = "found", matches: list[Match] | None = None, **kw: Any
) -> QuoteResult:
    return QuoteResult(
        id="q1", span=Span(start=0, end=10), quoted_text="x", kind="quran", language="ar", source_modality="text",
        status=status, score=1.0, message_key=key, matches=matches if matches is not None else [match()], **kw,
    )  # type: ignore[arg-type]  # fmt: skip


def resp(*quotes: QuoteResult) -> CheckResponse:
    return CheckResponse(
        request_id="r",
        corpus={},
        extraction_provider="mock",
        flags=Flags(),
        quotes=list(quotes),
        timings_ms=Timings(),
    )


def test_clean_response_passes() -> None:
    out = validate_response(resp(quote()), tiny_store(), MESSAGES)
    assert out.validator_rejections == 0 and out.quotes[0].status == "found"


def test_tampered_source_text_is_rejected() -> None:
    out = validate_response(
        resp(quote(matches=[match(source_text="إن الله مع الصابرين")])), tiny_store(), MESSAGES
    )
    q = out.quotes[0]
    assert (
        out.validator_rejections == 1
        and q.status == "needs_review"
        and q.review_reason == "validator_reject"
        and q.matches == []
    )


def test_unknown_ref_is_rejected() -> None:
    out = validate_response(
        resp(quote(matches=[match(ref={"surah": 2, "ayah": 154})])), tiny_store(), MESSAGES
    )
    assert out.validator_rejections == 1


def test_grade_must_come_from_hadeethenc_record() -> None:
    g = Grade(
        text="صحيح", takhrij="متفق عليه", version="1.7.0", url="https://hadeethenc.com/ar/browse/hadith/7"
    )
    # grade attached to a Quran match → reject
    out = validate_response(resp(quote(matches=[match(grade=g)])), tiny_store(), MESSAGES)
    assert out.validator_rejections == 1
    # grade on the right HadeethEnc record → pass
    m = match(
        corpus="hadeethenc",
        ref={"id": 7},
        collection_tier="hadeethenc",
        source_text="t\nh",
        source_url=g.url,
        grade=g,
    )
    assert validate_response(resp(quote(matches=[m])), tiny_store(), MESSAGES).validator_rejections == 0
    # altered grade text → reject
    g2 = Grade(text="حسن", takhrij="متفق عليه", version="1.7.0", url=g.url)
    m2 = match(
        corpus="hadeethenc",
        ref={"id": 7},
        collection_tier="hadeethenc",
        source_text="t\nh",
        source_url=g.url,
        grade=g2,
    )
    assert validate_response(resp(quote(matches=[m2])), tiny_store(), MESSAGES).validator_rejections == 1


def test_forbidden_word_in_our_label_is_rejected() -> None:
    out = validate_response(resp(quote(matches=[match(ref_label_ar="آية محرّفة")])), tiny_store(), MESSAGES)
    assert out.validator_rejections == 1


def test_found_without_matches_is_impossible() -> None:
    out = validate_response(resp(quote(matches=[])), tiny_store(), MESSAGES)
    assert out.quotes[0].status == "needs_review"


def test_disclaimer_keys_are_forced_valid() -> None:
    r = resp(quote())
    r.disclaimer_key = "nope"
    out = validate_response(r, tiny_store(), MESSAGES)
    assert out.disclaimer_key == "footer"
