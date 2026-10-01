"""Scholar-lens regression tests (E-030..E-036) — the six gaps found in the zero-defect audit.

Each test mirrors a question a *sharia* judge asks in the first minute. They run on the fixture
index (Al-Fatihah, Al-Baqarah 1–160, Al-Anfal 40–50, Ar-Rahman, Al-Ikhlas, Al-Falaq, An-Nas,
Sahih al-Bukhari 1–…). Status invariants I1–I9 are untouched: every new behaviour is a *notice*.
"""

from __future__ import annotations

import pytest

from app.config import Thresholds
from app.extract.rules import RuleSpan, asserted_kind, extract_spans
from app.pipeline import Pipeline
from app.schemas import CheckRequest, CheckResponse
from app.state import Evidence, QuoteFacts, decide

TH = Thresholds()


async def run(pipeline: Pipeline, text: str, **kw: object) -> CheckResponse:
    return await pipeline.check(CheckRequest(text=text, **kw))  # type: ignore[arg-type]


def _notices(r: CheckResponse, i: int = 0) -> list[str]:
    return r.quotes[i].notice_keys


# ---------------------------------------------------------------- I12 claimed ayah mismatch (G-1)


def test_state_claimed_ayah_mismatch_sets_flag_and_notice() -> None:
    f = QuoteFacts(6, "ar", "quran", True, claimed_quran_ref=(2, 5), matched_quran_ref=(94, 6))
    d = decide(f, [Evidence("tanzil", 1, 1.0, True, is_exact=True)], TH)
    assert d.status == "found"  # I8: status unchanged
    assert d.claimed_source_mismatch is True
    assert "claimed_ayah_mismatch" in d.notice_keys


def test_state_claimed_ayah_consistent_when_in_range() -> None:
    f = QuoteFacts(
        6, "ar", "quran", True, claimed_quran_ref=(1, 2), claimed_ayah_to=3, matched_quran_ref=(1, 2)
    )
    d = decide(f, [Evidence("tanzil", 1, 1.0, True, is_exact=True)], TH)
    assert d.claimed_source_mismatch is False
    assert "claimed_ayah_mismatch" not in d.notice_keys


def test_state_claimed_ayah_wrong_surah_same_number() -> None:
    f = QuoteFacts(6, "ar", "quran", True, claimed_quran_ref=(3, 45), matched_quran_ref=(2, 45))
    d = decide(f, [Evidence("tanzil", 1, 1.0, True, is_exact=True)], TH)
    assert d.claimed_source_mismatch is True


