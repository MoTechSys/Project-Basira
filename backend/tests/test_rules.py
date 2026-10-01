"""Deterministic extractor: brackets, introducers (longest-first), trailers, claimed sources, detectors."""

from __future__ import annotations

import pytest

from app.extract.rules import (
    detect_chain_message,
    detect_pii,
    detect_refusal,
    extract_spans,
    language_of,
    parse_claimed_source,
)

Q = "إن الله مع الصابرين"  # 4 tokens
H = "إنما الأعمال بالنيات"  # 3 tokens


def spans_of(text: str) -> list[tuple[str, str, bool]]:
    return [(text[s.start : s.end], s.kind, s.marked) for s in extract_spans(text)]


@pytest.mark.parametrize(
    "text,expected",
    [
        (f"قال تعالى: ﴿{Q}﴾", [(Q, "quran", True)]),
        (f"قال الله تعالى {Q}. لا تنسوا الأذكار.", [(Q, "quran", False)]),  # «تعالى» not swallowed
        (f"في خطبة الجمعة ذكر الإمام قوله تعالى: {Q}.", [(Q, "quran", False)]),
        (f"{Q} — صدق الله العظيم", [(Q, "quran", False)]),
        (f"وفي الحديث: {H}", [(H, "hadith_matn", False)]),
        (
            f"قال رسول الله ﷺ {H} وإنما لكل امرئ ما نوى",
            [(f"{H} وإنما لكل امرئ ما نوى", "hadith_matn", False)],
        ),
        (f"اليوم جميل. {H} رواه البخاري. انشرها", [(H, "hadith_matn", False)]),
        (f"قال رسول الله ﷺ: «{H}» رواه البخاري", [(H, "hadith_matn", True)]),  # bracket wins; kind from context (E-029)
        (f'قال تعالى: "{Q}"', [(Q, "quran", True)]),  # plain quotes + introducer → quran (E-029)
        (f'"{Q}" [البقرة: 153]', [(Q, "quran", True)]),  # plain quotes + claimed surah:ayah → quran (E-029)
        (f'"{H}"', [(H, "unknown", True)]),  # no context → unknown
        ("[البقرة: 255]", []),  # ref-only bracket is not a quote
        ("ذهبت إلى السوق واشتريت خبزا", []),
    ],
)
def test_extract_spans(text: str, expected: list[tuple[str, str, bool]]) -> None:
    assert spans_of(text) == expected


def test_span_offsets_slice_exactly() -> None:
    text = f"🌙 قال تعالى: ﴿{Q}﴾ 🤲🏽 وقال ﷺ: «{H}»."
    for s in extract_spans(text):
        seg = text[s.start : s.end]
        assert seg in (Q, H)


def test_claimed_source_parsing() -> None:
    assert parse_claimed_source("رواه البخاري") == {
        "raw": "رواه البخاري",
        "parsed": {"books": ["sahih_al-bukhari"]},
    }
    assert parse_claimed_source("متفق عليه")["parsed"]["muttafaq"] is True  # type: ignore[index]
    assert parse_claimed_source("[البقرة: 255]")["parsed"] == {"surah": 2, "ayah": 255, "ayah_to": None}  # type: ignore[index]
    assert parse_claimed_source("Quran 9:11")["parsed"]["surah"] == 9  # type: ignore[index]
    assert parse_claimed_source("قال أحمد إن الطقس جميل") is None  # bare «أحمد» is ambiguous
    sp = extract_spans(f"«{H}» أخرجه مسلم")
    assert sp[0].claimed_source and sp[0].claimed_source["parsed"]["books"] == ["sahih_muslim"]


def test_detectors() -> None:
    assert detect_chain_message("انشرها تؤجر")
    assert detect_chain_message("Forward this to ten people")
    assert not detect_chain_message(Q)
    assert detect_refusal("هل هذا الحديث صحيح؟")
    assert detect_refusal("ما حكم السفر وحدي؟")
    assert detect_refusal("Is it permissible to fast on Friday?")
    assert not detect_refusal(H)
    assert detect_pii("0551234567")
    assert detect_pii("a@b.co")
    assert detect_pii("1012345678")
    assert not detect_pii("رقم الآية 255 من سورة البقرة")


def test_language_of() -> None:
    assert language_of(Q) == "ar"
    assert language_of("Verily Allah is with the patient") == "en"
    assert language_of("...") == "other"


@pytest.mark.parametrize(
    "text",
    [
        f"قال رسول الله صلَّى اللهُ عَلَيْهِ وسلَّمَ:\n«{H}»\nرواه البخاري",  # OCR output with tashkeel honorific
        f"قال رسول الله صلى الله عليه وسلم {H} وإنما لكل امرئ ما نوى",
        f"قال النبي عليه الصلاة والسلام {H} وإنما لكل امرئ ما نوى",
    ],
)
def test_honorific_never_becomes_a_quote(text: str) -> None:
    for s in extract_spans(text):
        seg = text[s.start : s.end]
        assert "صل" not in seg[:4] and "عليه" not in seg[:6], seg
        assert seg.startswith(H)


def test_bare_qala_is_not_an_introducer_without_saws() -> None:
    """E-028: «قال فلان: …» (a scholar, a narrator) must not become a quote; «قال ﷺ: …» must."""
    assert extract_spans("قال ابن عثيمين رحمه الله إن هذا الأمر واضح في كتب الفقه") == []
    spans = extract_spans("قال ﷺ: الدين النصيحة لله ولكتابه ولرسوله")
    assert len(spans) == 1 and spans[0].kind == "hadith_matn"
    text = "قال ﷺ: الدين النصيحة لله ولكتابه ولرسوله"
    assert text[spans[0].start : spans[0].end] == "الدين النصيحة لله ولكتابه ولرسوله"


@pytest.mark.parametrize(
    "inner",
    ["رواه مسلم", "رواه البخاري ومسلم", "متفق عليه", "سورة البقرة, آية 257", "البقرة: 255", "عليه الصلاة والسلام", "2:255"],
)
def test_bracketed_attribution_is_not_a_quote(inner: str) -> None:
    """E-030: a bracketed reference/attribution is never checked as a quotation; the quote next to it is."""
    text = f'قال رسول الله ﷺ: "{H}" ({inner})'
    got = [text[s.start : s.end] for s in extract_spans(text)]
    assert got == [H]
