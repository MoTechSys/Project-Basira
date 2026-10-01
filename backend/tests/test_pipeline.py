"""End-to-end pipeline on the fixture corpus: the canonical cases + religious-safety guarantees."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from app.messages import scan_forbidden
from app.pipeline import Pipeline
from app.providers import MockLLM
from app.providers.base import ExtractionResult, LLMClient, ProposedQuote, ProviderError
from app.schemas import CheckRequest, CheckResponse


async def run(pipeline: Pipeline, text: str, **kw: object) -> CheckResponse:
    return await pipeline.check(CheckRequest(text=text, **kw))  # type: ignore[arg-type]


# ---- canonical cases (mirror scripts/smoke.py, now through the whole pipeline) -------------


async def test_exact_quran_found_with_verbatim_source(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال تعالى: ﴿إن الله مع الصابرين﴾")
    assert len(r.quotes) == 1
    q = r.quotes[0]
    assert q.status == "found" and q.kind == "quran"
    refs = {(m.ref["surah"], m.ref["ayah"]) for m in q.matches}
    assert (2, 153) in refs and (8, 46) in refs
    m = next(m for m in q.matches if m.ref["ayah"] == 153)
    assert m.source_text == pipeline.store.lookup("tanzil", surah=2, ayah=153).display  # type: ignore[union-attr]
    assert m.source_url == "https://quranpedia.net/surah/1/2/153"
    assert m.diff == [] and m.diff_kinds == []
    assert r.validator_rejections == 0


async def test_adversarial_typo_is_never_found(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال تعالى: إن الله علي كل شيء قدير")
    q = r.quotes[0]
    assert q.status == "needs_review"
    assert q.review_reason == "orthographic_difference"
    assert q.message_key == "needs_review_quran"
    assert q.matches and all("word_replaced" in m.diff_kinds for m in q.matches)
    # the diff must point at the user's «علي» (chars 8..11 of the quote)
    rep = [o for o in q.matches[0].diff if o.op == "replace"]
    assert rep and q.quoted_text[rep[0].quote_chars[0] : rep[0].quote_chars[1]] == "علي"


async def test_cross_ayah_quote_reports_range(pipeline: Pipeline) -> None:
    r = await run(pipeline, "﴿قل هو الله أحد الله الصمد﴾")
    q = r.quotes[0]
    assert q.status == "found"
    m = q.matches[0]
    assert m.ref == {"surah": 112, "ayah": 1}
    assert m.continues_to == {"surah": 112, "ayah": 2}
    assert "1–2" in m.ref_label_ar


async def test_quran_near_miss_shows_diff_never_partial(pipeline: Pipeline) -> None:
    r = await run(pipeline, "﴿إن الله مع الصابرين والمتقين﴾")
    q = r.quotes[0]
    assert q.status == "needs_review" and q.review_reason == "near_miss"
    assert q.status != "partial_match"
    assert q.matches[0].ref == {"surah": 2, "ayah": 153}
    assert q.matches[0].diff_kinds


async def test_quran_not_found_shows_no_candidates(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال تعالى: الدين المعاملة والصدق منجاة")
    q = r.quotes[0]
    assert q.status == "not_found" and q.matches == [] and q.total_positions == 0
    assert q.message_key == "not_found_quran"
    assert q.external_search_links  # referral, not a verdict


async def test_hadith_found_with_claimed_source_mismatch(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال رسول الله ﷺ: «طلب العلم فريضة على كل مسلم» رواه البخاري")
    q = r.quotes[0]
    assert q.status == "found"
    assert q.claimed_source is not None and q.claimed_source.parsed["books"] == ["sahih_al-bukhari"]
    assert q.claimed_source_mismatch is True
    assert "claimed_source_mismatch" in q.notice_keys
    assert q.matches[0].ref["book"] == "sunan_ibn-maja" and q.matches[0].ref["num"] == 220
    assert "ohd_numbering" in q.notice_keys and "other_nine_referral" in q.notice_keys
    assert q.matches[0].source_url.startswith("https://github.com/mhashim6/Open-Hadith-Data/blob/1515f6cb/")


async def test_hadith_variant_is_partial_with_caveat(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال رسول الله ﷺ: «إنما الأعمال بالنية وإنما لكل امرئ ما نوى»")
    q = r.quotes[0]
    assert q.status == "partial_match"
    assert "hadith_variant" in q.notice_keys
    assert q.matches[0].corpus == "ohd" and q.matches[0].ref["book"] == "sahih_al-bukhari"
    assert "word_replaced" in q.matches[0].diff_kinds


async def test_hadeethenc_link_mode_never_embeds_text(pipeline: Pipeline) -> None:
    link_pipe = Pipeline(
        pipeline.store,
        pipeline.retriever,
        pipeline.llm,
        replace(pipeline.settings, ohd_mode="off"),
        pipeline.meta,
    )
    r = await run(link_pipe, "قال رسول الله ﷺ: «إنما الأعمال بالنيات»")
    q = r.quotes[0]
    assert q.status == "found"
    assert all(m.corpus == "hadeethenc" for m in q.matches)
    for m in q.matches:
        assert m.source_text == ""  # Q2 default: linked, not embedded
        assert m.grade is not None and m.grade.url.startswith("https://hadeethenc.com/")
    assert "grade_line" in q.notice_keys and "hadeethenc_link_only" in q.notice_keys
    assert r.validator_rejections == 0


async def test_hadeethenc_embed_mode_shows_verbatim_text(pipeline: Pipeline) -> None:
    embed = Pipeline(
        pipeline.store,
        pipeline.retriever,
        pipeline.llm,
        replace(pipeline.settings, ohd_mode="off", hadeethenc_mode="embed"),
        pipeline.meta,
    )
    r = await run(embed, "«إنما الأعمال بالنيات»")
    m = r.quotes[0].matches[0]
    rec = pipeline.store.lookup("hadeethenc", id=m.ref["id"])
    assert rec is not None and m.source_text == rec.display


async def test_non_arabic_quote_needs_review_and_offers_ref(pipeline: Pipeline) -> None:
    r = await run(pipeline, 'He said: "Verily Allah is with the patient" (Quran 2:153)')
    q = r.quotes[0]
    assert q.status == "needs_review" and q.review_reason == "non_arabic"
    assert "arabic_text_at_ref" in q.notice_keys
    assert q.matches == []


async def test_flags_are_descriptive_only(pipeline: Pipeline) -> None:
    r = await run(pipeline, "هل هذا الحديث صحيح؟ «إنما الأعمال بالنيات» انشرها تؤجر — رقمي 0551234567")
    assert r.flags.refusal and r.flags.chain_message and r.flags.pii_suspected
    assert r.quotes[0].status == "found"  # flags never change a verdict


async def test_no_quotes_yields_empty_list(pipeline: Pipeline) -> None:
    r = await run(pipeline, "ذهبت اليوم إلى السوق واشتريت خبزًا")
    assert r.quotes == []


async def test_image_modality_adds_notice(pipeline: Pipeline) -> None:
    r = await run(pipeline, "﴿إن الله مع الصابرين﴾", source_modality="image")
    assert "image_extracted" in r.quotes[0].notice_keys


# ---- provider interplay -----------------------------------------------------------------------


class _Broken(LLMClient):
    name = "broken"

    async def extract(self, text: str) -> ExtractionResult:
        raise ProviderError("boom")


class _Slow(LLMClient):
    name = "slow"

    async def extract(self, text: str) -> ExtractionResult:
        await asyncio.sleep(30)
        return ExtractionResult(self.name)


class _Liar(LLMClient):
    """Proposes text that is NOT in the input and a fake offset for text that is."""

    name = "liar"

    async def extract(self, text: str) -> ExtractionResult:
        return ExtractionResult(
            self.name,
            (
                ProposedQuote("إن الله مع الصابرين والمتقين", "quran", 0, 10),
                ProposedQuote("إن الله مع الصابرين", "hadith_matn", 999, 1200),
            ),
        )


async def test_provider_failure_degrades_but_rules_still_answer(pipeline: Pipeline) -> None:
    p = Pipeline(pipeline.store, pipeline.retriever, _Broken(), pipeline.settings, pipeline.meta)
    r = await run(p, "﴿إن الله مع الصابرين﴾")
    assert r.extraction_degraded is True and r.extraction_provider == "broken"
    assert r.quotes[0].status == "found"


async def test_provider_timeout_is_bounded(pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.pipeline as pl  # noqa: PLC0415

    monkeypatch.setattr(pl, "PROVIDER_TIMEOUT_S", 0.05)
    p = Pipeline(pipeline.store, pipeline.retriever, _Slow(), pipeline.settings, pipeline.meta)
    r = await run(p, "﴿إن الله مع الصابرين﴾")
    assert r.extraction_degraded is True and r.quotes[0].status == "found"


async def test_lying_provider_cannot_inject_text_or_offsets(pipeline: Pipeline) -> None:
    p = Pipeline(pipeline.store, pipeline.retriever, _Liar(), pipeline.settings, pipeline.meta)
    text = "كتب أحدهم: إن الله مع الصابرين فاصبروا"
    r = await run(p, text)
    assert len(r.quotes) == 1
    q = r.quotes[0]
    assert q.quoted_text == "إن الله مع الصابرين"  # relocated to the real position, fake span ignored
    assert text[q.span.start : q.span.end] == q.quoted_text
    assert q.status == "found"


async def test_mock_llm_adds_unmarked_sentence_proposal(pipeline: Pipeline) -> None:
    assert isinstance(pipeline.llm, MockLLM)
    r = await run(pipeline, "عن أبي هريرة ﷺ إنما الأعمال بالنيات وإنما لكل امرئ ما نوى")
    assert r.quotes and r.quotes[0].status in ("found", "partial_match")


# ---- religious-safety sweep over everything we emit --------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "قال تعالى: إن الله علي كل شيء قدير",
        "﴿إن الله مع الصابرين والمتقين﴾",
        "قال رسول الله ﷺ: «إنما الأعمال بالنية وإنما لكل امرئ ما نوى»",
        "قال النبي ﷺ: الدين المعاملة",
        'He said: "Verily Allah is with the patient" (Quran 2:153)',
    ],
)
async def test_no_forbidden_lexicon_in_our_strings(pipeline: Pipeline, text: str) -> None:
    r = await run(pipeline, text)
    for q in r.quotes:
        ours = [q.message_key, *q.notice_keys, *(k for m in q.matches for k in m.diff_kinds)]
        for lang in ("ar", "en"):
            msgs = pipeline.msgs_ar if lang == "ar" else pipeline.msgs_en
            for k in ours:
                for section in ("status", "notice", "labels"):
                    if msgs.has(section, k):
                        assert scan_forbidden(msgs.get(section, k)) == []
        for m in q.matches:
            assert scan_forbidden(m.ref_label_ar) == [] and scan_forbidden(m.ref_label_en) == []


async def test_deterministic_output(pipeline: Pipeline) -> None:
    a = await run(pipeline, "قال تعالى: إن الله علي كل شيء قدير. وقال ﷺ: «إنما الأعمال بالنيات»")
    b = await run(pipeline, "قال تعالى: إن الله علي كل شيء قدير. وقال ﷺ: «إنما الأعمال بالنيات»")
    strip = lambda r: r.model_dump(exclude={"request_id", "timings_ms"})  # noqa: E731
    assert strip(a) == strip(b)
