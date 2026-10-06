"""rich.py: Rich Message documents are valid, verbatim, lexicon-clean and within the Bot API limits."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from html import unescape

import pytest
from app.messages import scan_forbidden

from bot import render, rich
from bot import strings_ar as txt

from conftest import ROOT, load
from fake_telegram import validate_rich

CHECKS = [
    "found_quran",
    "needs_review_quran",
    "not_found_hadith",
    "partial_hadith",
    "multi",
    "no_quotes",
    "refusal",
]


def visible(doc: str) -> str:
    doc = re.sub(r'<tg-button[^>]*text="([^"]*)"[^>]*>', " ", doc)  # copy payload is source text, not prose
    doc = re.sub(r"</?(mark|b|i|sup|code)>", "", doc)  # inline marks never split a verbatim string
    return unescape(re.sub(r"<[^>]+>", " ", doc))


def authored(doc: str, resp: Mapping[str, object]) -> str:
    out = visible(doc)
    fields: list[str] = [str(resp.get("ocr_text") or "")]
    for q in resp.get("quotes") or []:  # type: ignore[attr-defined]
        fields.append(q.get("quoted_text", ""))
        for mt in q.get("matches") or []:
            fields += [mt.get("source_text", ""), mt.get("ref_label_ar", "")]
            fields += [
                s.get(k, "") for s in mt.get("source_segments") or [] for k in ("source_text", "ref_label_ar")
            ]
            fields += [link.get("name", "") for link in mt.get("links") or []]
    for f in sorted((str(f) for f in fields if f), key=len, reverse=True):
        out = out.replace(f, " ")
    for q in resp.get("quotes") or []:  # type: ignore[attr-defined]
        for mt in (q.get("matches") or [])[:1]:
            rng, src = mt.get("source_text_range"), str(mt.get("source_text", ""))
            if rng and len(src) > render.SOURCE_WINDOW_OVER:  # the matched window shown in the pull-quote
                a = max(0, rng[0] - render.SOURCE_WINDOW_PAD)
                out = out.replace(src[a : min(len(src), rng[1] + render.SOURCE_WINDOW_PAD)], " ")
    return out


def docs_for(name: str, m: Mapping[str, Mapping[str, str]]) -> list[str]:
    return rich.render_rich(load(name), m, image=name.startswith("image"), site_url="https://basirapp.site")


@pytest.mark.parametrize("name", [*CHECKS, "image_hadith"])
def test_documents_are_valid_rich_html_within_limits(name: str, m: Mapping[str, Mapping[str, str]]) -> None:
    docs = docs_for(name, m)
    assert docs
    for d in docs:
        assert validate_rich(d) is None, validate_rich(d)
        assert len(d) <= rich.RICH_LIMIT


@pytest.mark.parametrize("name", [*CHECKS, "image_hadith"])
def test_nothing_authored_carries_judgement_vocabulary(name: str, m: Mapping[str, Mapping[str, str]]) -> None:
    resp = load(name)
    assert scan_forbidden(authored("".join(docs_for(name, m)), resp)) == []


def test_static_screens_are_valid_and_clean(m: Mapping[str, Mapping[str, str]]) -> None:
    for doc in (
        rich.welcome(m, "https://basirapp.site"),
        rich.sources(load("sources"), "https://basirapp.site"),
        rich.limits(load("rules")["text"][:1500], "https://basirapp.site"),
        rich.thinking(False),
        rich.thinking(True),
        rich.paragraph("<b>x</b>\ny"),
    ):
        assert validate_rich(doc) is None
        assert scan_forbidden(visible(doc).replace("SAFETY.md", "")) == [] or "rules" in doc


def test_source_is_a_verbatim_pull_quote_with_the_reference_as_credit(
    m: Mapping[str, Mapping[str, str]],
) -> None:
    resp = load("found_quran")
    top = resp["quotes"][0]["matches"][0]
    doc = docs_for("found_quran", m)[0]
    assert (
        f"<aside>{render.esc(top['source_text'])}<cite>{render.esc(top['ref_label_ar'])}</cite></aside>"
        in doc
    )


def test_multi_ayah_quote_shows_one_pull_quote_per_record(m: Mapping[str, Mapping[str, str]]) -> None:
    resp = load("multi")
    segs = resp["quotes"][0]["matches"][0]["source_segments"]
    doc = docs_for("multi", m)[0]
    for seg in segs:
        assert (
            f"<aside>{render.esc(seg['source_text'])}<cite>{render.esc(seg['ref_label_ar'])}</cite></aside>"
            in doc
        )


def test_differences_are_marked_on_both_sides_from_the_api_diff(m: Mapping[str, Mapping[str, str]]) -> None:
    doc = docs_for("needs_review_quran", m)[0]
    assert "<blockquote>إن الله <mark>علي</mark> كل شيء قدير<cite>" in doc
    assert "<mark>عَلَىٰ</mark>" in doc  # whole cluster incl. the dagger alif


def test_long_hadith_window_plus_full_record_in_details(m: Mapping[str, Mapping[str, str]]) -> None:
    resp = load("multi")
    top = resp["quotes"][1]["matches"][0]
    doc = docs_for("multi", m)[0]
    assert txt.FULL_RECORD in doc
    full = re.search(rf"<summary>{re.escape(txt.FULL_RECORD)}</summary><blockquote>(.*?)<cite>", doc)
    assert full and unescape(re.sub(r"</?mark>", "", full.group(1))) == top["source_text"]


def test_status_strip_counts_and_arabic_number_agreement(m: Mapping[str, Mapping[str, str]]) -> None:
    doc = docs_for("multi", m)[0]
    assert "✅ <b>2</b> وُجد" in doc and txt.QUOTES_2 in doc
    assert [txt.quotes_count(n) for n in (1, 2, 3, 10, 11, 103)] == [
        "اقتباس واحد",
        "اقتباسان",
        "3 اقتباسات",
        "10 اقتباسات",
        "11 اقتباسًا",
        "103 اقتباسات",
    ]


def test_metadata_table_holds_only_api_fields(m: Mapping[str, Mapping[str, str]]) -> None:
    doc = docs_for("multi", m)[0]
    table = re.findall(r"<table bordered compact>(.*?)</table>", doc)[1]
    assert "صحيح البخاري" in table and "الصحيحان" in table and "<b>7</b>" in table and "رواه مسلم" in table


def test_buttons_source_search_copy(m: Mapping[str, Mapping[str, str]]) -> None:
    resp = load("not_found_hadith")
    doc = docs_for("not_found_hadith", m)[0]
    for link in resp["quotes"][0]["external_search_links"]:
        assert f'url="{render.attr(link["url"])}"' in doc
    found = docs_for("found_quran", m)[0]
    src = load("found_quran")["quotes"][0]["matches"][0]["source_text"]
    assert f'type="copy_text" text="{render.attr(src)}"' in found


def test_copy_button_is_omitted_when_source_exceeds_256_chars(m: Mapping[str, Mapping[str, str]]) -> None:
    doc = docs_for("partial_hadith", m)[0]
    assert len(load("partial_hadith")["quotes"][0]["matches"][0]["source_text"]) > rich.COPY_MAX
    assert "copy_text" not in doc


def test_image_result_shows_ocr_first_and_never_found(m: Mapping[str, Mapping[str, str]]) -> None:
    doc = docs_for("image_hadith", m)[0]
    assert doc.index(txt.OCR_TITLE) < doc.index("<h3>")
    assert "✅" not in doc and "copy_text" not in doc


def test_refusal_is_a_single_notice(m: Mapping[str, Mapping[str, str]]) -> None:
    [doc] = docs_for("refusal", m)
    assert doc.startswith(f"<aside>ℹ️ {render.esc(m['notice']['refusal'])}</aside>")
    assert "<h3>" not in doc


def test_hostile_api_strings_are_escaped(m: Mapping[str, Mapping[str, str]]) -> None:
    resp = load("not_found_hadith")
    resp["quotes"][0]["quoted_text"] = '</blockquote><tg-button type="url" url="https://evil">x</tg-button>'
    resp["quotes"][0]["external_search_links"] = [{"name": "<b>x", "url": "javascript:alert(1)"}]
    doc = rich.render_rich(resp, m)[0]
    assert validate_rich(doc) is None
    real_buttons = re.findall(r'<tg-button [^>]*url="([^"]*)"', doc)  # actual tags, not escaped text
    assert "https://evil" not in real_buttons and "javascript:" not in doc
    assert "&lt;tg-button" in doc  # the user's markup is shown as text


def test_huge_result_splits_into_several_valid_documents(m: Mapping[str, Mapping[str, str]]) -> None:
    resp = load("partial_hadith")
    resp["quotes"] = resp["quotes"] * 40
    docs = rich.render_rich(resp, m)
    assert len(docs) > 1 and all(validate_rich(d) is None and len(d) <= rich.RICH_LIMIT for d in docs)
    assert sum(d.count("<h3>") for d in docs) == 40


def test_frontend_fixture_renders(m: Mapping[str, Mapping[str, str]]) -> None:
    resp = json.loads((ROOT / "frontend/src/__fixtures__/check_response.json").read_text(encoding="utf-8"))
    resp["flags"]["refusal"] = False
    for d in rich.render_rich(resp, m):
        assert validate_rich(d) is None
        assert scan_forbidden(authored(d, resp)) == []


# ------------------------------------------------------------------ E-063 deep link
def test_check_link_carries_short_text_and_falls_back_when_too_long() -> None:
    from urllib.parse import parse_qs, urlparse

    base = rich.check_link("https://basirapp.site/")
    assert base == "https://basirapp.site/check"
    url = rich.check_link("https://basirapp.site", "قال تعالى: ﴿إن الله مع الصابرين﴾")
    assert url.startswith("https://basirapp.site/check?text=") and len(url) <= rich.DEEP_LINK_MAX
    assert parse_qs(urlparse(url).query)["text"] == [
        "قال تعالى: ﴿إن الله مع الصابرين﴾"
    ]  # round-trips exactly
    # Arabic is 6 chars per letter once percent-encoded: 330 letters exceed 2000 → plain /check
    assert rich.check_link("https://basirapp.site", "ا" * 330) == base
    # boundary: exactly at the cap stays a deep link
    pad = rich.DEEP_LINK_MAX - len("https://basirapp.site/check?text=")
    assert len(rich.check_link("https://basirapp.site", "a" * pad)) == rich.DEEP_LINK_MAX
    assert rich.check_link("https://basirapp.site", "a" * (pad + 1)) == base


def test_render_rich_uses_open_url_for_the_site_button(m: Mapping[str, Mapping[str, str]]) -> None:
    link = rich.check_link("https://basirapp.site", "نص")
    [doc] = rich.render_rich(load("found_quran"), m, site_url="https://basirapp.site", open_url=link)
    assert f'url="{render.attr(link)}"' in doc
    assert validate_rich(doc) is None
