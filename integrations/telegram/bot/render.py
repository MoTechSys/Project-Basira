"""CheckResponse → Telegram HTML messages.

Rules (SAFETY §1, AGENTS.md §2):
* Every sentence about a quotation is a template from ``messages`` (status / notice / labels / fixed), filled only
  with matcher or corpus fields — the same variables as the web UI (frontend ``QuoteCard.statusVars``).
* ``source_text`` and ``ref_label_ar`` are inserted verbatim (HTML-escaped only). Bold marks come from the API
  ``diff[].quote_chars`` / ``diff[].source_chars`` ranges; nothing is re-ordered, normalised or completed.
* Output is split on block boundaries so no message exceeds Telegram's 4096-character limit and no HTML tag is
  ever cut in half.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from html import escape
from typing import Any

from bot import strings_ar as txt

JSON = Mapping[str, Any]
Messages = Mapping[str, Mapping[str, str]]

TELEGRAM_LIMIT = 4096
BUDGET = 3800  # head-room under the hard limit (measured in UTF-16 units of the HTML source, a superset)
SOURCE_WINDOW_OVER = 400  # same windowing as the web DiffView: long records show the matched window ± pad
SOURCE_WINDOW_PAD = 120
OCR_MAX = 1500

_VAR = re.compile(r"\{(\w+)\}")


def fill(tpl: str, values: Mapping[str, object]) -> str:
    """Replace ``{name}`` only when ``name`` is supplied (identical to the web UI ``fill``)."""
    return _VAR.sub(lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), tpl)


def u16(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def esc(s: str) -> str:
    return escape(s, quote=False)


def attr(s: str) -> str:
    return escape(s, quote=True)


# ------------------------------------------------------------------ text with highlighted ranges
Run = tuple[str, bool]  # (text, bold)


def merge_ranges(ranges: Iterable[Sequence[int]]) -> list[tuple[int, int]]:
    rs = sorted((int(r[0]), int(r[1])) for r in ranges if len(r) == 2 and 0 <= int(r[0]) < int(r[1]))
    out: list[tuple[int, int]] = []
    for a, b in rs:
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _cluster_bounds(text: str, a: int, b: int) -> tuple[int, int]:
    """Widen [a, b) to whole letter clusters: a bold edge between a letter and its combining marks (harakat,
    dagger alif) breaks the glyph in Telegram clients. Characters are never added, removed or re-ordered."""
    while 0 < a < len(text) and unicodedata.combining(text[a]):
        a -= 1
    while b < len(text) and unicodedata.combining(text[b]):
        b += 1
    return a, b


def runs(text: str, marks: Sequence[tuple[int, int]], offset: int = 0) -> list[Run]:
    """Split ``text`` into plain/bold runs; ``marks`` are absolute ranges, ``text`` starts at ``offset``."""
    out: list[Run] = []
    i = 0
    for a0, b0 in marks:
        a, b = _cluster_bounds(text, max(0, a0 - offset), min(len(text), b0 - offset))
        if b <= i or a >= len(text):
            continue
        a = max(a, i)
        if a > i:
            out.append((text[i:a], False))
        out.append((text[a:b], True))
        i = b
    if i < len(text):
        out.append((text[i:], False))
    return out


def runs_html(rs: Sequence[Run]) -> str:
    return "".join(f"<b>{esc(t)}</b>" if bold else esc(t) for t, bold in rs if t)


@dataclass
class Block:
    """One self-contained piece of HTML. ``rs`` blocks can be split further; ``html`` blocks are atomic."""

    html: str = ""
    rs: list[Run] = field(default_factory=list)
    wrap: str = ""  # "blockquote" | "blockquote expandable" | "i" | ""
    prefix: str = ""  # escaped HTML placed before the runs, repeated on continuation pieces

    def render(self) -> str:
        if not self.rs:
            return self.html
        body = self.prefix + runs_html(self.rs)
        if not self.wrap:
            return body
        tag = self.wrap.split()[0]
        return f"<{self.wrap}>{body}</{tag}>"

    def split(self, budget: int) -> list[str]:
        """Render, splitting the runs across pieces when the block alone exceeds ``budget``.

        Each piece is a complete, balanced HTML fragment (the wrapper and prefix are repeated); cuts prefer a
        space so a word — and the marks on its letters — stays whole. Atomic ``html`` blocks are short fixed
        lines and are returned as they are.
        """
        whole = self.render()
        if u16(whole) <= budget or not self.rs:
            return [whole]

        def size(rs: list[Run]) -> int:
            return u16(Block(rs=rs, wrap=self.wrap, prefix=self.prefix).render())

        pieces: list[str] = []
        cur: list[Run] = []
        for text, bold in self.rs:
            rest = text
            while rest:
                lo, hi = 0, len(rest)
                while lo < hi:  # largest prefix of `rest` that still fits next to `cur`
                    mid = (lo + hi + 1) // 2
                    if size([*cur, (rest[:mid], bold)]) <= budget:
                        lo = mid
                    else:
                        hi = mid - 1
                if lo == 0:
                    if cur:
                        pieces.append(Block(rs=cur, wrap=self.wrap, prefix=self.prefix).render())
                        cur = []
                        continue
                    lo = 1  # a single character always fits an empty piece
                if lo < len(rest):
                    sp = rest.rfind(" ", 0, lo)
                    if sp > lo // 2:
                        lo = sp + 1
                cur.append((rest[:lo], bold))
                rest = rest[lo:]
                if rest:
                    pieces.append(Block(rs=cur, wrap=self.wrap, prefix=self.prefix).render())
                    cur = []
        if cur:
            pieces.append(Block(rs=cur, wrap=self.wrap, prefix=self.prefix).render())
        return pieces


def pack(groups: Sequence[Sequence[Block]], budget: int = BUDGET) -> list[str]:
    """Pack groups of blocks (one group per quote) into messages; a group starts a new message when it does not
    fit whole in the current one, and is split on block boundaries only when it is larger than a message."""
    msgs: list[str] = []
    cur = ""

    def flush() -> None:
        nonlocal cur
        if cur:
            msgs.append(cur)
            cur = ""

    for group in groups:
        rendered = [b.render() for b in group if b.html or b.rs]
        whole = "\n".join(rendered)
        if not whole:
            continue
        sep = "\n\n" if cur else ""
        if u16(cur) + u16(sep) + u16(whole) <= budget:
            cur += sep + whole
            continue
        flush()
        if u16(whole) <= budget:
            cur = whole
            continue
        for b in group:
            for piece in b.split(budget):
                sep = "\n" if cur else ""
                if u16(cur) + u16(sep) + u16(piece) > budget:
                    flush()
                    sep = ""
                cur += sep + piece
    flush()
    return msgs


# ------------------------------------------------------------------ templates and variables
def msg(m: Messages, section: str, key: str, values: Mapping[str, object] | None = None) -> str | None:
    tpl = m.get(section, {}).get(key)
    return None if tpl is None else fill(tpl, values or {})


def source_name(match: JSON, m: Messages) -> str:
    corpus = match.get("corpus")
    if corpus == "tanzil":
        return m.get("labels", {}).get("source_quran", "")
    if corpus == "hadeethenc":
        return txt.HADEETHENC_NAME
    book = str((match.get("ref") or {}).get("book", ""))
    return txt.BOOK_NAMES.get(book, book)


def status_vars(q: JSON, m: Messages) -> dict[str, object]:
    matches = q.get("matches") or []
    top = matches[0] if matches else None
    return {
        "source_name": source_name(top, m) if top else "",
        "ref": top.get("ref_label_ar", "") if top else "",
        "count": q.get("total_positions", 0),
        "shown": len(matches),
        "total": q.get("total_positions", 0),
        "n": len(str(q.get("quoted_text", "")).split()),
    }


def notice_vars(key: str, q: JSON, m: Messages) -> dict[str, object]:
    v = status_vars(q, m)
    matches = q.get("matches") or []
    top = matches[0] if matches else None
    claimed = q.get("claimed_source") or {}
    parsed = claimed.get("parsed") or {}
    if key == "claimed_source_mismatch":
        books = parsed.get("books") or []
        v["found_in"] = source_name(top, m) if top else ""
        v["claimed"] = " و".join(txt.BOOK_NAMES.get(b, b) for b in books) or claimed.get("raw", "")
    if key in {"claimed_ayah_mismatch", "claimed_ref_invalid"}:
        v["found_ref"] = top.get("ref_label_ar", "") if top else ""
        raw = claimed.get("raw")
        if raw:
            v["claimed_ref"] = raw
        elif "surah" in parsed:
            to = parsed.get("ayah_to")
            v["claimed_ref"] = f"{parsed['surah']}:{parsed.get('ayah')}" + (f"-{to}" if to else "")
    if key == "arabic_text_at_ref" and "surah" in parsed:
        v["ref"] = f"{parsed['surah']}:{parsed.get('ayah')}"
    if key == "grade_line" and top and top.get("grade"):
        g = top["grade"]
        v.update(grade_source=txt.HADEETHENC_NAME, version=g.get("version", ""), grade_text=g.get("text", ""))
        v["takhrij"] = g.get("takhrij", "")
    if key == "ohd_numbering" and top:
        v["num"] = str((top.get("ref") or {}).get("num", ""))
    return v


# ------------------------------------------------------------------ blocks
def _links(items: Iterable[JSON]) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for link in items:
        url, name = str(link.get("url", "")), str(link.get("name", ""))
        if not url.startswith(("https://", "http://")) or url in seen:
            continue
        seen.add(url)
        out.append(f'<a href="{attr(url)}">{esc(name or url)}</a>')
    return " · ".join(out)


def _source_block(match: JSON) -> Block | None:
    text = str(match.get("source_text") or "")
    if not text:
        return None
    marks = merge_ranges(
        op.get("source_chars", []) for op in match.get("diff") or [] if op.get("op") != "equal"
    )
    offset, shown = 0, text
    rng = match.get("source_text_range")
    if rng and len(text) > SOURCE_WINDOW_OVER:
        offset = max(0, int(rng[0]) - SOURCE_WINDOW_PAD)
        end = min(len(text), int(rng[1]) + SOURCE_WINDOW_PAD)
        shown = text[offset:end]
    rs = runs(shown, marks, offset)
    if offset > 0:
        rs.insert(0, (txt.ELLIPSIS + " ", False))
    if offset + len(shown) < len(text):
        rs.append((" " + txt.ELLIPSIS, False))
    return Block(rs=rs, wrap="blockquote expandable" if len(shown) > 600 else "blockquote")


def quote_blocks(q: JSON, i: int, n: int, m: Messages) -> list[Block]:
    status = str(q.get("status", ""))
    label = m.get("labels", {}).get(status, status)
    head = f"{txt.STATUS_ICON.get(status, '•')} <b>{esc(label)}</b> · {esc(txt.KIND.get(str(q.get('kind')), txt.KIND['unknown']))}"
    if n > 1:
        head = f"<b>{esc(fill(txt.QUOTE_HEADING, {'i': i, 'n': n}))}</b>\n" + head
    blocks = [Block(html=head)]

    matches = list(q.get("matches") or [])
    top = matches[0] if matches else None
    line = msg(m, "status", str(q.get("message_key", "")), status_vars(q, m))
    if line:
        blocks.append(Block(html=esc(line)))

    quoted = str(q.get("quoted_text", ""))
    qmarks = merge_ranges(
        op.get("quote_chars", []) for op in (top or {}).get("diff") or [] if op.get("op") != "equal"
    )
    blocks.append(Block(rs=runs(quoted, qmarks), prefix=f"<b>{esc(txt.YOUR_TEXT)}:</b> «", wrap=""))
    blocks[-1].rs.append(("»", False))

    if top:
        ref = str(top.get("ref_label_ar", ""))
        segments = top.get("source_segments") or []
        blocks.append(Block(html=f"<b>{esc(txt.SOURCE_TEXT)} — {esc(ref)}</b>"))
        if len(segments) > 1:
            for seg in segments:
                blocks.append(Block(html=f"<i>{esc(str(seg.get('ref_label_ar', '')))}</i>"))
                blocks.append(Block(rs=[(str(seg.get("source_text", "")), False)], wrap="blockquote"))
        else:
            sb = _source_block(top)
            if sb:
                blocks.append(sb)
        if qmarks:
            blocks.append(Block(html=f"<i>{esc(txt.DIFF_LEGEND)}</i>"))
        if top.get("grade"):
            g = msg(m, "notice", "grade_line", notice_vars("grade_line", q, m))
            if g:
                blocks.append(Block(html=esc(g)))

    for key in q.get("notice_keys") or []:
        if key == "grade_line":
            continue
        t = msg(m, "notice", str(key), notice_vars(str(key), q, m))
        if t:
            blocks.append(Block(html=f"<i>{esc(t)}</i>"))

    if len(matches) > 1:
        others = " · ".join(
            f'<a href="{attr(str(x.get("source_url", "")))}">{esc(str(x.get("ref_label_ar", "")))}</a>'
            if str(x.get("source_url", "")).startswith("https://")
            else esc(str(x.get("ref_label_ar", "")))
            for x in matches[1:]
        )
        blocks.append(Block(html=f"<b>{esc(txt.OTHER_POSITIONS)}:</b> {others}"))

    link_items: list[JSON] = []
    if top:
        open_src = m.get("labels", {}).get("open_source", "")
        if str(top.get("source_url", "")).startswith("https://"):
            link_items.append({"name": open_src, "url": top["source_url"]})
        link_items.extend(top.get("links") or [])
    link_items.extend(q.get("external_search_links") or [])
    links = _links(link_items)
    if links:
        blocks.append(Block(html=f"🔗 {links}"))
    return blocks


def header_blocks(resp: JSON, m: Messages, *, image: bool) -> list[Block]:
    out: list[Block] = []
    if image and resp.get("ocr_text"):
        out.append(Block(html=f"<b>{esc(txt.OCR_HEADING)}</b>"))
        ocr = str(resp["ocr_text"])
        if len(ocr) > OCR_MAX:
            ocr = ocr[:OCR_MAX] + " " + txt.ELLIPSIS
        out.append(Block(rs=[(ocr, False)], wrap="blockquote expandable"))
    flags = resp.get("flags") or {}
    for key in ("chain_message", "pii_suspected"):
        if flags.get(key):
            t = msg(m, "notice", key)
            if t:
                out.append(Block(html=f"ℹ️ {esc(t)}"))
    if resp.get("extraction_degraded"):
        t = msg(m, "notice", "extraction_degraded")
        if t:
            out.append(Block(html=f"ℹ️ {esc(t)}"))
    return out


def footer_blocks(resp: JSON, m: Messages) -> list[Block]:
    out: list[Block] = []
    t = msg(m, "fixed", str(resp.get("transparency_key") or "transparency_notice"))
    if t:
        out.append(Block(html=f"<i>{esc(t)}</i>"))
    h = str(resp.get("determinism_hash") or "")
    if h:
        out.append(Block(html=f"<code>#{esc(h[:16])}</code>"))
    return out


def render_check(resp: JSON, m: Messages, *, image: bool = False) -> list[str]:
    """Render a ``/v1/check`` or ``/v1/check/image`` response into one or more Telegram HTML messages.

    ``flags.refusal`` (a religious question, not a quotation) → the refusal notice from ``messages`` and nothing
    else: no quote card can be read as an answer to the question.
    """
    flags = resp.get("flags") or {}
    if flags.get("refusal"):
        t = msg(m, "notice", "refusal")
        return [f"ℹ️ {esc(t)}"] if t else []
    quotes = list(resp.get("quotes") or [])
    head = header_blocks(resp, m, image=image)
    if not quotes:
        t = msg(m, "notice", "no_quotes")
        if t:
            head.append(Block(html=esc(t)))
        return pack([head, footer_blocks(resp, m)])
    groups: list[list[Block]] = [head] if head else []
    n = len(quotes)
    groups.extend(quote_blocks(q, i, n, m) for i, q in enumerate(quotes, 1))
    groups.append(footer_blocks(resp, m))
    return pack(groups)


def status_counts(resp: JSON) -> dict[str, int]:
    """Counts by status — the only thing about a result that the bot ever logs."""
    c: dict[str, int] = {}
    for q in resp.get("quotes") or []:
        s = str(q.get("status", "?"))
        c[s] = c.get(s, 0) + 1
    return c
