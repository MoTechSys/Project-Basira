"""Safety gates B01–B03 (DECISIONS D-013, E-044, E-045).

Written FAILING first against main@817c6fb — every case below was reproduced live on the full index:

  B02  «قل هو HELLO الله أحد» / «قل هو 123 الله أحد»  → were `found` (normalisation swallowed the foreign run)
  B01  35:28 «يَخْشَى اللَّهُ»  (Mushaf: «ٱللَّهَ»)            → was `found` (word-final letter never judged)
  B01  39:53 partially vocalised («إِنَّ الله يَغْفِرُ…»)      → was `found` with nothing shown
  waqf 112:1 «…أَحَدْ» (pausal sukun on the last letter)      → stays `found` + note (the ONLY exception)
  B03  «﴿قل هو الله أحد﴾ … ﴿قل هو الله احد﴾»                 → second occurrence inherited the first verdict

Harakat policy (owner 2026-10-03): any vowel the user WROTE that contradicts the Mushaf on the same
letter is a difference, wherever it sits in the word. Marks the user did not write are never a
contradiction, but when the quote is vocalised at all, the letters whose marks are missing are shown.
The single exception: a sukun on the last letter of the quote where the Mushaf has a vowel = pause.
"""

from __future__ import annotations

import pytest

from app.match.harakat import compare_words
from app.pipeline import Pipeline
from app.schemas import CheckRequest, CheckResponse


async def _run(pipeline: Pipeline, text: str) -> CheckResponse:
    return await pipeline.check(CheckRequest(text=text))


# ---------------------------------------------------------------- pure unit: compare_words


def test_final_letter_vowel_change_is_a_conflict() -> None:
    # 35:28 — «اللهُ» (nominative) vs Mushaf «اللهَ» (accusative): the meaning flips
    diffs = compare_words("اللَّهُ", "اللَّهَ", quote_final=False)
    assert diffs is not None
    assert [d.kind for d in diffs] == ["conflict"]


def test_pausal_sukun_on_last_letter_of_quote_is_not_a_conflict() -> None:
    res = compare_words("أَحَدْ", "أَحَدٌ", quote_final=True)
    assert res is not None
    assert [d.kind for d in res] == ["waqf"]
    # …but the same sukun INSIDE the quote is a conflict
    res2 = compare_words("أَحَدْ", "أَحَدٌ", quote_final=False)
    assert res2 is not None and [d.kind for d in res2] == ["conflict"]


def test_missing_marks_are_reported_as_missing_not_conflict() -> None:
    res = compare_words("الله", "اللَّهَ", quote_final=False)
    assert res is not None
    assert {d.kind for d in res} == {"missing"}


def test_unalignable_words_return_none() -> None:
    # Uthmani «ٱلْعُلَمَٰٓؤُا۟» spells the hamza differently from simple «الْعُلَمَاءُ» → letters differ
    assert compare_words("الْعُلَمَاءُ", "ٱلْعُلَمَٰٓؤُا۟", quote_final=True) is None
    # Uthmani «ٱلصَّٰبِرِينَ» has one base letter fewer than «الصَّابِرِينَ» (dagger alif is a mark)
    assert compare_words("الصَّابِرِينَ", "ٱلصَّٰبِرِينَ", quote_final=True) is None


# ---------------------------------------------------------------- B02 foreign material


@pytest.mark.parametrize("text", ["قال تعالى: ﴿قل هو HELLO الله أحد﴾.", "قال تعالى: ﴿قل هو 123 الله أحد﴾."])
async def test_foreign_material_inside_quote_is_never_found(pipeline: Pipeline, text: str) -> None:
    r = await _run(pipeline, text)
    assert len(r.quotes) == 1
    q = r.quotes[0]
    assert q.status == "needs_review"
    assert q.review_reason == "foreign_material"
    assert "foreign_material" in q.notice_keys
    # the foreign run itself is highlighted inside the user's text
    ranges = [tuple(op.quote_chars) for m in q.matches for op in m.diff if op.op != "equal"]
    assert ranges, "foreign run must be highlighted"
    a, b = ranges[0]
    assert q.quoted_text[a:b] in ("HELLO", "123")


async def test_ayah_number_in_brackets_is_not_foreign(pipeline: Pipeline) -> None:
    r = await _run(pipeline, "قال تعالى: ﴿قل هو الله أحد ﴿١﴾﴾")
    assert r.quotes[0].status == "found"


