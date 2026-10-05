"""Religious-safety invariants of the four-state machine (see app/state.py docstring I1–I9)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.config import Thresholds
from app.state import Evidence, QuoteFacts, decide

TH = Thresholds()
MESSAGES = Path(__file__).resolve().parents[2] / "messages"


def facts(n: int = 6, kind: str = "unknown", marked: bool = False, **kw: object) -> QuoteFacts:
    return QuoteFacts(n_tokens=n, language="ar", kind=kind, marked=marked, **kw)  # type: ignore[arg-type]


def q(score: float, *, exact: bool = False, strict: bool = False, idx: int = 1) -> Evidence:
    return Evidence("tanzil", idx, score, strict, is_exact=exact)


def h(
    score: float, *, exact: bool = False, strict: bool = False, book: str = "sahih_al-bukhari", idx: int = 9
) -> Evidence:
    return Evidence("ohd", idx, score, strict, book=book, is_exact=exact)


# ---- I2 the adversarial case: loose-exact, strict-different -------------------------------


def test_orthographic_difference_is_never_found() -> None:
    d = decide(facts(), [q(1.0, exact=True, strict=False)], TH)
    assert d.status == "needs_review"
    assert d.review_reason == "orthographic_difference"
    assert d.message_key == "needs_review_quran"
    assert d.winners  # diff is shown against the near record


def test_strict_exact_quran_is_found() -> None:
    d = decide(facts(), [q(1.0, exact=True, strict=True)], TH)
    assert d.status == "found"
    assert d.corpus_scope == "quran"


# ---- I1 Quran never partial; I3 no candidates on not_found --------------------------------


@given(st.floats(min_value=0.0, max_value=0.9999))
def test_quran_never_partial_match(score: float) -> None:
    d = decide(facts(), [q(score)], TH)
    assert d.status != "partial_match"
    if d.status == "not_found":
        assert d.show_candidates is False and d.winners == []


def test_quran_review_band_boundaries() -> None:
    assert decide(facts(), [q(0.602)], TH).status == "needs_review"
    assert decide(facts(), [q(0.598)], TH).status == "not_found"
    # one-word change in a 4-word ayah = 0.75 → must be review, not not_found (eval category C)
    d = decide(facts(n=4, marked=True), [q(0.75)], TH)
    assert d.status == "needs_review"


# ---- hadith thresholds ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0.752, "partial_match"),
        (0.75, "partial_match"),
        (0.748, "needs_review"),
        (0.702, "needs_review"),
        (0.698, "not_found"),
    ],
)
def test_hadith_threshold_boundaries(score: float, expected: str) -> None:
    assert decide(facts(), [h(score)], TH).status == expected


def test_hadith_partial_carries_variant_caveat() -> None:
    d = decide(facts(), [h(0.9)], TH)
    assert d.status == "partial_match" and "hadith_variant" in d.notice_keys


# ---- I4 cross-corpus: strict Quran beats hadith -------------------------------------------


def test_quran_strict_exact_wins_over_hadith_even_with_hadith_claim() -> None:
    d = decide(
        facts(kind="hadith_matn", claimed_books=("sahih_al-bukhari",)),
        [h(1.0, exact=True, strict=True), q(1.0, exact=True, strict=True)],
        TH,
    )
    assert d.status == "found" and d.corpus_scope == "quran"
    assert "quran_wins" in d.notice_keys
    assert d.claimed_source_mismatch is False


# ---- I5 short quotes -----------------------------------------------------------------------


def test_short_quote_exact_found_but_fuzzy_never_partial() -> None:
    assert decide(facts(n=3), [h(1.0, exact=True, strict=True)], TH).status == "found"
    d = decide(facts(n=3), [h(0.9)], TH)
    assert d.status == "needs_review" and d.review_reason == "short_quote"
    assert decide(facts(n=3), [h(0.7)], TH).status == "not_found"


# ---- I6 grade attachment -------------------------------------------------------------------


def test_grade_only_on_found_or_partial() -> None:
    assert decide(facts(), [h(1.0, exact=True, strict=True)], TH).attach_grade is True
    assert decide(facts(), [h(0.8)], TH).attach_grade is True
    assert decide(facts(), [h(0.72)], TH).attach_grade is False
    assert decide(facts(), [q(1.0, exact=True, strict=True)], TH).attach_grade is False


# ---- I7 non-Arabic -------------------------------------------------------------------------


def test_non_arabic_needs_review_and_offers_ref_text() -> None:
    f = QuoteFacts(n_tokens=8, language="en", kind="quran", marked=True, claimed_quran_ref=(9, 11))
    d = decide(f, [], TH)
    assert d.status == "needs_review" and d.review_reason == "non_arabic"
    assert "arabic_text_at_ref" in d.notice_keys and d.extra["show_ref"] == (9, 11)
    assert d.show_candidates is False


# ---- I8 claimed source mismatch never changes status -------------------------------------


def test_claimed_source_mismatch_is_notice_only() -> None:
    d = decide(
        facts(claimed_books=("sahih_al-bukhari",)),
        [h(1.0, exact=True, strict=True, book="sunan_ibn-maja")],
        TH,
    )
    assert d.status == "found"
    assert d.claimed_source_mismatch is True and "claimed_source_mismatch" in d.notice_keys
    d2 = decide(
        facts(claimed_books=("sunan_ibn-maja",)), [h(1.0, exact=True, strict=True, book="sunan_ibn-maja")], TH
    )
    assert d2.claimed_source_mismatch is False


# ---- nothing found -------------------------------------------------------------------------


def test_no_evidence() -> None:
    d = decide(facts(kind="quran"), [], TH)
    assert d.status == "not_found" and d.message_key == "not_found_quran" and not d.show_candidates
    assert decide(facts(kind="hadith_matn"), [], TH).message_key == "not_found"


# ---- I9 every key emitted exists in both message files -----------------------------------


def test_all_emitted_keys_exist_in_messages() -> None:
    ar = json.loads((MESSAGES / "ar.json").read_text(encoding="utf-8"))
    en = json.loads((MESSAGES / "en.json").read_text(encoding="utf-8"))
    scenarios = [
        ([q(1.0, exact=True, strict=True)], facts()),
        ([q(1.0, exact=True, strict=False)], facts()),
        ([q(0.7)], facts()),
        ([q(0.3)], facts()),
        ([h(1.0, exact=True, strict=True)], facts(claimed_books=("sahih_muslim",))),
        ([h(1.0, exact=True, strict=False)], facts()),
        ([h(0.8)], facts()),
        ([h(0.72)], facts()),
        ([h(0.5)], facts()),
        ([h(0.9)], facts(n=3)),
        ([], QuoteFacts(3, "en", "unknown", True, claimed_quran_ref=(2, 255))),
        ([h(1.0, exact=True, strict=True), q(1.0, exact=True, strict=True)], facts(kind="hadith_matn")),
    ]
    for ev, f in scenarios:
        d = decide(f, ev, TH)
        for data in (ar, en):
            assert d.message_key in data["status"], d.message_key
            for k in d.notice_keys:
                assert k in data["notice"], k


# ---- property: found ⇒ strict exact evidence exists ---------------------------------------


@given(
    st.lists(
        st.builds(
            Evidence,
            corpus=st.sampled_from(["tanzil", "ohd", "hadeethenc"]),
            rec_idx=st.integers(0, 50),
            score=st.floats(0.0, 1.0),
            strict_ok=st.booleans(),
            book=st.sampled_from(["sahih_al-bukhari", "sunan_ibn-maja", ""]),
            is_exact=st.booleans(),
        ),
        max_size=8,
    ),
    st.integers(1, 12),
)
def test_found_implies_strict_exact(ev: list[Evidence], n: int) -> None:
    d = decide(facts(n=n), ev, TH)
    if d.status == "found":
        assert all(e.is_exact and e.strict_ok for e in d.winners) and d.winners
    if d.corpus_scope == "quran":
        assert d.status != "partial_match"
