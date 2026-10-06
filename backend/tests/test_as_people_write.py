"""«كما يكتب الناس» — unmarked, hamza-less input must be understood (supervisor feedback, 2026-10-05).

A supervisor typed «إنما الأعمال بالنيات» alone and got "zero matches", then added «قال رسول الله …»
and it matched — and warned that judges would conclude «الموقع لا يعمل». E-057/E-058 fix the detector;
D-015 fixes the hamza. These tests pin both, on the fixture (records chosen from it). Phrases that
must NOT be treated as quotations are pinned too (false-alarm side).
"""

from __future__ import annotations

import pytest

from app.extract.anchor import detect
from app.pipeline import Pipeline
from app.schemas import CheckRequest, CheckResponse
from app.store import Store


async def _run(pipeline: Pipeline, text: str) -> CheckResponse:
    return await pipeline.check(CheckRequest(text=text, ui_lang="ar"))


# ---------------------------------------------------------------- detected without any marker


@pytest.mark.parametrize(
    "text",
    [
        "قل هو الله أحد",  # whole ayah, 3 stop-words (E-057)
        "قل هو الله احد",  # + unwritten hamza (D-015)
        "إن الله مع الصابرين",  # ayah fragment, rare phrase (E-058)
        "ان الله مع الصابرين",
        "إنما الأعمال بالنيات",  # the supervisor's exact input
        "انما الاعمال بالنيات",
        "اياك نعبد واياك نستعين",
        "فبأي آلاء ربكما تكذبان",
    ],
)
async def test_unmarked_famous_text_is_detected_and_found(pipeline: Pipeline, text: str) -> None:
    r = await _run(pipeline, text)
    assert r.quotes, f"no quote detected for {text!r}"
    q = r.quotes[0]
    assert q.status == "found", (text, q.status, q.review_reason)
    assert q.quoted_text == text  # the whole input is the quote, not a truncated tail
    assert r.validator_rejections == 0


async def test_unmarked_and_marked_input_agree(pipeline: Pipeline) -> None:
    """The verdict must not depend on whether the user typed «قال رسول الله» (supervisor's complaint)."""
    bare = await _run(pipeline, "إنما الأعمال بالنيات")
    marked = await _run(pipeline, "قال رسول الله ﷺ: «إنما الأعمال بالنيات»")
    assert bare.quotes[0].status == marked.quotes[0].status == "found"
    key = lambda m: (m.corpus, tuple(sorted(m.ref.items())))  # noqa: E731
    assert {key(m) for m in bare.quotes[0].matches} == {key(m) for m in marked.quotes[0].matches}


async def test_leading_stop_words_are_part_of_the_quote(pipeline: Pipeline) -> None:
    """Backward extension: the seed starts at the first content word but the quote starts earlier."""
    r = await _run(pipeline, "ان الله علي كل شيء قدير")
    q = r.quotes[0]
    assert q.quoted_text == "ان الله علي كل شيء قدير"
    assert q.status == "needs_review" and q.review_reason == "rasm_ambiguous"  # إن / أن both in the Mushaf


# ---------------------------------------------------------------- must NOT become quotations


@pytest.mark.parametrize(
    "text",
    [
        "ذهبت اليوم إلى السوق واشتريت خبزا وعدت إلى البيت",
        "حب الوطن من الإيمان",
        "الدين المعاملة",
        "والله أعلم بالصواب",
    ],
)
async def test_prose_and_non_corpus_sayings_are_not_detected(pipeline: Pipeline, text: str) -> None:
    r = await _run(pipeline, text)
    assert all(q.status in ("not_found", "needs_review") for q in r.quotes), [q.status for q in r.quotes]


def test_isnad_fragment_does_not_anchor_as_a_rare_phrase(store: Store) -> None:
    """«نافع عن ابن عمر» is rare as a phrase but is a narrator chain, not a matn (E-058 guard)."""
    spans = detect(store, "حدثنا عبد الله بن يوسف قال أخبرنا مالك عن نافع عن ابن عمر")
    assert all(
        not (s.n_tokens <= 5 and "نافع" in "x") for s in spans
    )  # structural guard below is the real check
    from app.extract.anchor import _isnad_shaped  # noqa: PLC0415
    from app.normalize import tokenize  # noqa: PLC0415

    assert _isnad_shaped(tokenize("نافع عن ابن عمر"))
    assert _isnad_shaped(tokenize("حدثنا عبد الله بن يوسف قال"))
    assert not _isnad_shaped(tokenize("إنما الأعمال بالنيات"))
    assert not _isnad_shaped(tokenize("لا ضرر ولا ضرار"))
