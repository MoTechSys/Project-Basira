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
    # «علي» for «على» is a *written* ya where the Mushaf has alef maqsura — a swap, not an unwritten
    # mark — and «ان» stands for both «إن» and «أن» in this very sentence. D-015 (I19): never `found`;
    # the rasm layer names the reason and exposes both Mushaf spellings.
    r = await run(pipeline, "قال تعالى: إن الله علي كل شيء قدير")
    q = r.quotes[0]
    assert q.status == "needs_review"
    assert q.review_reason == "rasm_ambiguous"
    assert q.message_key == "needs_review_rasm_ambiguous"
    assert q.rasm is not None and q.rasm.verdict == "ambiguous"
    assert {a.spelling for a in q.rasm.alternatives} >= {"إن الله على كل شيء قدير", "أن الله على كل شيء قدير"}
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


async def test_mixed_rasm_quote_is_found_and_not_highlighted(pipeline: Pipeline) -> None:
    """E-024: 2:4 in the Uthmani rasm reads «بِمَآ … وَمَآ … وَبِٱلْءَاخِرَةِ»; a quote mixing the simple
    spelling of some words («بما», «وبالآخرة») with the Uthmani «ومآ» is byte-faithful to the Mushaf
    in every word and must pass the strict gate — but a real letter change must still fail it."""
    r = await run(pipeline, "قال تعالى: ﴿والذين يؤمنون بما أنزل إليك ومآ أنزل من قبلك وبالآخرة هم يوقنون﴾")
    q = r.quotes[0]
    assert q.status == "found" and (q.matches[0].ref["surah"], q.matches[0].ref["ayah"]) == (2, 4)
    assert q.matches[0].diff == []
    # same ayah, one letter changed («إليك» → «عليك»): never found; the diff highlights only that word
    r = await run(pipeline, "قال تعالى: ﴿والذين يؤمنون بما أنزل عليك ومآ أنزل من قبلك وبالآخرة هم يوقنون﴾")
    q = r.quotes[0]
    assert q.status == "needs_review" and q.review_reason in ("near_miss", "orthographic_difference")
    changed = [o for o in q.matches[0].diff if o.op != "equal"]
    assert len(changed) == 1 and changed[0].op == "replace"
    assert q.quoted_text[changed[0].quote_chars[0] : changed[0].quote_chars[1]] == "عليك"


async def test_decomposed_madda_is_byte_faithful(pipeline: Pipeline) -> None:
    """E-023: Tanzil writes «آ» as ا+U+0653; a quote with the precomposed U+0622 is identical text."""
    r = await run(pipeline, "قال تعالى: ﴿قالوا سبحانك لا علم لنا إلا ما علمتنآ إنك أنت العليم الحكيم﴾")
    assert r.quotes[0].status == "found"


async def test_fragment_of_ayah_is_found_but_labelled_fragment(pipeline: Pipeline) -> None:
    """E-026: faithful text that is only part of an ayah is `found` (it IS Mushaf text) with the
    `quran_fragment` notice; a whole ayah carries no such notice."""
    r = await run(pipeline, "قال تعالى: ﴿إن الله مع الصابرين﴾")
    assert r.quotes[0].status == "found" and "quran_fragment" in r.quotes[0].notice_keys
    r = await run(pipeline, "قال تعالى: ﴿الحمد لله رب العالمين﴾")
    assert r.quotes[0].status == "found" and "quran_fragment" not in r.quotes[0].notice_keys


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


async def test_image_modality_never_confirms_found(pipeline: Pipeline) -> None:
    """OCR can silently normalise the user's text, so an image-sourced exact hit is `needs_review`
    (image_unconfirmed) with the match still shown for comparison — never a confirmed `found`."""
    r = await run(pipeline, "﴿إن الله مع الصابرين﴾", source_modality="image")
    q = r.quotes[0]
    assert "image_extracted" in q.notice_keys
    assert q.status == "needs_review" and q.review_reason == "image_unconfirmed"
    assert q.message_key == "needs_review_image"
    assert q.matches and q.matches[0].ref == {"surah": 2, "ayah": 153}
    assert r.validator_rejections == 0


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


