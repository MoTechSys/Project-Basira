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
        (f"قال رسول الله ﷺ: «{H}» رواه البخاري", [(H, "unknown", True)]),  # bracket wins, trailer skipped
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
