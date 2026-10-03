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
            "عنوان\nمتن",
            4,
            2,
            0,
            henc_id=7,
            title="عنوان",
            hadith_text="متن",
            grade="صحيح",
            takhrij="متفق عليه",
            link="https://hadeethenc.com/ar/browse/hadith/7",
        ),
    ]
    # Strict token streams are real (V6 re-derives the proof from them): ayah 2:153 fragment at
    # positions 0..3 (Uthmani «الصبرين» with its simple-rasm twin «الصابرين» in GS2, E-024), the
    # HadeethEnc record «عنوان متن» at positions 4..5.
    svocab = {"إن": 0, "الله": 1, "مع": 2, "الصبرين": 3, "عنوان": 4, "متن": 5, "الصابرين": 6}
    gs = np.array([0, 1, 2, 3, 4, 5], dtype=np.int32)
    gs2 = np.array([0, 1, 2, 6, 4, 5], dtype=np.int32)
    g_rec = np.array([0, 0, 0, 0, 1, 1], dtype=np.int32)
    z = np.zeros(6, dtype=np.int32)
    return Store(
        records=recs, vocab={}, svocab=svocab, G=z, GS=gs, GS2=gs2, G2=z, span_start=z, span_end=z, g_rec=g_rec, g_doc=z,
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
    status: str = "found",
    key: str = "found",
    matches: list[Match] | None = None,
    quoted_text: str = "إن الله مع الصابرين",
    **kw: Any,
) -> QuoteResult:
    return QuoteResult(
        id="q1", span=Span(start=0, end=10), quoted_text=quoted_text, kind="quran", language="ar", source_modality="text",
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
        source_text="عنوان\nمتن",
        source_url=g.url,
        grade=g,
    )
    assert (
        validate_response(
            resp(quote(matches=[m], quoted_text="عنوان متن")), tiny_store(), MESSAGES
        ).validator_rejections
        == 0
    )
    # altered grade text → reject
    g2 = Grade(text="حسن", takhrij="متفق عليه", version="1.7.0", url=g.url)
    m2 = match(
        corpus="hadeethenc",
        ref={"id": 7},
        collection_tier="hadeethenc",
        source_text="عنوان\nمتن",
        source_url=g.url,
        grade=g2,
    )
    assert (
        validate_response(
            resp(quote(matches=[m2], quoted_text="عنوان متن")), tiny_store(), MESSAGES
        ).validator_rejections
        == 1
    )


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


# --------------------------------------------------------------------------- V6 (B04, I17)


def test_v6_forged_found_is_downgraded_to_unproven() -> None:
    """A `found` whose quoted words are NOT a contiguous window of the matched record must not survive."""
    forged = quote(quoted_text="إن الله مع الصابرين دائما")  # one word the ayah fragment does not contain
    out = validate_response(resp(forged), tiny_store(), MESSAGES)
    q = out.quotes[0]
    assert out.validator_rejections == 1
    assert q.status == "needs_review" and q.review_reason == "validator_unproven"
    assert q.message_key == "needs_review_unproven"
    assert q.matches, "V6 keeps the closest record visible (unlike V1–V3 rejections)"


def test_v6_reordered_words_are_unproven() -> None:
    out = validate_response(resp(quote(quoted_text="الله إن مع الصابرين")), tiny_store(), MESSAGES)
    assert out.quotes[0].review_reason == "validator_unproven" and out.validator_rejections == 1


def test_v6_accepts_sub_window_and_ignores_tashkeel() -> None:
    assert (
        validate_response(resp(quote(quoted_text="مع الصابرين")), tiny_store(), MESSAGES).validator_rejections
        == 0
    )
    assert (
        validate_response(
            resp(quote(quoted_text="إِنَّ اللهَ مَعَ الصَّابِرِينَ")), tiny_store(), MESSAGES
        ).validator_rejections
        == 0
    )


def test_v6_strict_tier_rejects_loose_only_equality() -> None:
    """«علي» ≠ «على» strictly — a loose-equal forgery is still unproven (I2 re-derived independently)."""
    forged = quote(quoted_text="إن الله مع الصابرين", matches=[match()])
    forged.quoted_text = "ان الله مع الصابرين"  # alif without hamza: loose-equal, strict-different
    out = validate_response(resp(forged), tiny_store(), MESSAGES)
    assert out.quotes[0].review_reason == "validator_unproven"


def test_v6_only_applies_to_found() -> None:
    nr = quote(status="needs_review", key="needs_review_quran", quoted_text="كلام آخر تماما")
    nr.review_reason = "near_miss"
    out = validate_response(resp(nr), tiny_store(), MESSAGES)
    assert out.validator_rejections == 0 and out.quotes[0].review_reason == "near_miss"


