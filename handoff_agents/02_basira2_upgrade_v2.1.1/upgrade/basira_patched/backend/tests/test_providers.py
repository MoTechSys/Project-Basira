"""Provider layer (ADR-005): proposals are relocated verbatim; failures degrade, never crash."""

from __future__ import annotations

import os

import pytest

from app.normalize import loose_tokens
from app.providers import MockLLM, MockVision, ProviderError, make_llm, make_vision, relocate
from app.providers.base import ProposedQuote
from app.providers.openai_compat import _parse_quotes

TEXT = "قال تعالى: ﴿إن الله مع الصابرين﴾ ثم قال: إن الله مع الصابرين."


def test_relocate_prefers_occurrence_near_hint() -> None:
    needle = "إن الله مع الصابرين"
    first = TEXT.find(needle)
    second = TEXT.find(needle, first + 1)
    assert relocate(TEXT, ProposedQuote(needle, start=second - 1)) == (second, second + len(needle))
    assert relocate(TEXT, ProposedQuote(needle)) == (first, first + len(needle))


def test_relocate_drops_non_verbatim() -> None:
    assert relocate(TEXT, ProposedQuote("إن الله مع الصابرين والمتقين")) is None
    assert relocate(TEXT, ProposedQuote("   ")) is None


async def test_mock_llm_wraps_rules_and_heuristic() -> None:
    res = await MockLLM().extract("قال رسول الله ﷺ إنما الأعمال بالنيات وإنما لكل امرئ ما نوى")
    assert res.provider == "mock"
    assert any("الأعمال" in q.quoted_text for q in res.quotes)
    for q in res.quotes:
        assert relocate("قال رسول الله ﷺ إنما الأعمال بالنيات وإنما لكل امرئ ما نوى", q) is not None


async def test_mock_llm_no_quotes_in_plain_text() -> None:
    res = await MockLLM().extract("اليوم طقس جميل وذهبت إلى السوق")
    assert res.quotes == ()


async def test_mock_vision_fixture_and_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    v = MockVision()
    r = await v.ocr(b"\x89PNG", mime="image/png")
    assert "الصابرين" in loose_tokens(r.text)  # fixture carries tashkeel
    with pytest.raises(ProviderError):
        await v.ocr(b"", mime="image/png")
    with pytest.raises(ProviderError):
        await v.ocr(b"x", mime="application/pdf")
    monkeypatch.setenv("BASIRA_MOCK_OCR_FAIL", "1")
    with pytest.raises(ProviderError):
        await v.ocr(b"x", mime="image/png")


def test_factory_falls_back_to_mock_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("VISION_API_KEY", raising=False)
    assert make_llm("openai-compatible").name == "mock"
    assert make_vision("openai-compatible").name == "mock"
    assert make_llm("nonsense").name == "mock"
    assert os.environ.get("LLM_API_KEY") is None


def test_factory_builds_real_adapter_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL", "m1")
    assert make_llm("openai-compatible").name == "openai-compatible:m1"


def test_parse_quotes_schema_hardening() -> None:
    q = _parse_quotes(
        '{"quotes":[{"text":"إن الله مع الصابرين","kind":"quran"},{"text":"","kind":"x"},5,{"text":"abc","kind":"weird"}]}'
    )
    assert [x.kind for x in q] == ["quran", "unknown"]
    with pytest.raises(ProviderError):
        _parse_quotes("not json")
    with pytest.raises(ProviderError):
        _parse_quotes('{"nope":[]}')
