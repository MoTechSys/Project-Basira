"""render.py: every sentence comes from messages/*.json, source text is verbatim, HTML is always valid."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from html import unescape
from html.parser import HTMLParser
from typing import Any

import pytest
from app.messages import scan_forbidden

from bot import render
from bot import strings_ar as txt

from conftest import ROOT, load

FIXTURES = [
    "found_quran",
    "needs_review_quran",
    "not_found_hadith",
    "partial_hadith",
    "refusal",
    "no_quotes",
    "multi",
]
ALLOWED_TAGS = {"b", "i", "a", "code", "blockquote"}


class TagChecker(HTMLParser):
    """Telegram HTML subset: known tags only, balanced, ``href`` on <a> only."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in ALLOWED_TAGS:
            self.errors.append(f"tag {tag}")
        for k, _ in attrs:
            if not ((tag == "a" and k == "href") or (tag == "blockquote" and k == "expandable")):
                self.errors.append(f"attr {tag}.{k}")
        self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack or self.stack.pop() != tag:
            self.errors.append(f"unbalanced {tag}")


def valid_html(s: str) -> bool:
    p = TagChecker()
    p.feed(s)
    p.close()
    return not p.errors and not p.stack


def visible(s: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", s))


def authored_text(pieces: list[str], resp: Mapping[str, Any]) -> str:
    """Visible text minus every verbatim corpus/API field — what remains is what the bot (or messages) wrote."""
    out = visible("\n".join(pieces))
    fields: list[str] = [str(resp.get("ocr_text") or "")]
    for q in resp.get("quotes") or []:
        fields.append(str(q.get("quoted_text", "")))
        for mt in q.get("matches") or []:
            fields += [str(mt.get("source_text", "")), str(mt.get("ref_label_ar", ""))]
            fields += [str(s.get("source_text", "")) for s in mt.get("source_segments") or []]
            fields += [str(s.get("ref_label_ar", "")) for s in mt.get("source_segments") or []]
            fields += [str(link.get("name", "")) for link in mt.get("links") or []]
    for f in sorted(fields, key=len, reverse=True):
        if f:
            out = out.replace(f, " ")
    return out


@pytest.mark.parametrize("name", FIXTURES)
def test_every_fixture_renders_valid_bounded_html(name: str, m: Mapping[str, Mapping[str, str]]) -> None:
    pieces = render.render_check(load(name), m)
    assert pieces, name
    for p in pieces:
        assert render.u16(p) <= render.TELEGRAM_LIMIT
        assert valid_html(p), p[:300]


@pytest.mark.parametrize("name", FIXTURES)
def test_no_forbidden_vocabulary_in_anything_authored(name: str, m: Mapping[str, Mapping[str, str]]) -> None:
    resp = load(name)
    assert scan_forbidden(authored_text(render.render_check(resp, m), resp)) == []


def test_web_fixture_from_frontend_renders(m: Mapping[str, Mapping[str, str]]) -> None:
    """The frontend's own response fixture (refusal flag set) → only the refusal notice, verbatim."""
    resp = json.loads((ROOT / "frontend/src/__fixtures__/check_response.json").read_text(encoding="utf-8"))
    assert render.render_check(resp, m) == [f"ℹ️ {render.esc(m['notice']['refusal'])}"]
    resp["flags"]["refusal"] = False
    pieces = render.render_check(resp, m)
    assert all(valid_html(p) for p in pieces)
    assert scan_forbidden(authored_text(pieces, resp)) == []


def test_every_status_has_an_icon_and_a_label(m: Mapping[str, Mapping[str, str]]) -> None:
    for status in ("found", "partial_match", "needs_review", "not_found"):
        assert status in txt.STATUS_ICON
        assert m["labels"][status]


def test_source_text_is_verbatim(m: Mapping[str, Mapping[str, str]]) -> None:
    for name in ("found_quran", "needs_review_quran", "multi"):
        resp = load(name)
        shown = visible("\n".join(render.render_check(resp, m)))
        for q in resp["quotes"]:
            top = q["matches"][0]
            segs = top["source_segments"]
            for full in [s["source_text"] for s in segs] if len(segs) > 1 else [top["source_text"]]:
                t, rng = full, top["source_text_range"]
                if len(full) > render.SOURCE_WINDOW_OVER and rng:  # long record: the exact window, verbatim
                    a = max(0, rng[0] - render.SOURCE_WINDOW_PAD)
                    t = full[a : min(len(full), rng[1] + render.SOURCE_WINDOW_PAD)]
                assert t in shown, name
            assert top["ref_label_ar"] in shown


def test_long_hadith_shows_the_matched_window_verbatim(m: Mapping[str, Mapping[str, str]]) -> None:
    resp = load("partial_hadith")
    top = resp["quotes"][0]["matches"][0]
    shown = visible(render.render_check(resp, m)[0])
    a, b = top["source_text_range"]
    assert top["source_text"][a:b] in shown


def test_diff_words_are_bold_from_the_api_ranges(m: Mapping[str, Mapping[str, str]]) -> None:
    resp = load("needs_review_quran")
    out = render.render_check(resp, m)[0]
    q = resp["quotes"][0]
    op = next(o for o in q["matches"][0]["diff"] if o["op"] != "equal")
    qa, qb = op["quote_chars"]
    assert f"<b>{q['quoted_text'][qa:qb]}</b>" in out  # «علي» in the user's text
    sa, sb = op["source_chars"]
    src = q["matches"][0]["source_text"]
    bolds = re.findall(r"<b>([^<]*)</b>", out)
    assert any(src[sa:sb] in b for b in bolds)  # «عَلَى» (+ its dagger alif) in the source
    assert m["notice"]["many_positions"].split("{")[0] in visible(out)


def test_bold_never_splits_a_letter_from_its_marks() -> None:
    text = "إِنَّ ٱللَّهَ عَلَىٰ كُلِّ"
    a = text.index("عَلَى")
    rs = render.runs(text, [(a, a + 5)])  # API range stops before the dagger alif U+0670
    bold = "".join(t for t, b in rs if b)
    assert bold == "عَلَىٰ"
    assert "".join(t for t, _ in rs) == text


def test_not_found_has_search_links_and_no_candidates(m: Mapping[str, Mapping[str, str]]) -> None:
    resp = load("not_found_hadith")
    out = render.render_check(resp, m)[0]
    for link in resp["quotes"][0]["external_search_links"]:
        assert link["name"] in out and render.attr(link["url"]) in out
    assert txt.SOURCE_TEXT not in out
    assert m["status"]["not_found"] in visible(out)


def test_no_quotes_message_and_transparency(m: Mapping[str, Mapping[str, str]]) -> None:
    out = visible(render.render_check(load("no_quotes"), m)[0])
    assert m["notice"]["no_quotes"] in out
    assert m["fixed"]["transparency_notice"] in out


def test_image_shows_ocr_first_and_never_found(m: Mapping[str, Mapping[str, str]]) -> None:
    resp = load("image_hadith")
    out = render.render_check(resp, m, image=True)[0]
    assert out.index(txt.OCR_HEADING) < out.index(m["labels"]["needs_review"])
    assert all(q["status"] != "found" for q in resp["quotes"])
    assert m["labels"]["found"] + "</b>" not in out


def test_claimed_source_mismatch_names_both_books(m: Mapping[str, Mapping[str, str]]) -> None:
    out = visible("\n".join(render.render_check(load("multi"), m)))
    assert "وُجد النص في صحيح البخاري، وليس في صحيح مسلم المذكور في نصك." in out


def test_user_text_is_escaped(m: Mapping[str, Mapping[str, str]]) -> None:
    resp = load("not_found_hadith")
    resp["quotes"][0]["quoted_text"] = '<a href="javascript:x">x</a> & <b>'
    out = render.render_check(resp, m)[0]
    assert "&lt;a href" in out and "&amp;" in out and valid_html(out)


def test_non_https_links_are_dropped(m: Mapping[str, Mapping[str, str]]) -> None:
    resp = load("not_found_hadith")
    resp["quotes"][0]["external_search_links"] = [{"name": "x", "url": "javascript:alert(1)"}]
    assert "javascript:" not in render.render_check(resp, m)[0]


def test_split_respects_limit_and_keeps_every_character(m: Mapping[str, Mapping[str, str]]) -> None:
    resp = load("partial_hadith")
    q = resp["quotes"][0]
    resp["quotes"] = [json.loads(json.dumps(q)) for _ in range(12)]  # 12 long cards
    pieces = render.render_check(resp, m)
    assert len(pieces) > 1
    assert all(render.u16(p) <= render.BUDGET and valid_html(p) for p in pieces)
    assert visible("\n".join(pieces)).count(q["quoted_text"].split()[0]) >= 12


def test_one_giant_block_is_split_on_balanced_tags() -> None:
    word = "بِسْمِ ٱللَّهِ "
    block = render.Block(rs=[(word * 900, False), ("x" * 50, True)], wrap="blockquote")
    pieces = block.split(1000)
    assert len(pieces) > 5
    assert all(render.u16(p) <= 1000 and valid_html(p) for p in pieces)
    assert "".join(visible(p) for p in pieces) == word * 900 + "x" * 50


def test_fill_leaves_unknown_placeholders() -> None:
    assert render.fill("{a} و {b}", {"a": 1}) == "1 و {b}"