def test_v6_message_keys_exist_and_are_clean() -> None:
    from app.messages import load_messages, scan_forbidden  # noqa: PLC0415

    for lang in ("ar", "en"):
        m = load_messages(MESSAGES, lang)
        assert m.has("status", "needs_review_unproven")
        assert scan_forbidden(m.get("status", "needs_review_unproven")) == []


# --------------------------------------------------------------------------- B05 (attribution_only)


def test_b05_attribution_only_kind_classifies_without_a_matn() -> None:
    from app.verify import attribution_only_kind  # noqa: PLC0415

    # attribution only: a takhrij phrase with no text of its own
    assert attribution_only_kind("رواه البخاري") == "attribution"
    assert attribution_only_kind("«متفق عليه»") == "attribution"
    assert attribution_only_kind("أخرجه مسلم في صحيحه") == "attribution"
    assert (
        attribution_only_kind("قال ﷺ: «رواه البخاري ومسلم»") == "attribution"
    )  # introducer kept by extractor
    # isnad only: a chain of narrators that stops before any matn
    assert (
        attribution_only_kind("عن أبي هريرة رضي الله عنه قال: قال رسول الله صلى الله عليه وسلم:") == "isnad"
    )
    assert attribution_only_kind("حدثنا عبد الله بن يوسف قال أخبرنا مالك عن نافع عن ابن عمر") == "isnad"
    # anything with words of its own is NOT attribution-only (fixture matn + a verbatim narrator line)
    assert attribution_only_kind("إنما الأعمال بالنيات") is None
    assert attribution_only_kind("قال ﷺ: «إنما الأعمال بالنيات»") is None
    assert attribution_only_kind("إن الله مع الصابرين") is None
    assert attribution_only_kind("") is None


def test_b05_attribution_only_rewords_not_found_without_counting_a_rejection() -> None:
    nf = quote(status="not_found", key="not_found_hadith", quoted_text="رواه البخاري", matches=[])
    nf.external_search_links = ["https://example.invalid/search"]
    nf.total_positions = 3
    out = validate_response(resp(nf), tiny_store(), MESSAGES)
    q = out.quotes[0]
    assert out.validator_rejections == 0  # wording, not a rejection
    assert q.status == "needs_review" and q.review_reason == "attribution_only"
    assert q.message_key == "needs_review_attribution_only"
    assert q.matches == [] and q.external_search_links == [] and q.total_positions == 0


def test_b05_never_touches_a_found_quote() -> None:
    out = validate_response(resp(quote(quoted_text="إن الله مع الصابرين")), tiny_store(), MESSAGES)
    assert out.quotes[0].status == "found" and out.quotes[0].review_reason is None


def test_b05_message_keys_exist_and_are_clean() -> None:
    from app.messages import load_messages, scan_forbidden  # noqa: PLC0415

    for lang in ("ar", "en"):
        m = load_messages(MESSAGES, lang)
        assert m.has("status", "needs_review_attribution_only")
        assert scan_forbidden(m.get("status", "needs_review_attribution_only")) == []


# --------------------------------------------------------------------------- B07 (segments are records)


def test_b07_forged_source_segment_is_rejected() -> None:
    from app.schemas import SourceSegment  # noqa: PLC0415

    m = match()
    m.source_segments = [
        SourceSegment(
            ref={"surah": 2, "ayah": 153},
            ref_label_ar="x",
            ref_label_en="x",
            source_text="إِنَّ ٱللَّهَ مَعَ ٱلصَّـٰبِرِينَ",
            source_url="https://quranpedia.net/surah/1/2/153",
        )
    ]
    assert validate_response(resp(quote(matches=[m])), tiny_store(), MESSAGES).validator_rejections == 0
    m.source_segments[0].source_text = "إِنَّ ٱللَّهَ مَعَ ٱلصَّـٰبِرِينَ."  # one byte off → V1 per segment
    out = validate_response(resp(quote(matches=[m])), tiny_store(), MESSAGES)
    assert out.validator_rejections == 1 and out.quotes[0].status == "needs_review"
    m.source_segments[0].source_text = "إِنَّ ٱللَّهَ مَعَ ٱلصَّـٰبِرِينَ"
    m.source_segments[0].ref = {"surah": 99, "ayah": 1}  # unknown record → V2 per segment
    assert validate_response(resp(quote(matches=[m])), tiny_store(), MESSAGES).validator_rejections == 1