# ---- B05: an isnad / attribution with no matn is not a verdict on any text -------------------


async def test_attribution_without_matn_is_needs_review_not_not_found(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال ﷺ: «رواه البخاري ومسلم»")
    q = r.quotes[0]
    assert q.status == "needs_review" and q.review_reason == "attribution_only"
    assert q.message_key == "needs_review_attribution_only"
    assert q.matches == [] and q.external_search_links == []
    assert scan_forbidden(r.disclaimer_key) == []


async def test_isnad_without_matn_is_needs_review_not_not_found(pipeline: Pipeline) -> None:
    r = await run(pipeline, "عن أبي هريرة رضي الله عنه قال: قال رسول الله صلى الله عليه وسلم:")
    assert r.quotes, "the chain is still extracted as a quote"
    q = r.quotes[0]
    assert q.status == "needs_review" and q.review_reason == "attribution_only"
    assert q.matches == [] and q.message_key == "needs_review_attribution_only"


async def test_isnad_that_is_verbatim_in_a_record_stays_found(pipeline: Pipeline) -> None:
    """OHD records carry their isnad; a chain that IS in the record is literal text and stays `found`
    (V6 proves it). B05 only rewords verdicts that would otherwise judge an absent matn."""
    r = await run(pipeline, "حدثنا عبد الله بن يوسف قال أخبرنا مالك عن نافع عن ابن عمر")
    assert r.quotes[0].status == "found" and r.quotes[0].matches[0].ref["book"] == "sahih_al-bukhari"


async def test_isnad_with_matn_is_untouched_by_b05(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال رسول الله ﷺ: «إنما الأعمال بالنيات» رواه البخاري")
    assert r.quotes[0].status == "found" and r.quotes[0].review_reason is None


# ---- B10: never a silent cut ------------------------------------------------------------------


async def test_more_quotes_than_max_is_declared_not_silently_cut(pipeline: Pipeline) -> None:
    small = Pipeline(
        pipeline.store,
        pipeline.retriever,
        pipeline.llm,
        replace(pipeline.settings, max_quotes=2),
        pipeline.meta,
    )
    text = " ".join(f"قال تعالى: ﴿إن الله مع الصابرين﴾ {i}" for i in range(4))
    r = await run(small, text)
    assert r.quotes_detected == 4 and r.extraction_truncated is True
    assert len(r.quotes) <= 2
    assert all("extraction_truncated" in q.notice_keys for q in r.quotes)
    ok = await run(pipeline, text)
    assert ok.quotes_detected == 4 and ok.extraction_truncated is False
    assert not any("extraction_truncated" in q.notice_keys for q in ok.quotes)


async def test_truncation_notice_is_lexicon_clean(pipeline: Pipeline) -> None:
    from app.messages import load_messages  # noqa: PLC0415

    for lang in ("ar", "en"):
        m = load_messages(pipeline.settings.messages_dir, lang)
        for key in ("extraction_truncated", "ocr_truncated"):
            assert m.has("notice", key) and scan_forbidden(m.get("notice", key)) == []


# ---- B07: a multi-ayah quote shows every ayah as its own verbatim record -----------------------


async def test_multi_ayah_quote_carries_one_verbatim_segment_per_ayah(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال تعالى: ﴿قل هو الله أحد الله الصمد﴾")
    q = r.quotes[0]
    assert q.status == "found"
    m = q.matches[0]
    assert m.continues_to is not None and int(m.continues_to["ayah"]) == 2
    assert [(s.ref["surah"], s.ref["ayah"]) for s in m.source_segments] == [(112, 1), (112, 2)]
    for seg in m.source_segments:
        rec = pipeline.store.lookup("tanzil", surah=int(seg.ref["surah"]), ayah=int(seg.ref["ayah"]))
        assert rec is not None and seg.source_text == rec.display  # byte-exact, never a joined line
        assert seg.source_url.startswith("https://quranpedia.net/")
    single = await run(pipeline, "قال تعالى: ﴿إن الله مع الصابرين﴾")
    assert single.quotes[0].matches[0].source_segments == []


# ---- B06: repeated verbatim passages and impossible references ------------------------------------


async def test_claimed_ref_at_a_later_repetition_is_not_a_mismatch(pipeline: Pipeline) -> None:
    """The refrain of سورة الرحمن occurs 31 times; «[الرحمن: 77]» is a correct reference for it (B06)."""
    r = await run(pipeline, "قال تعالى: ﴿فبأي آلاء ربكما تكذبان﴾ [الرحمن: 77]")
    q = r.quotes[0]
    assert q.status == "found" and q.claimed_source_mismatch is False
    assert "claimed_ayah_mismatch" not in q.notice_keys
    wrong = await run(pipeline, "قال تعالى: ﴿فبأي آلاء ربكما تكذبان﴾ [البقرة: 5]")
    assert wrong.quotes[0].claimed_source_mismatch is True
    assert "claimed_ayah_mismatch" in wrong.quotes[0].notice_keys
    assert wrong.quotes[0].status == "found"  # I8: the notice never changes the status


async def test_impossible_claimed_reference_gets_its_own_notice(pipeline: Pipeline) -> None:
    r = await run(pipeline, "قال تعالى: ﴿قل هو الله أحد﴾ [الإخلاص: 1-999]")
    q = r.quotes[0]
    assert q.status == "found" and "claimed_ref_invalid" in q.notice_keys
    assert q.claimed_source_mismatch is False  # the text IS at 112:1; only the range is impossible
    ok = await run(pipeline, "قال تعالى: ﴿قل هو الله أحد﴾ [الإخلاص: 1]")
    assert "claimed_ref_invalid" not in ok.quotes[0].notice_keys
    beyond = await run(pipeline, "قال تعالى: ﴿قل هو الله أحد﴾ [البقرة: 300]")
    assert {"claimed_ref_invalid", "claimed_ayah_mismatch"} <= set(beyond.quotes[0].notice_keys)
    for lang in ("ar", "en"):
        from app.messages import load_messages  # noqa: PLC0415

        m = load_messages(pipeline.settings.messages_dir, lang)
        assert scan_forbidden(m.get("notice", "claimed_ref_invalid", claimed_ref="x")) == []


def test_ayah_counts_are_the_kufic_count() -> None:
    from app.quran_meta import AYAH_COUNTS, ayah_count, claimed_ref_possible  # noqa: PLC0415

    assert len(AYAH_COUNTS) == 114 and sum(AYAH_COUNTS) == 6236
    assert (ayah_count(1), ayah_count(2), ayah_count(55), ayah_count(112), ayah_count(114)) == (
        7,
        286,
        78,
        4,
        6,
    )
    assert ayah_count(0) is None and ayah_count(115) is None
    assert (
        claimed_ref_possible(55, 77, None)
        and claimed_ref_possible(2, 1, 5)
        and claimed_ref_possible(112, 1, 4)
    )
    assert not claimed_ref_possible(112, 1, 999) and not claimed_ref_possible(2, 300, None)
    assert not claimed_ref_possible(2, 5, 1) and not claimed_ref_possible(115, 1, None)


def test_ayah_counts_equal_tanzil_when_the_corpus_is_present() -> None:
    """The table is data, not text — and it must equal the pinned Tanzil file, surah by surah."""
    from collections import Counter  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    from app.quran_meta import AYAH_COUNTS  # noqa: PLC0415

    p = Path(__file__).resolve().parents[2] / "corpus" / "data" / "tanzil-uthmani.txt"
    if not p.exists():
        pytest.skip("full Tanzil file not fetched")
    c: Counter[int] = Counter()
    for line in p.read_text(encoding="utf-8").splitlines():
        parts = line.split("|")
        if len(parts) >= 3 and parts[0].isdigit():
            c[int(parts[0])] += 1
    assert tuple(c[i] for i in range(1, 115)) == AYAH_COUNTS