# ---------------------------------------------------------------- B01 harakat


async def test_35_28_final_vowel_change_is_shown(pipeline: Pipeline) -> None:
    r = await _run(pipeline, "قال تعالى: ﴿إِنَّمَا يَخْشَى اللَّهُ مِنْ عِبَادِهِ الْعُلَمَاءَ﴾.")
    q = r.quotes[0]
    assert q.status == "needs_review"
    assert q.review_reason == "diacritic_difference"
    m = q.matches[0]
    assert (m.ref["surah"], m.ref["ayah"]) == (35, 28)
    marked = [op for op in m.diff if op.quote_letters]
    assert marked, "the conflicting letter must be highlighted"
    hit = "".join(q.quoted_text[a:b] for op in marked for a, b in op.quote_letters)
    assert "هُ" in hit  # the ه of «اللهُ»


async def test_35_28_correct_vocalisation_stays_found(pipeline: Pipeline) -> None:
    r = await _run(pipeline, "قال تعالى: ﴿إِنَّمَا يَخْشَى اللَّهَ مِنْ عِبَادِهِ الْعُلَمَاءُ﴾.")
    q = r.quotes[0]
    assert q.status == "found", q.notice_keys
    assert "diacritic_difference" not in q.notice_keys
    assert "harakat_incomplete" not in q.notice_keys


async def test_39_53_partial_vocalisation_is_found_but_shown(pipeline: Pipeline) -> None:
    # «الله» and «الذنوب» carry no marks while the rest is vocalised → found, missing marks visible
    r = await _run(pipeline, "قال تعالى: ﴿إِنَّ الله يَغْفِرُ الذنوب جَمِيعًا﴾")
    q = r.quotes[0]
    assert q.status == "found"
    assert "harakat_incomplete" in q.notice_keys
    m = q.matches[0]
    assert (m.ref["surah"], m.ref["ayah"]) == (39, 53)
    assert "diacritic_missing" in m.diff_kinds
    src_marked = [lt for op in m.diff for lt in op.source_letters]
    assert src_marked, "letters whose marks are missing must be highlighted on the source side"


async def test_39_53_wrong_vowel_is_never_found(pipeline: Pipeline) -> None:
    r = await _run(pipeline, "قال تعالى: ﴿إِنَّ اللَّهَ يَغْفَرُ الذُّنُوبَ جَمِيعًا﴾")
    assert r.quotes[0].status == "needs_review"
    assert r.quotes[0].review_reason == "diacritic_difference"


async def test_bare_text_has_no_harakat_notices(pipeline: Pipeline) -> None:
    r = await _run(pipeline, "قال تعالى: ﴿إن الله يغفر الذنوب جميعا﴾")
    q = r.quotes[0]
    assert q.status == "found"
    assert not {"harakat_incomplete", "diacritic_difference", "waqf_note"} & set(q.notice_keys)


# ---------------------------------------------------------------- waqf exception


async def test_pausal_sukun_at_end_of_quote_is_found_with_note(pipeline: Pipeline) -> None:
    r = await _run(pipeline, "قال تعالى: ﴿قُلْ هُوَ اللَّهُ أَحَدْ﴾")
    q = r.quotes[0]
    assert q.status == "found"
    assert "waqf_note" in q.notice_keys


# ---------------------------------------------------------------- B03 repeated quotes


async def test_each_occurrence_gets_its_own_verdict(pipeline: Pipeline) -> None:
    r = await _run(pipeline, "قال تعالى: ﴿قل هو الله أحد﴾. وقال تعالى: ﴿قل هو الله احد﴾.")
    assert len(r.quotes) == 2, [q.status for q in r.quotes]
    by_text = {q.quoted_text: q for q in r.quotes}
    assert by_text["قل هو الله أحد"].status == "found"
    assert by_text["قل هو الله احد"].status == "needs_review"
    assert by_text["قل هو الله احد"].review_reason == "orthographic_difference"


async def test_identical_repeats_are_still_merged(pipeline: Pipeline) -> None:
    r = await _run(pipeline, "﴿قل هو الله أحد﴾ … ﴿قل هو الله أحد﴾")
    assert len(r.quotes) == 1
    assert len(r.quotes[0].repeated_spans) == 1
    assert "repeated_in_text" in r.quotes[0].notice_keys
