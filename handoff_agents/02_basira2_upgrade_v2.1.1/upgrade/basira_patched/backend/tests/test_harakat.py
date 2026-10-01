"""E-037 — per-letter harakat comparison against the vocalized Mushaf (Tanzil Simple).

Invariant I14: a vowel-mark conflict NEVER changes the four-state status; it adds
``harakat_verdict="conflict"`` + exact letter offsets + the ``harakat_conflict`` notice.
Invariant I15: a user who writes no harakat (or only some, all agreeing) is never flagged.
"""

from __future__ import annotations

import pytest

from app.match.harakat import compare_quote, compare_token, extend_marks, skeleton
from app.normalize import tokenize
from app.pipeline import Pipeline
from app.schemas import CheckRequest

# ---------------------------------------------------------------- unit: skeleton / compare_token


def test_skeleton_attaches_marks_to_preceding_letter_and_ignores_non_harakat() -> None:
    sk = skeleton("مَٰلِكِ")  # dagger alif is not a haraka
    assert [(lt.char, sorted(lt.marks)) for lt in sk] == [
        ("م", ["fatha"]),
        ("ل", ["kasra"]),
        ("ك", ["kasra"]),
    ]
    sk = skeleton("اللَّهُ")
    assert [sorted(lt.marks) for lt in sk] == [[], [], ["fatha", "shadda"], ["damma"]]


def test_extend_marks_covers_trailing_case_ending() -> None:
    text = "الْعُلَمَاءُ إِنَّ"
    tok = tokenize(text)[0]
    # tokenizer ends after the last LETTER (ء); the ḍamma after it is the meaning-carrying mark
    assert text[tok.end] == "\u064f"
    assert extend_marks(text, tok.end) == tok.end + 1


@pytest.mark.parametrize(
    ("user", "mushaf", "expected", "n_conf"),
    [
        ("وَرَسُولِهِ", "وَرَسُولُهُ", "conflict", 2),  # 9:3 — the classic
        ("اللَّهُ", "اللَّهَ", "conflict", 1),  # 35:28 subject/object
        ("الْعُلَمَاءَ", "الْعُلَمَاءُ", "conflict", 1),
        ("إِبْرَاهِيمُ", "إِبْرَاهِيمَ", "conflict", 1),  # 2:124
        ("رَبَّهُ", "رَبُّهُ", "conflict", 1),
        ("يَعْلَمُ", "يُعَلِّمُ", "conflict", 3),  # pattern change
        ("أَسرَفُوا", "أَسْرَفُوا", "equal", 0),  # missing sukun is fine
        ("الله", "اللَّهَ", "unvocalized", 0),
        ("إنّ", "إِنَّ", "equal", 0),  # shadda only ⊆ shadda+kasra
        ("جَمِيعاً", "جَمِيعًا", "equal", 0),  # tanwīn placement variant (final)
        ("عِوَجَا", "عِوَجًا", "equal", 0),  # Uthmani pausal tanwīn drop (18:1)
        ("مَلَكِ", "مَالِكِ", "skeleton", 0),  # a LETTER differs → not our question
        ("ءَاتَيْنَٰكُم", "آتَيْنَاكُم", "skeleton", 0),  # Uthmani hamza+alif vs madda
    ],
)
def test_compare_token_matrix(user: str, mushaf: str, expected: str, n_conf: int) -> None:
    kind, conf = compare_token(user, (0, len(user)), mushaf, (0, len(mushaf)))
    assert kind == expected, (user, mushaf, kind, conf)
    assert len(conf) == n_conf


def test_conflict_offsets_point_at_the_exact_letter() -> None:
    user = "إِنَّمَا يَخْشَى اللَّهُ مِنْ عِبَادِهِ الْعُلَمَاءَ"
    ref = "إِنَّمَا يَخْشَى اللَّهَ مِنْ عِبَادِهِ الْعُلَمَاءُ"
    qs = [(t.start, t.end) for t in tokenize(user)]
    rs = [(t.start, t.end) for t in tokenize(ref)]
    verdict, conf, vocalized = compare_quote(user, qs, ref, rs)
    assert verdict == "conflict" and vocalized == 6
    assert [user[a:b] for a, b in (c.quote_chars for c in conf)] == ["هُ", "ءَ"]
    assert [ref[a:b] for a, b in (c.source_chars for c in conf)] == ["هَ", "ءُ"]


def test_quote_without_any_marks_is_none() -> None:
    user = "قل هو الله أحد"
    ref = "قُلْ هُوَ اللَّهُ أَحَدٌ"
    qs = [(t.start, t.end) for t in tokenize(user)]
    rs = [(t.start, t.end) for t in tokenize(ref)]
    assert compare_quote(user, qs, ref, rs)[0] == "none"


# ---------------------------------------------------------------- pipeline (fixture covers 1:1–2:160 …)