async def test_pipeline_ayah_with_wrong_surah_reference(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال تعالى: ﴿قُلْ هُوَ اللَّهُ أَحَدٌ﴾ [البقرة: 5]")
    q = r.quotes[0]
    assert q.status == "found"
    assert q.matches[0].ref == {"surah": 112, "ayah": 1}
    assert q.claimed_source_mismatch is True
    assert "claimed_ayah_mismatch" in q.notice_keys


async def test_pipeline_ayah_with_correct_reference_has_no_mismatch(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال تعالى: ﴿قُلْ هُوَ اللَّهُ أَحَدٌ﴾ [الإخلاص: 1]")
    assert r.quotes[0].claimed_source_mismatch is False
    assert "claimed_ayah_mismatch" not in _notices(r)


# ---------------------------------------------------------------- I13 attribution cross-notices (G-2)


def test_asserted_kind_from_wording() -> None:
    t1 = "قال رسول الله ﷺ: «إن مع العسر يسرا»"
    sp1 = RuleSpan(t1.index("إن"), t1.index("»"), "unknown", True)
    assert asserted_kind(t1, sp1) == "hadith"
    t2 = "قال تعالى: ﴿إنما الأعمال بالنيات﴾"
    sp2 = RuleSpan(t2.index("إنما"), t2.index("﴾"), "quran", True)
    assert asserted_kind(t2, sp2) == "quran"
    t3 = "قال الله تعالى في الحديث القدسي: «أنا عند ظن عبدي بي»"  # both → nothing asserted
    sp3 = RuleSpan(t3.index("أنا"), t3.index("»"), "unknown", True)
    assert asserted_kind(t3, sp3) == ""
    t4 = "إنما الأعمال بالنيات رواه البخاري"  # trailer asserts hadith
    sp4 = RuleSpan(0, t4.index(" رواه"), "hadith_matn", False)
    assert asserted_kind(t4, sp4) == "hadith"


def test_state_quran_hit_introduced_as_hadith_gets_notice() -> None:
    f = QuoteFacts(5, "ar", "unknown", True, asserted="hadith")
    d = decide(f, [Evidence("tanzil", 1, 1.0, True, is_exact=True)], TH)
    assert d.status == "found"
    assert "attribution_quran_not_hadith" in d.notice_keys


def test_state_hadith_hit_introduced_as_quran_gets_notice() -> None:
    f = QuoteFacts(5, "ar", "quran", True, asserted="quran")
    d = decide(f, [Evidence("ohd", 9, 1.0, True, book="sahih_al-bukhari", is_exact=True)], TH)
    assert d.status == "found"
    assert "attribution_hadith_not_quran" in d.notice_keys


async def test_pipeline_ayah_attributed_to_prophet(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال رسول الله ﷺ: «قل هو الله أحد»")
    q = r.quotes[0]
    assert q.status == "found" and q.matches[0].corpus == "tanzil"
    assert "attribution_quran_not_hadith" in q.notice_keys


async def test_pipeline_hadith_attributed_to_quran(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال تعالى: ﴿إنما الأعمال بالنيات﴾")
    q = r.quotes[0]
    assert q.status == "found" and q.matches[0].corpus == "ohd"
    assert "attribution_hadith_not_quran" in q.notice_keys


async def test_pipeline_hadith_qudsi_has_no_attribution_notice(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال الله تعالى في الحديث القدسي: «إنما الأعمال بالنيات»")
    assert all(not k.startswith("attribution_") for k in _notices(r))


# ---------------------------------------------------------------- qiraah note (G-3)


async def test_qiraah_malik_without_dagger_alif_is_found_with_note(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال تعالى: ﴿مَلِكِ يَوْمِ الدِّينِ﴾")
    q = r.quotes[0]
    assert q.status == "found" and q.matches[0].ref == {"surah": 1, "ayah": 4}
    assert "qiraah_note" in q.notice_keys


async def test_hafs_rasm_has_no_qiraah_note(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال تعالى: ﴿مَٰلِكِ يَوْمِ ٱلدِّينِ﴾")
    assert "qiraah_note" not in _notices(r)


async def test_plain_orthography_malik_has_no_qiraah_note(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال تعالى: ﴿مالك يوم الدين﴾")
    assert r.quotes[0].status == "found"
    assert "qiraah_note" not in _notices(r)


# ---------------------------------------------------------------- partial ayah context (G-4)


async def test_fragment_of_longer_ayah_gets_context_notice(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال تعالى: ﴿وَأَقِيمُوا الصَّلَاةَ وَآتُوا الزَّكَاةَ﴾")  # 2:43 fragment
    q = r.quotes[0]
    assert q.status in ("found", "needs_review")
    assert "partial_ayah_context" in q.notice_keys


async def test_full_ayah_has_no_context_notice(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال تعالى: ﴿قُلْ هُوَ اللَّهُ أَحَدٌ﴾")
    assert "partial_ayah_context" not in _notices(r)


# ---------------------------------------------------------------- progressive stage (options.stage)


async def test_rules_stage_skips_provider_and_is_deterministic(pipeline: Pipeline) -> None:
    from app.schemas import CheckOptions, CheckRequest  # noqa: PLC0415

    text = "قال تعالى: ﴿قُلْ هُوَ اللَّهُ أَحَدٌ﴾ ثم قال: كلام عادي بلا علامات"
    r1 = await pipeline.check(CheckRequest(text=text, options=CheckOptions(stage="rules")))
    r2 = await pipeline.check(CheckRequest(text=text, options=CheckOptions(stage="rules")))
    assert r1.extraction_stage == "rules" and r1.extraction_provider == "rules"
    assert r1.extraction_degraded is False  # skipping the LLM on purpose is not a degradation
    assert r1.quotes and r1.quotes[0].status == "found"
    assert r1.determinism_hash == r2.determinism_hash
    assert r1.timings_ms.extract < 200  # no provider wait


async def test_full_stage_is_default_and_superset_of_rules(pipeline: Pipeline) -> None:
    from app.schemas import CheckOptions, CheckRequest  # noqa: PLC0415

    text = "قال تعالى: ﴿قُلْ هُوَ اللَّهُ أَحَدٌ﴾"
    full = await pipeline.check(CheckRequest(text=text))
    rules = await pipeline.check(CheckRequest(text=text, options=CheckOptions(stage="rules")))
    assert full.extraction_stage == "full"
    rule_spans = {(q.span.start, q.span.end) for q in rules.quotes}
    full_spans = {(q.span.start, q.span.end) for q in full.quotes}
    assert rule_spans <= full_spans  # the LLM may only ADD spans; rules never disappear


# ---------------------------------------------------------------- English introducer (G-6)


def test_english_introducer_is_captured() -> None:
    sp = extract_spans("The Prophet (PBUH) said: Actions are judged by intentions.")
    assert (
        sp
        and "Actions are judged by intentions"
        in "The Prophet (PBUH) said: Actions are judged by intentions."[sp[0].start : sp[0].end]
    )


async def test_english_quote_reported_as_non_arabic_review(pipeline: Pipeline) -> None:
    r = await run(pipeline, "Allah says: Say, He is Allah, the One.")
    assert r.quotes and r.quotes[0].status == "needs_review"
    assert r.quotes[0].message_key == "needs_review_non_arabic"


# ---------------------------------------------------------------- noise & duplicates (N-1, N-4)


def test_label_only_pseudo_quote_is_dropped() -> None:
    sp = extract_spans("قال الله تعالى في الحديث القدسي: «أنا عند ظن عبدي بي»")
    assert len(sp) == 1
    assert sp[0].marked is True


async def test_repeated_quote_is_merged(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال تعالى ﴿قل هو الله أحد﴾ ثم كرر ﴿قل هو الله أحد﴾")
    assert len(r.quotes) == 1
    assert len(r.quotes[0].repeated_spans) == 1
    assert "repeated_in_text" in r.quotes[0].notice_keys


# ---------------------------------------------------------------- all new keys exist in both languages (I9)


@pytest.mark.parametrize(
    "key",
    [
        "claimed_ayah_mismatch",
        "attribution_quran_not_hadith",
        "attribution_hadith_not_quran",
        "partial_ayah_context",
        "qiraah_note",
        "basmala_note",
        "repeated_in_text",
    ],
)
def test_new_notice_keys_exist_in_both_languages(key: str, pipeline: Pipeline) -> None:
    assert pipeline.msgs_ar.has("notice", key)
    assert pipeline.msgs_en.has("notice", key)
