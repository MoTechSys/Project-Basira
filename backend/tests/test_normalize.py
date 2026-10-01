"""normalize.py — BUILD_SPEC §3.1 (loose) and ADR-002 (strict) behaviour."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.normalize import (
    char_trigrams,
    loose_join,
    loose_tokens,
    strict_join,
    strict_tokens,
    tokenize,
)


def test_loose_folds_all_listed_letters() -> None:
    assert loose_join("إأآٱ") == "اااا"
    assert loose_join("ى ة ؤ ئ") == "ي ه و ي"


def test_strict_keeps_orthographic_distinctions() -> None:
    assert strict_join("إأآ") == "إأآ"
    assert strict_join("ى ة ؤ ئ") == "ى ة ؤ ئ"
    # wasla is folded in both tiers (rasm notation, not a distinct letter)
    assert strict_join("ٱلله") == "الله"


def test_diacritics_and_quranic_marks_removed_in_both_tiers() -> None:
    s = "إِنَّ ٱللَّهَ مَعَ ٱلصَّـٰبِرِينَ"
    assert loose_join(s) == "ان الله مع الصبرين"
    assert strict_join(s) == "إن الله مع الصبرين"


def test_sallallahu_ligature_dropped_before_nfkc() -> None:
    assert loose_tokens("قال النبي ﷺ كذا") == ["قال", "النبي", "كذا"]
    assert loose_tokens("الله ﷻ") == ["الله"]


def test_persian_yeh_and_kaf_folded() -> None:
    # ی (U+06CC) → ي and ک (U+06A9) → ك in both tiers
    assert loose_join("علی کل") == "علي كل"
    assert strict_join("علی کل") == "علي كل"


def test_punctuation_digits_and_ornaments_become_separators() -> None:
    s = "﴿١﴾ «الحمد» لله، 123 رب!"
    assert loose_tokens(s) == ["الحمد", "لله", "رب"]


def test_rlm_and_tatweel_removed_without_splitting_tokens() -> None:
    assert loose_tokens("\u200fحدثنا\u200f أبو\u0640\u0640 بكر") == ["حدثنا", "ابو", "بكر"]


def test_presentation_form_ligature_expands_within_one_char() -> None:
    # U+FEFB (ﻻ) is one source char producing two letters; span must cover it.
    toks = tokenize("ﻻ إله")
    assert toks[0].loose == "لا"
    assert (toks[0].start, toks[0].end) == (0, 1)


def test_spans_point_into_original_text() -> None:
    s = "قال رسول الله ﷺ: «طلب العلم فريضة على كل مسلم»"
    for t in tokenize(s):
        piece = s[t.start : t.end]
        assert piece.strip()
        # re-normalizing the sliced piece yields the same token
        assert loose_tokens(piece) == [t.loose]
        assert strict_tokens(piece) == [t.strict]


def test_adversarial_typo_differs_only_in_strict_tier() -> None:
    good = "إن الله على كل شيء قدير"
    typo = "إن الله علي كل شيء قدير"
    assert loose_join(good) == loose_join(typo)
    assert strict_join(good) != strict_join(typo)


def test_char_trigrams() -> None:
    assert char_trigrams("ان") == ["#ان", "ان#"]
    assert char_trigrams("ا") == ["#ا#"]
    assert char_trigrams("الله") == ["#ال", "الل", "لله", "له#"]


@given(st.text(min_size=0, max_size=200))
def test_tiers_always_align(s: str) -> None:
    toks = tokenize(s)
    assert len(loose_tokens(s)) == len(strict_tokens(s)) == len(toks)
    for t in toks:
        assert 0 <= t.start < t.end <= len(s)
        assert t.loose and t.strict
        assert " " not in t.loose and " " not in t.strict


@given(st.text(alphabet=st.characters(min_codepoint=0x0600, max_codepoint=0x06FF), max_size=80))
def test_idempotent(s: str) -> None:
    once = loose_join(s)
    assert loose_join(once) == once
    once_s = strict_join(s)
    assert strict_join(once_s) == once_s


def test_combining_madda_and_hamza_compose_in_strict_tier() -> None:
    # E-023: Tanzil Uthmani writes «آ» as ا + U+0653; other texts use the precomposed U+0622.
    # A byte-faithful quote must not be flagged as an orthographic difference.
    assert strict_join("كَمَا\u0653") == strict_join("كَمَآ") == "كمآ"
    assert strict_join("ا\u0654حمد") == strict_join("أحمد")
    assert strict_join("ا\u0655ن") == strict_join("إن")
    assert strict_join("يسا\u0654ل") == strict_join("يسأل")
    # the mark is consumed by the token: spans stay contiguous, loose tier unchanged
    toks = tokenize("كَمَا\u0653 قال")
    assert [t.loose for t in toks] == ["كما", "قال"]
    assert toks[0].end == 6
    # Uthmani elongation marks over و/ى/ي are NOT letters: still dropped in both tiers
    assert strict_join("تَبُوٓءُ") == "تبوء"
    assert strict_join("يَٰٓأَيُّهَا") == "يأيها"