async def _one(pipeline: Pipeline, text: str):  # type: ignore[no-untyped-def]
    r = await pipeline.check(CheckRequest(text=text))
    assert r.quotes, text
    return r.quotes[0]


async def test_pipeline_flags_conflict_without_changing_status(pipeline: Pipeline) -> None:
    # 2:124 — «إبراهيمُ ربَّه» (subject/object swapped by vowels) vs Mushaf «إبراهيمَ ربُّه»
    q = await _one(pipeline, "قال تعالى: ﴿وَإِذِ ابْتَلَىٰ إِبْرَاهِيمُ رَبَّهُ بِكَلِمَاتٍ﴾")
    assert q.status == "found"  # I14: letters are identical → still found
    m = q.matches[0]
    assert m.ref == {"surah": 2, "ayah": 124}
    assert m.harakat_verdict == "conflict"
    assert "harakat_conflict" in q.notice_keys
    assert m.harakat_reference and m.harakat_reference_range is not None
    a, b = m.harakat_reference_range
    assert all(
        a <= c.reference_chars[0] and c.reference_chars[1] <= b for c in m.harakat_conflicts
    )  # range covers marks
    letters = [q.quoted_text[c.quote_chars[0] : c.quote_chars[1]] for c in m.harakat_conflicts]
    assert letters == ["مُ", "بَّ"]
    assert m.harakat_conflicts[0].reference_marks == ["fatha"] and m.harakat_conflicts[0].quote_marks == [
        "damma"
    ]


async def test_pipeline_consistent_and_none_verdicts(pipeline: Pipeline) -> None:
    ok = await _one(pipeline, "قال تعالى: ﴿وَإِذِ ابْتَلَىٰ إِبْرَاهِيمَ رَبُّهُ بِكَلِمَاتٍ﴾")
    assert ok.matches[0].harakat_verdict == "consistent" and "harakat_consistent" in ok.notice_keys
    assert ok.matches[0].harakat_reference == ""  # reference text only shipped on conflict
    bare = await _one(pipeline, "قال تعالى: ﴿وإذ ابتلى إبراهيم ربه بكلمات﴾")
    assert bare.matches[0].harakat_verdict == "none"
    assert not any(k.startswith("harakat") for k in bare.notice_keys)


async def test_pipeline_partial_vocalization_user_dropped_marks_is_consistent(pipeline: Pipeline) -> None:
    # the user's own example: several sukun/damma dropped, nothing contradicted
    q = await _one(pipeline, "قال تعالى: ﴿إِنَّ اللهَ مَعَ الصَّابِرِين﴾")  # 2:153
    assert q.status == "found" and q.matches[0].harakat_verdict == "consistent"


async def test_pipeline_uthmani_input_does_not_false_alarm(pipeline: Pipeline) -> None:
    q = await _one(pipeline, "قال تعالى: ﴿مَٰلِكِ يَوْمِ ٱلدِّينِ﴾")
    assert q.matches[0].harakat_verdict in ("consistent", "none")


async def test_hadith_matches_have_no_harakat_layer(pipeline: Pipeline) -> None:
    r = await pipeline.check(CheckRequest(text="قال رسول الله ﷺ: إنما الأعمال بالنيات"))
    for q in r.quotes:
        for m in q.matches:
            if m.corpus != "tanzil":
                assert m.harakat_verdict == "none" and not m.harakat_conflicts


def test_harakat_messages_exist_in_both_languages(pipeline: Pipeline) -> None:
    for key in ("harakat_conflict", "harakat_consistent"):
        assert pipeline.msgs_ar.has("notice", key) and pipeline.msgs_en.has("notice", key)


# ---------------------------------------------------------------- E-038 spliced quotes (fixture covers 1:1–2:160)


async def test_spliced_quote_is_decomposed_without_changing_status(pipeline: Pipeline) -> None:
    r = await pipeline.check(CheckRequest(text="قال تعالى: ﴿قل هو الله أحد الحمد لله رب العالمين﴾"))
    q = r.quotes[0]
    assert q.status != "found"
    assert "spliced_quote" in q.notice_keys
    assert [(p.surah, p.ayah) for p in q.splice_parts] == [(112, 1), (1, 2)]
    assert [q.quoted_text[p.chars[0] : p.chars[1]] for p in q.splice_parts] == [
        "قل هو الله أحد",
        "الحمد لله رب العالمين",
    ]


async def test_single_passage_and_typo_are_not_splices(pipeline: Pipeline) -> None:
    for text in ("قال تعالى: ﴿قل هو الله أحد﴾", "قال تعالى: ﴿إن الله مع الصابرن﴾"):
        r = await pipeline.check(CheckRequest(text=text))
        assert all(not q.splice_parts and "spliced_quote" not in q.notice_keys for q in r.quotes), text


def test_splice_message_in_both_languages(pipeline: Pipeline) -> None:
    assert pipeline.msgs_ar.has("notice", "spliced_quote") and pipeline.msgs_en.has("notice", "spliced_quote")
