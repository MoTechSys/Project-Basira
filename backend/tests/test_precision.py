"""Precision guarantees added in the «basira-pro» pass.

* I10 — the not-found wording follows what the text CLAIMS to be (a hadith is never told
  «not found among the ayat of the Mushaf»); unknown kinds get a neutral both-corpora message.
* I11 — a diacritic the user wrote that contradicts the Mushaf is a difference (any letter, B01); missing
  diacritics are not; a pausal sukun on the LAST letter of the quote is not; hadith vocalisation is
  never gated (editorial, not canonical).
* letter-level (char-by-char) highlighting inside replaced words never splits a letter from
  its marks.
* conjunction-prefixed introducers («وقال رسول الله ﷺ …») are recognised.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.match.diff import letter_diff
from app.match.harakat import skeleton, word_conflicts
from app.pipeline import Pipeline
from app.schemas import CheckRequest, CheckResponse

# ---------------------------------------------------------------- pure units


@pytest.mark.parametrize(
    ("user", "source", "n_conflicts"),
    [
        ("حُرِّمَ", "حَرَّمَ", 2),  # passive vs active: ح and ر vowels differ
        ("الْمَيْتَةُ", "ٱلْمَيْتَةَ", 1),  # B01 (D-013): a written final vowel IS judged
        ("حرم", "حَرَّمَ", 0),  # no diacritics written → never a conflict
        ("اللَّهَ", "ٱللَّهَ", 0),  # identical vocalisation, wasla ignored
        ("شِيْءٍ", "شَىْءٍ", 1),  # kasra on ش where the Mushaf has fatha
        ("بِهِم", "بِهِمْ", 0),  # missing final sukun
        ("ذُرِّيَّتُهُمْ", "ذُرِّيَّتُهُم", 0),  # extra final sukun (pausal form)
    ],
)
def test_word_conflicts(user: str, source: str, n_conflicts: int) -> None:
    assert len(word_conflicts(user, source)) == n_conflicts


def test_skeleton_ignores_quranic_annotation_signs() -> None:
    # «ءَامَنُوا۟»: the small round zero over the final alif is rasm notation (no vowel)
    sk = skeleton("ءَامَنُوا۟")
    assert [m.vowel for m in sk][:3] == ["\u064e", None, "\u064e"]


_AR_LETTERS = st.sampled_from(list("ابتثجحخدذرزسشصضطظعغفقكلمنهوي"))
_MARKS = st.sampled_from(["", "\u064e", "\u064f", "\u0650", "\u0652", "\u0651\u064e"])


@given(st.lists(st.tuples(_AR_LETTERS, _MARKS), min_size=2, max_size=8))
def test_identical_or_bare_words_never_conflict(pairs: list[tuple[str, str]]) -> None:
    vocalised = "".join(c + m for c, m in pairs)
    bare = "".join(c for c, _ in pairs)
    assert word_conflicts(vocalised, vocalised) == []
    assert word_conflicts(bare, vocalised) == []  # absence of diacritics is never a difference


def test_letter_diff_highlights_only_the_differing_letter() -> None:
    ql, sl = letter_diff("علي", "عَلَىٰ")
    assert ql == [(2, 3)]  # «ي» in the user's word
    a, b = sl[0]
    assert "عَلَىٰ"[a:b].startswith("ى")  # whole grapheme incl. its marks


def test_letter_diff_on_unrelated_words_is_empty() -> None:
    assert letter_diff("قدير", "سميع") == ([], [])


# ---------------------------------------------------------------- end-to-end


async def _run(p: Pipeline, text: str) -> CheckResponse:
    return await p.check(CheckRequest(text=text))


async def test_hadith_not_found_never_gets_quran_wording(pipeline: Pipeline) -> None:
    for text in (
        "قال رسول الله ﷺ: «اطلبوا العلم ولو في الصين»",
        "وقال رسول الله ﷺ «اطلبوا العلم ولو في الصين»",
    ):
        r = await _run(pipeline, text)
        q = r.quotes[0]
        assert q.kind == "hadith_matn", text
        assert q.status == "not_found"
        assert q.message_key == "not_found"
        assert all("quranpedia" not in link.url for link in q.external_search_links)


async def test_unknown_not_found_is_neutral(pipeline: Pipeline) -> None:
    r = await _run(pipeline, "قال الحكيم: «العلم نور يهدي القلوب»")
    q = r.quotes[0]
    assert q.status == "not_found" and q.message_key == "not_found_any"
    hosts = {link.url.split("/")[2] for link in q.external_search_links}
    assert {"quranpedia.net", "dorar.net"} <= hosts


async def test_contradicting_diacritics_are_never_found(pipeline: Pipeline) -> None:
    # 2:153 «إِنَّ ٱللَّهَ مَعَ ٱلصَّٰبِرِينَ» — user writes kasra on the «ع» of «مَعَ»
    r = await _run(pipeline, "قال تعالى: «إِنَّ اللَّهَ مِعَ الصَّابِرِينَ»")
    q = r.quotes[0]
    assert q.status == "needs_review" and q.review_reason == "diacritic_difference"
    assert "diacritic_difference" in q.notice_keys
    m = q.matches[0]
    marked = [op for op in m.diff if op.quote_letters]
    assert marked, "the conflicting letter must be highlighted"
    a, b = marked[0].quote_letters[0]
    assert q.quoted_text[a:b].startswith("م")  # offsets are relative to quoted_text (as quote_chars)


async def test_correct_or_bare_diacritics_stay_found(pipeline: Pipeline) -> None:
    for text in ("قال تعالى: «إِنَّ اللَّهَ مَعَ الصَّابِرِينَ»", "قال تعالى: «إن الله مع الصابرين»"):
        r = await _run(pipeline, text)
        assert r.quotes[0].status == "found", text


async def test_orthographic_typo_gets_letter_level_highlight(pipeline: Pipeline) -> None:
    r = await _run(pipeline, "قال تعالى: إن الله علي كل شيء قدير")
    q = r.quotes[0]
    assert q.status == "needs_review"
    letters = [lt for m in q.matches for op in m.diff for lt in op.quote_letters]
    assert letters, "char-by-char highlight expected inside «علي»"
