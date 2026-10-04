"""English gate wired into the pipeline (E-048; docs/ENGLISH_GATE.md §6.2–6.3).

A non-Arabic quote keeps I7 (`needs_review/non_arabic`) and now carries `english_candidates`:
approved translations cross-referenced to byte-exact Arabic records, with at most one `selected`
by a deterministic rule or by a constrained model picker. Nothing here generates text.
"""

from __future__ import annotations

import pytest

from app.english_gate import RULE_MIN_GAP, RULE_MIN_TOP1, EnglishGate, EnglishPicker
from app.pipeline import Pipeline
from app.providers.openai_compat import OpenAICompatPicker, parse_pick
from app.schemas import CheckRequest, CheckResponse, EnglishCandidate


async def _run(pipeline: Pipeline, text: str) -> CheckResponse:
    return await pipeline.check(CheckRequest(text=text))


# ---------------------------------------------------------------- pipeline integration


async def test_english_quote_keeps_i7_and_carries_candidates(pipeline: Pipeline) -> None:
    r = await _run(pipeline, 'Allah says: "Indeed, Allah is with the patient"')
    q = r.quotes[0]
    assert q.status == "needs_review" and q.review_reason == "non_arabic"  # I7 unchanged
    assert q.english_candidates, "candidates expected from the fixture translations index"
    assert "english_candidates" in q.notice_keys
    top = q.english_candidates[0]
    assert top.kind == "quran" and (top.ref["surah"], top.ref["ayah"]) in {(2, 153), (8, 46)}
    assert top.translation_source in {"english_saheeh", "english_rwwad"}
    assert top.source_url.startswith("https://quranpedia.net/")


async def test_candidate_arabic_text_is_the_verbatim_record(pipeline: Pipeline) -> None:
    r = await _run(pipeline, 'Allah says: "Indeed, Allah is with the patient"')
    for c in r.quotes[0].english_candidates:
        if c.kind == "quran":
            rec = pipeline.store.lookup("tanzil", surah=int(c.ref["surah"]), ayah=int(c.ref["ayah"]))
            assert rec is not None and c.arabic_text == rec.display
        else:
            assert c.arabic_text == ""  # owner Q2: HadeethEnc body is linked, never embedded
    assert r.validator_rejections == 0


async def test_at_most_one_selected_and_rule_is_explicit(pipeline: Pipeline) -> None:
    r = await _run(pipeline, 'Allah says: "Indeed, Allah is with the patient"')
    q = r.quotes[0]
    assert sum(c.selected for c in q.english_candidates) <= 1
    assert q.picker in {"rule", "none"}
    if q.picker == "rule":
        c0, c1 = q.english_candidates[0], q.english_candidates[1]
        assert c0.selected and c0.score >= RULE_MIN_TOP1 and c0.score - c1.score >= RULE_MIN_GAP


async def test_arabic_quotes_are_untouched(pipeline: Pipeline) -> None:
    r = await _run(pipeline, "قال تعالى: ﴿إن الله مع الصابرين﴾")
    q = r.quotes[0]
    assert q.status == "found"
    assert q.english_candidates == [] and q.picker == ""
    assert "english_candidates" not in q.notice_keys


async def test_gate_is_deterministic(pipeline: Pipeline) -> None:
    a = await _run(pipeline, 'He said: "There is no compulsion in religion"')
    b = await _run(pipeline, 'He said: "There is no compulsion in religion"')
    ca = [(c.kind, c.ref, c.score, c.selected) for c in a.quotes[0].english_candidates]
    cb = [(c.kind, c.ref, c.score, c.selected) for c in b.quotes[0].english_candidates]
    assert ca == cb and a.quotes[0].picker == b.quotes[0].picker


async def test_disabled_gate_is_harmless(pipeline: Pipeline) -> None:
    saved = pipeline.english
    pipeline.english = EnglishGate(pipeline.store, None)
    try:
        r = await _run(pipeline, 'Allah says: "Indeed, Allah is with the patient"')
        q = r.quotes[0]
        assert q.status == "needs_review" and q.english_candidates == [] and q.picker == ""
    finally:
        pipeline.english = saved


# ---------------------------------------------------------------- model picker contract


class _FixedPicker(EnglishPicker):
    name = "fixed"

    def __init__(self, answer: int | None, *, raise_: bool = False) -> None:
        self.answer = answer
        self.raise_ = raise_
        self.calls = 0

    async def pick(self, quote: str, candidates: list[EnglishCandidate]) -> int | None:
        self.calls += 1
        if self.raise_:
            raise RuntimeError("boom")
        return self.answer


async def test_model_picker_is_used_only_when_rule_abstains(pipeline: Pipeline) -> None:
    picker = _FixedPicker(1)
    gate = EnglishGate(pipeline.store, pipeline.english.index, picker)
    res = await gate.run("Seek knowledge even if you have to go to China")  # low scores → rule abstains
    if res.candidates:
        assert picker.calls == 1
        assert res.picker == "model" and res.candidates[1].selected
        assert sum(c.selected for c in res.candidates) == 1


async def test_model_refusal_and_failure_leave_nothing_selected(pipeline: Pipeline) -> None:
    for picker in (_FixedPicker(None), _FixedPicker(99), _FixedPicker(0, raise_=True)):
        gate = EnglishGate(pipeline.store, pipeline.english.index, picker)
        res = await gate.run("Seek knowledge even if you have to go to China")
        if res.candidates and res.picker != "rule":
            assert res.picker == "none" and not any(c.selected for c in res.candidates)


@pytest.mark.parametrize(
    ("content", "n", "expected"),
    [
        ('{"pick": 1}', 5, 0),
        ('{"pick": 5}', 5, 4),
        ('{"pick": 0}', 5, None),
        ('{"pick": 6}', 5, None),
        ('{"pick": "2"}', 5, None),
        ('{"pick": true}', 5, None),
        ("not json", 5, None),
        ('{"other": 1}', 5, None),
    ],
)
def test_parse_pick_is_constrained(content: str, n: int, expected: int | None) -> None:
    assert parse_pick(content, n) == expected


def test_picker_prompt_contains_only_candidate_texts() -> None:
    p = OpenAICompatPicker.prompt("quote here", ["first translation", "second translation"])
    assert "QUOTATION: quote here" in p
    assert "1. first translation" in p and "2. second translation" in p
    assert "صحيح" not in p and "ضعيف" not in p  # no judgment vocabulary anywhere near the model
