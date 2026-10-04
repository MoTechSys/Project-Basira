"""Guard (docs/GUARD.md): verdicts, counts, fixed-template summaries, red lines."""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app import guard_messages
from app.config import Settings
from app.guard import guard_answer, verdict_of
from app.messages import scan_forbidden
from app.pipeline import Pipeline

AYAH_OK = "قال تعالى: ﴿إن الله مع الصابرين﴾"
HADITH_OK = "قال ﷺ: «إنما الأعمال بالنيات وإنما لكل امرئ ما نوى فمن كانت هجرته إلى دنيا يصيبها»"
HADITH_ALTERED = "قال ﷺ: «إنما الأعمال بالنيات وإنما لكل إنسان ما نوى فمن كانت هجرته إلى دنيا يصيبها»"
NOT_FOUND = "قال ﷺ: «الدين المعاملة»"
ARABIC_LETTERS = re.compile(r"[\u0621-\u064A]{2,}")


# --------------------------------------------------------------------------- verdict logic (pure)


def test_verdict_of_rules() -> None:
    assert verdict_of([]) == "no_quotes"
    assert verdict_of(["found"]) == "clear"
    assert verdict_of(["found", "found"]) == "clear"
    assert verdict_of(["found", "partial_match"]) == "flagged"
    assert verdict_of(["needs_review"]) == "flagged"
    assert verdict_of(["not_found", "found"]) == "flagged"


# --------------------------------------------------------------------------- templates


def test_every_template_is_forbidden_lexicon_clean() -> None:
    for tpl in guard_messages.all_templates():
        assert scan_forbidden(tpl) == [], tpl
    for verdict in ("clear", "flagged", "no_quotes"):
        for lang in ("ar", "en"):
            for n, k in ((0, 0), (1, 0), (1, 1), (2, 1), (3, 2), (11, 5), (30, 30)):
                assert scan_forbidden(guard_messages.render(verdict, lang, n=n, k=k)) == []


def test_arabic_number_agreement() -> None:
    assert guard_messages.arabic_count(1) == "اقتباس واحد"
    assert guard_messages.arabic_count(2) == "اقتباسان"
    assert guard_messages.arabic_count(3) == "3 اقتباسات"
    assert guard_messages.arabic_count(10) == "10 اقتباسات"
    assert guard_messages.arabic_count(11) == "11 اقتباسًا"
    assert guard_messages.arabic_k(1) == "واحد منها" and guard_messages.arabic_k(2) == "اثنان منها"
    assert guard_messages.arabic_k(7) == "7 منها"


@given(n=st.integers(min_value=0, max_value=200), k=st.integers(min_value=0, max_value=200))
def test_render_is_total_and_contains_counts(n: int, k: int) -> None:
    en = guard_messages.render("flagged", "en", n=n, k=k)
    assert str(n) in en and str(k) in en and en.endswith("when in doubt.")
    ar = guard_messages.render("flagged", "ar", n=n, k=k)
    assert "ليس حكمًا" in ar


# --------------------------------------------------------------------------- end to end (fixture)


async def test_clear_when_every_quote_found(pipeline: Pipeline, test_settings: Settings) -> None:
    out = await guard_answer(pipeline, test_settings, f"{AYAH_OK} و{HADITH_OK}", "ar")
    assert out["verdict"] == "clear"
    assert out["counts"] == {"quotes": 2, "found": 2, "flagged": 0, "by_status": {"found": 2}}
    assert out["flagged_quote_ids"] == []
    assert out["summary_ar"].startswith("في الإجابة اقتباسان؛ وُجدت كلها")
    assert out["summary_en"].startswith("The answer contains 2 quotation(s); all of them were found")


async def test_flagged_correct_ayah_plus_altered_hadith(pipeline: Pipeline, test_settings: Settings) -> None:
    out = await guard_answer(pipeline, test_settings, f"{AYAH_OK}. {HADITH_ALTERED}", "ar")
    assert out["verdict"] == "flagged"
    assert out["counts"]["quotes"] == 2 and out["counts"]["flagged"] == 1
    assert out["counts"]["by_status"] == {"found": 1, "partial_match": 1}
    assert len(out["flagged_quote_ids"]) == 1
    flagged = next(q for q in out["quotes"] if q["id"] == out["flagged_quote_ids"][0])
    assert flagged["status"] == "partial_match" and flagged["kind"] == "hadith_matn"
    assert "واحد منها يحتاج مراجعة" in out["summary_ar"]
    assert "1 of them need review" in out["summary_en"]


async def test_flagged_not_found(pipeline: Pipeline, test_settings: Settings) -> None:
    out = await guard_answer(pipeline, test_settings, NOT_FOUND, "en")
    assert out["verdict"] == "flagged" and out["counts"]["by_status"] == {"not_found": 1}
    assert out["quotes"][0]["matches"] == []  # nothing shown for not_found (I3 spirit: no candidates)


async def test_no_quotes(pipeline: Pipeline, test_settings: Settings) -> None:
    out = await guard_answer(pipeline, test_settings, "اليوم طقس جميل ونحن ذاهبون إلى السوق.", "ar")
    assert out["verdict"] == "no_quotes" and out["counts"]["quotes"] == 0
    assert out["quotes"] == [] and out["flagged_quote_ids"] == []
    assert out["summary_ar"].startswith("لم نجد في الإجابة اقتباسًا")
    assert out["summary_en"].startswith("No Quran or Hadith quotation")


async def test_summaries_contain_no_religious_text(pipeline: Pipeline, test_settings: Settings) -> None:
    """The summary must not leak the quotation or the source text — only counts and fixed words."""
    out = await guard_answer(pipeline, test_settings, f"{AYAH_OK} {HADITH_ALTERED}", "ar")
    for summary in (out["summary_ar"], out["summary_en"]):
        assert scan_forbidden(summary) == []
        for q in out["quotes"]:
            assert q["quoted_text"] not in summary
            for m in q["matches"]:
                assert m["source_text"] not in summary
                # no 4-word window of the source text either
                words = m["source_text"].split()
                for i in range(max(0, len(words) - 3)):
                    assert " ".join(words[i : i + 4]) not in summary
    # Arabic summary only uses the fixed template vocabulary (+ digits)
    allowed = set(ARABIC_LETTERS.findall(" ".join(guard_messages.all_templates())))
    for n in (1, 2, 3, 11):
        allowed |= set(
            ARABIC_LETTERS.findall(f"{guard_messages.arabic_count(n)} {guard_messages.arabic_k(n)}")
        )
    assert set(ARABIC_LETTERS.findall(out["summary_ar"])) <= allowed


async def test_guard_is_deterministic_and_matches_pipeline_hash(
    pipeline: Pipeline, test_settings: Settings
) -> None:
    a = await guard_answer(pipeline, test_settings, f"{AYAH_OK} {NOT_FOUND}", "ar")
    b = await guard_answer(pipeline, test_settings, f"{AYAH_OK} {NOT_FOUND}", "ar")
    assert a == b
    assert len(a["determinism_hash"]) == 64


async def test_guard_input_validation(pipeline: Pipeline, test_settings: Settings) -> None:
    from app.devgate import DevGateError  # noqa: PLC0415

    with pytest.raises(DevGateError) as e:
        await guard_answer(pipeline, test_settings, "   ", "ar")
    assert e.value.code == "invalid_input"
    with pytest.raises(DevGateError) as e:
        await guard_answer(pipeline, test_settings, "ا" * (test_settings.max_text_chars + 1), "ar")
    assert e.value.code == "text_too_long" and e.value.vars["max"] == test_settings.max_text_chars
