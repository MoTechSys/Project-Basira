"""English gate — retrieval tests on the real translations index (corpus/index/translations.pkl).

Skipped when the index is absent (CI without the network fetch). Every numeric bound below is a
*measured* value from `backend/.venv/bin/python eval/run_english.py` on 2026-10-03 (index sha
62c1fc6e…, sources: saheeh 6792bcbe…, rwwad 1212a876…, hadeethenc_en 3b51594a…), with a margin so a
re-fetch of a slightly revised translation does not flip the test, while a regression still would.
No religious text is asserted here beyond the short English quotations themselves.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.retrieve import translations as tr
from app.retrieve.translations import Candidate, TranslationIndex, normalize_en

REPO = Path(__file__).resolve().parents[2]
PKL = REPO / "corpus" / "index" / "translations.pkl"

pytestmark = pytest.mark.skipif(
    not PKL.exists(), reason="translations index not built (fetch_translations + build_index)"
)

# (quote, expected ref, measured top-1 score, measured rank) — rank must stay ≤ 5; top-1 ≥ 90 % of measured.
QURAN_CASES: list[tuple[str, str, float, int]] = [
    ("There is no compulsion in religion", "2:256", 1.0438, 1),
    ("Indeed, with hardship comes ease", "94:6", 1.5677, 1),
    ("whoever kills a soul it is as if he had slain mankind entirely", "5:32", 1.0141, 1),
    ("And kill them wherever you find them", "2:191", 1.0904, 1),
    ("We have not sent you except as a mercy to the worlds", "21:107", 1.3480, 1),
    (
        "Allah does not burden a soul beyond that it can bear",
        "2:286",
        0.7834,
        4,
    ),  # popular wording ≠ either translation
]
HADITH_CASES: list[tuple[str, str, float, int]] = [
    (
        "None of you truly believes until he loves for his brother what he loves for himself",
        "4717",
        1.1781,
        1,
    ),
    ("Religion is sincerity", "4309", 1.3384, 2),  # 66516 is the same hadith under a second HadeethEnc id
    ("Be in this world as if you were a stranger or a traveler", "4704", 0.7851, 1),
]
# Ordinary English — measured top-1 scores 0.3027 / 0.4378 / 0.3103; all must stay below the ceiling.
NEGATIVE_CASES: list[tuple[str, float]] = [
    ("The weather is nice today and I am going to the market to buy vegetables", 0.3027),
    ("Please remember to submit the quarterly report before Friday afternoon", 0.4378),
    ("The function returns a sorted list of integers and raises ValueError on empty input", 0.3103),
]
LOW_SCORE_CEILING = 0.60  # eval/run_english.py: highest negative top-1 over 7 negatives = 0.4654; lowest positive top-1 = 0.4972


@pytest.fixture(scope="module")
def idx() -> TranslationIndex:
    return TranslationIndex.load(PKL)


def _rank(cands: list[Candidate], ref: str, kind: str) -> int | None:
    return next((i + 1 for i, c in enumerate(cands) if c.kind == kind and c.ref == ref), None)


# --------------------------------------------------------------------------- the 12 required cases


@pytest.mark.parametrize(("quote", "ref", "measured_top1", "measured_rank"), QURAN_CASES)
def test_famous_ayat_in_top5(
    idx: TranslationIndex, quote: str, ref: str, measured_top1: float, measured_rank: int
) -> None:
    cands = idx.candidates(quote, 5)
    assert len(cands) == 5
    rank = _rank(cands, ref, "quran")
    assert rank is not None and rank <= 5, [(c.kind, c.ref, c.score) for c in cands]
    assert rank <= measured_rank, f"rank regressed: {rank} > measured {measured_rank}"
    assert cands[0].score >= 0.9 * measured_top1
    assert cands[0].score == pytest.approx(measured_top1, abs=0.15)


@pytest.mark.parametrize(("quote", "ref", "measured_top1", "measured_rank"), HADITH_CASES)
def test_hadeethenc_hadith_in_top5(
    idx: TranslationIndex, quote: str, ref: str, measured_top1: float, measured_rank: int
) -> None:
    cands = idx.candidates(quote, 5)
    rank = _rank(cands, ref, "hadith")
    assert rank is not None and rank <= measured_rank, [(c.kind, c.ref, c.score) for c in cands]
    assert cands[0].kind == "hadith"
    assert cands[0].score == pytest.approx(measured_top1, abs=0.15)
    hit = cands[rank - 1]
    assert hit.source_key == "hadeethenc_en" and hit.ref.isdigit()


@pytest.mark.parametrize(("text", "measured_top1"), NEGATIVE_CASES)
def test_ordinary_english_scores_low(idx: TranslationIndex, text: str, measured_top1: float) -> None:
    cands = idx.candidates(text, 5)
    assert cands, "BM25 always finds *something* for common words; emptiness would mean a broken vocab"
    assert cands[0].score < LOW_SCORE_CEILING
    assert cands[0].score == pytest.approx(measured_top1, abs=0.10)
    assert all(c.score <= cands[0].score for c in cands)


def test_positive_negative_separation(idx: TranslationIndex) -> None:
    """Every positive top-1 beats every negative top-1 (measured gap 0.4972 vs 0.4654 on the 30-case set)."""
    pos = min(idx.candidates(q, 1)[0].score for q, *_ in QURAN_CASES + HADITH_CASES)
    neg = max(idx.candidates(t, 1)[0].score for t, _ in NEGATIVE_CASES)
    assert pos > neg


# --------------------------------------------------------------------------- determinism & contract


def test_deterministic_same_input_same_output(idx: TranslationIndex) -> None:
    quotes = [q for q, *_ in QURAN_CASES + HADITH_CASES] + [t for t, _ in NEGATIVE_CASES]
    first = [idx.candidates(q, 5) for q in quotes]
    for _ in range(25):
        assert [idx.candidates(q, 5) for q in quotes] == first
    fresh = TranslationIndex.load(PKL)  # a second load from disk gives byte-identical candidates
    assert [fresh.candidates(q, 5) for q in quotes] == first


def test_candidates_unique_per_ref_and_sorted(idx: TranslationIndex) -> None:
    cands = idx.candidates("There is no compulsion in religion", 20)
    keys = [(c.kind, c.ref) for c in cands]
    assert len(keys) == len(set(keys)), "one slot per (kind, ref)"
    assert [c.score for c in cands] == sorted((c.score for c in cands), reverse=True)
    for c in cands:
        assert c.kind in ("quran", "hadith")
        assert c.source_key in ("english_saheeh", "english_rwwad", "hadeethenc_en")
        assert (c.kind == "quran") == (":" in c.ref)
        assert c.translation_text  # verbatim upstream text, never empty


def test_translation_text_is_verbatim_upstream(idx: TranslationIndex) -> None:
    """Candidate.translation_text must equal the stored upstream string byte-for-byte (red line 1)."""
    with PKL.open("rb") as fh:
        state = pickle.load(fh)
    stored = {(k, r, s): t for (k, r, s, _p, t, _it) in state["docs"]}
    for q, *_ in QURAN_CASES + HADITH_CASES:
        for c in idx.candidates(q, 5):
            assert c.translation_text == stored[(c.kind, c.ref, c.source_key)]


def test_kind_filter_and_k(idx: TranslationIndex) -> None:
    only_q = idx.candidates("There is no compulsion in religion", 3, kinds=["quran"])
    assert len(only_q) == 3 and all(c.kind == "quran" for c in only_q)
    only_h = idx.candidates("There is no compulsion in religion", 3, kinds=["hadith"])
    assert all(c.kind == "hadith" for c in only_h)
    assert idx.candidates("There is no compulsion in religion", 0) == []
    assert idx.candidates("", 5) == []
    assert idx.candidates("xqzvlkj wplmnt", 5) == []  # no vocabulary overlap → no candidates, not a crash


def test_module_level_candidates_is_cached(idx: TranslationIndex) -> None:
    a = tr.candidates("Religion is sincerity", 5)
    b = tr.candidates("Religion is sincerity", 5)
    assert a == b == idx.candidates("Religion is sincerity", 5)
    assert tr.load_default() is tr.load_default()


def test_index_meta_counts(idx: TranslationIndex) -> None:
    m = idx.meta
    assert m["n_quran_docs"] == 2 * 6236
    assert m["n_hadith_docs"] == m["source_counts"]["hadeethenc_en"] > 2000
    assert m["n_docs"] == m["n_quran_docs"] + m["n_hadith_docs"] == len(idx.docs)
    assert m["bigram_weight"] == tr.BIGRAM_WEIGHT


# --------------------------------------------------------------------------- normaliser


def test_normalize_en_folds() -> None:
    assert normalize_en("Allāh") == normalize_en("Allah") == ["allah"]
    assert normalize_en("ṭāghūt[104]") == ["taghut"]
    assert normalize_en("Qur’ān") == normalize_en("Quran") == ["quran"]
    assert normalize_en("[acceptance of] the religion.") == ["acceptance", "of", "the", "religion"]
    assert normalize_en("intentions deeds cities") == ["intention", "deed", "city"]
    assert normalize_en("this is his glass") == ["this", "is", "his", "glass"]  # S-stemmer guards
    assert normalize_en("") == [] and normalize_en("!!! ---") == []


@settings(max_examples=200, deadline=None)
@given(st.text(min_size=0, max_size=80))
def test_normalize_en_total_and_idempotent(s: str) -> None:
    toks = normalize_en(s)
    assert all(t and t.isascii() and t == t.lower() for t in toks)
    assert normalize_en(" ".join(toks)) == toks
