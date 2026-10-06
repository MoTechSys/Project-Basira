"""D-015 — rasm-uniqueness proof (I18) and rasm-ambiguity (I19). See app/match/rasm.py and verify.py V7."""

from __future__ import annotations

import pytest

from app.match.rasm import bare, classify_token
from app.pipeline import Pipeline
from app.schemas import CheckRequest, CheckResponse
from app.verify import prove_rasm_found


async def _run(pipeline: Pipeline, text: str) -> CheckResponse:
    return await pipeline.check(CheckRequest(text=text, ui_lang="ar"))


# ---------------------------------------------------------------- pure classification


@pytest.mark.parametrize(
    ("user", "corpus", "expected"),
    [
        ("احد", "أحد", "completion"),
        ("امنوا", "آمنوا", "completion"),
        ("سالك", "سألك", "completion"),
        ("فاني", "فإني", "completion"),
        ("الصلاه", "الصلاة", "completion"),
        ("موسي", "موسى", "completion"),
        ("شي", "شيء", "other"),  # a missing letter is not a rasm question
        ("علي", "على", "completion"),  # ya for alef maqsura is a keyboard convention (bare form)
        ("على", "علي", "swap"),  # but WRITING alef maqsura where the Mushaf has ya is a choice
        ("أن", "إن", "swap"),  # user wrote a different hamza
        ("ألا", "إلا", "swap"),
        ("أحد", "أحد", "equal"),
        ("احد", "واحد", "other"),
    ],
)
def test_classify_token(user: str, corpus: str, expected: str) -> None:
    assert classify_token(user, corpus) == expected


def test_bare_fold_is_idempotent() -> None:
    for w in ("أحد", "إن", "آمنوا", "موسى", "الصلاة", "ؤ", "ئ"):
        assert bare(bare(w)) == bare(w)


# ---------------------------------------------------------------- I18: unique → found + completion


@pytest.mark.parametrize(
    ("text", "ref", "completed"),
    [
        ("قال تعالى: قل هو الله احد", (112, 1), ["أحد"]),
        ("قال تعالى: ان الله مع الصابرين", (2, 153), ["إن"]),
        ("قال تعالى: اياك نعبد واياك نستعين", (1, 5), ["إياك", "وإياك"]),
        (
            "قال تعالى: واقيموا الصلاه واتوا الزكاه واركعوا مع الراكعين",
            (2, 43),
            ["وأقيموا", "الصلاة", "وآتوا", "الزكاة"],
        ),
        ("قال تعالى: واذ اتينا موسي الكتاب والفرقان لعلكم تهتدون", (2, 53), ["وإذ", "آتينا", "موسى"]),
    ],
)
async def test_unwritten_hamza_on_a_uniquely_spelled_ayah_is_found(
    pipeline: Pipeline, text: str, ref: tuple[int, int], completed: list[str]
) -> None:
    r = await _run(pipeline, text)
    q = r.quotes[0]
    assert q.status == "found", (q.status, q.review_reason)
    assert "rasm_completed" in q.notice_keys
    assert q.rasm is not None and q.rasm.verdict == "unique"
    assert [c.corpus for c in q.rasm.completions] == completed
    # every completion points at a real span of the USER's text
    for c in q.rasm.completions:
        a, b = c.quote_chars
        assert q.quoted_text[a:b].strip() and bare(q.quoted_text[a:b]) == bare(c.corpus)
    assert (q.matches[0].ref["surah"], q.matches[0].ref["ayah"]) == ref
    assert r.validator_rejections == 0  # V7 re-proved it


async def test_fully_written_quote_carries_no_rasm_block(pipeline: Pipeline) -> None:
    r = await _run(pipeline, "قال تعالى: ﴿قل هو الله أحد﴾")
    q = r.quotes[0]
    assert q.status == "found" and q.rasm is None and "rasm_completed" not in q.notice_keys


# ---------------------------------------------------------------- I19: ambiguous → review + alternatives


async def test_bare_text_with_two_mushaf_spellings_is_review_with_alternatives(pipeline: Pipeline) -> None:
    r = await _run(pipeline, "قال تعالى: ان الله علي كل شيء قدير")
    q = r.quotes[0]
    assert q.status == "needs_review" and q.review_reason == "rasm_ambiguous"
    assert q.rasm is not None and q.rasm.verdict == "ambiguous"
    spellings = {a.spelling for a in q.rasm.alternatives}
    assert spellings == {"إن الله على كل شيء قدير", "أن الله على كل شيء قدير"}
    assert all(a.count > 0 for a in q.rasm.alternatives)
    assert q.matches  # the user still sees the candidate positions


async def test_written_different_hamza_is_a_swap_never_found(pipeline: Pipeline) -> None:
    # «أياك» written where the only Mushaf spelling is «إياك»: a positive choice → review
    r = await _run(pipeline, "قال تعالى: أياك نعبد وأياك نستعين")
    q = r.quotes[0]
    assert q.status == "needs_review" and q.review_reason == "rasm_ambiguous"


async def test_real_letter_difference_keeps_orthographic_difference(pipeline: Pipeline) -> None:
    # «شي» for «شيء» drops a letter; not a rasm question at all
    r = await _run(pipeline, "قال تعالى: إن الله على كل شي قدير")
    q = r.quotes[0]
    assert q.status != "found"
    assert q.review_reason in ("orthographic_difference", "near_miss")


# ---------------------------------------------------------------- V7 independence


async def test_v7_rejects_a_forged_rasm_found(pipeline: Pipeline) -> None:
    r = await _run(pipeline, "قال تعالى: ان الله علي كل شيء قدير")
    q = r.quotes[0]
    # forge: pretend the ambiguous one was `found` with a completion notice
    q.status = "found"
    q.notice_keys.append("rasm_completed")
    assert prove_rasm_found(pipeline.store, q) is False


async def test_v7_accepts_a_genuine_rasm_found(pipeline: Pipeline) -> None:
    r = await _run(pipeline, "قال تعالى: قل هو الله احد")
    q = r.quotes[0]
    assert q.status == "found" and prove_rasm_found(pipeline.store, q) is True
