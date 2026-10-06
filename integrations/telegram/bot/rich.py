"""CheckResponse → one Telegram *Rich Message* (Bot API 10.3, ``sendRichMessage`` / ``editMessageText.rich_message``).

Layout of a result (right-to-left):

    ## 🔎 نتيجة الفحص                       heading
    ✅ 1  ⚠️ 1   · اقتباسان                  status strip (counts from the API)
    ─────────────────
    ### ✅ وُجد · قرآن                        per quote: state heading
    <status sentence>                        messages.status[message_key]
    ┃ نصك ……… <mark>علي</mark> ……            blockquote, cite «نصك — كما كتبته»
    ┃ ﴿source_text﴾ <mark>…</mark>           pull-quote (verbatim), credit = ref_label_ar
    | الموضع | المصدر | المجموعة | …|          compact bordered table (API fields only)
    ▸ ℹ️ ملاحظات (n)                         <details>, notices from messages.notice
    ▸ 📍 مواضع أخرى (n)                      <details>, linked refs
    [📖 المصدر] [ابحث في الدرر] [📋 نسخ]      in-message buttons (url / copy_text)
    ─────────────────
    footer: transparency notice · بصمة الفحص

Rules are those of render.py: every sentence is a ``messages`` template; ``source_text`` / ``ref_label_ar`` are
verbatim (HTML-escaped only); highlights are the API ``diff`` ranges (widened to whole letter clusters).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from bot import render
from bot import strings_ar as txt
from bot.render import (
    JSON,
    Messages,
    attr,
    esc,
    merge_ranges,
    msg,
    notice_vars,
    runs,
    source_name,
    status_vars,
)

RICH_LIMIT = 32768  # UTF-8 characters per rich message (Bot API "Rich Message Limits")
RICH_BUDGET = 30000
COPY_MAX = 256  # CopyTextButton.text 1-256 characters
BUTTON_TEXT_MAX = 40

ORDER = ("found", "partial_match", "needs_review", "not_found")


def _marked(text: str, marks: Sequence[tuple[int, int]], offset: int = 0) -> str:
    return "".join(f"<mark>{esc(t)}</mark>" if hot else esc(t) for t, hot in runs(text, marks, offset) if t)


def _diff_marks(match: JSON | None, side: str) -> list[tuple[int, int]]:
    if not match:
        return []
    key = "quote_chars" if side == "quote" else "source_chars"
    return merge_ranges(op.get(key, []) for op in match.get("diff") or [] if op.get("op") != "equal")


def _https(url: object) -> str:
    u = str(url or "")
    return u if u.startswith("https://") else ""


def _button(label: str, *, url: str = "", copy: str = "", style: str = "") -> str:
    label = label if len(label) <= BUTTON_TEXT_MAX else label[: BUTTON_TEXT_MAX - 1] + "…"
    st = f' style="{style}"' if style else ""
    if url:
        return f'<tg-button type="url"{st} url="{attr(url)}">{esc(label)}</tg-button>'
    return f'<tg-button type="copy_text"{st} text="{attr(copy[:COPY_MAX])}">{esc(label)}</tg-button>'


def _table(rows: Sequence[tuple[str, str]]) -> str:
    """Two-column key/value table; values are already-escaped HTML (inline formatting only)."""
    body = "".join(f"<tr><th>{esc(k)}</th><td>{v}</td></tr>" for k, v in rows if v)
    return f"<table bordered compact>{body}</table>" if body else ""


def _status_strip(quotes: Sequence[JSON], m: Messages) -> str:
    counts: dict[str, int] = {}
    for q in quotes:
        counts[str(q.get("status"))] = counts.get(str(q.get("status")), 0) + 1
    cells = [
        f"{txt.STATUS_ICON[s]} <b>{counts[s]}</b> {esc(m.get('labels', {}).get(s, s))}"
        for s in ORDER
        if counts.get(s)
    ]
    return " · ".join(cells)


def _source_html(match: JSON) -> str:
    """The matched source text: whole when short, the matched window (± pad, like the web DiffView) when long."""
    text = str(match.get("source_text") or "")
    marks = _diff_marks(match, "source")
    rng = match.get("source_text_range")
    if rng and len(text) > render.SOURCE_WINDOW_OVER:
        a = max(0, int(rng[0]) - render.SOURCE_WINDOW_PAD)
        b = min(len(text), int(rng[1]) + render.SOURCE_WINDOW_PAD)
        inner = _marked(text[a:b], marks, a)
        return ("… " if a > 0 else "") + inner + (" …" if b < len(text) else "")
    return _marked(text, marks)


def quote_html(q: JSON, i: int, n: int, m: Messages, *, image: bool) -> str:
    status = str(q.get("status", ""))
    label = m.get("labels", {}).get(status, status)
    kind = txt.KIND.get(str(q.get("kind")), txt.KIND["unknown"])
    matches = list(q.get("matches") or [])
    top = matches[0] if matches else None
    parts: list[str] = []

    counter = f" <sup>{i}/{n}</sup>" if n > 1 else ""
    parts.append(f"<h3>{txt.STATUS_ICON.get(status, '•')} {esc(label)} · {esc(kind)}{counter}</h3>")

    line = msg(m, "status", str(q.get("message_key", "")), status_vars(q, m))
    if line:
        parts.append(f"<p>{esc(line)}</p>")

    qmarks = _diff_marks(top, "quote")
    parts.append(
        f"<blockquote>{_marked(str(q.get('quoted_text', '')), qmarks)}<cite>{esc(txt.YOUR_TEXT_CITE)}</cite></blockquote>"
    )

    if top:
        ref = str(top.get("ref_label_ar", ""))
        segments = top.get("source_segments") or []
        if len(segments) > 1:  # B07: one verbatim record per ayah, never a joined line
            for seg in segments:
                parts.append(
                    f"<aside>{esc(str(seg.get('source_text', '')))}<cite>{esc(str(seg.get('ref_label_ar', '')))}</cite></aside>"
                )
        else:
            parts.append(f"<aside>{_source_html(top)}<cite>{esc(ref)}</cite></aside>")
        full = str(top.get("source_text") or "")
        if len(full) > render.SOURCE_WINDOW_OVER and top.get("source_text_range"):
            parts.append(
                f"<details><summary>{esc(txt.FULL_RECORD)}</summary>"
                f"<blockquote>{_marked(full, _diff_marks(top, 'source'))}<cite>{esc(ref)}</cite></blockquote></details>"
            )

        rows: list[tuple[str, str]] = [
            (txt.META_SOURCE, esc(source_name(top, m))),
            (txt.META_TIER, esc(txt.TIER.get(str(top.get("collection_tier")), ""))),
        ]
        total = int(q.get("total_positions") or 0)
        if total > 1:
            rows.append((txt.META_POSITIONS, f"<b>{total}</b>"))
        kinds = [m.get("labels", {}).get(f"diff_{k}", "") for k in top.get("diff_kinds") or []]
        if any(kinds):
            rows.append((txt.META_DIFF, esc("، ".join(k for k in dict.fromkeys(kinds) if k))))
        reason = q.get("review_reason")
        if reason and reason in txt.REASON:
            rows.append((txt.META_REASON, esc(txt.REASON[str(reason)])))
        claimed = (q.get("claimed_source") or {}).get("raw")
        if claimed:
            rows.append((txt.META_CLAIMED, esc(str(claimed))))
        parts.append(_table(rows))
        if top.get("grade"):
            g = msg(m, "notice", "grade_line", notice_vars("grade_line", q, m))
            if g:
                parts.append(f"<p><b>{esc(g)}</b></p>")
    elif q.get("review_reason") in txt.REASON:
        parts.append(_table([(txt.META_REASON, esc(txt.REASON[str(q["review_reason"])]))]))

    notes = [
        t
        for k in q.get("notice_keys") or []
        if k != "grade_line" and (t := msg(m, "notice", str(k), notice_vars(str(k), q, m)))
    ]
    if notes:
        items = "".join(f"<li>{esc(t)}</li>" for t in notes)
        parts.append(
            f"<details><summary>{esc(txt.NOTES.replace('{n}', str(len(notes))))}</summary><ul>{items}</ul></details>"
        )

    if len(matches) > 1:
        items = "".join(
            f'<li><a href="{attr(u)}">{esc(str(x.get("ref_label_ar", "")))}</a></li>'
            if (u := _https(x.get("source_url")))
            else f"<li>{esc(str(x.get('ref_label_ar', '')))}</li>"
            for x in matches[1:]
        )
        parts.append(
            f"<details><summary>{esc(txt.POSITIONS.replace('{n}', str(len(matches) - 1)))}</summary><ul>{items}</ul></details>"
        )

    buttons: list[str] = []
    if top and (u := _https(top.get("source_url"))):
        buttons.append(_button(txt.OPEN_SOURCE, url=u, style="primary"))
    seen: set[str] = set()
    for link in [*(top.get("links") or [] if top else []), *(q.get("external_search_links") or [])]:
        u = _https(link.get("url"))
        if u and u not in seen and u != _https(top.get("source_url") if top else ""):
            seen.add(u)
            buttons.append(_button(str(link.get("name") or u), url=u))
    if top and (src := str(top.get("source_text") or "").strip()) and len(src) <= COPY_MAX and not image:
        buttons.append(_button(txt.COPY_SOURCE, copy=src))
    if buttons:
        rows_html = "".join(
            f"<tg-button-row>{''.join(buttons[k : k + 2])}</tg-button-row>" for k in range(0, len(buttons), 2)
        )
        parts.append(rows_html)
    return "".join(p for p in parts if p)


def render_rich(resp: JSON, m: Messages, *, image: bool = False, site_url: str = "") -> list[str]:
    """One or more rich-message HTML documents (normally exactly one; split only past 30 000 characters)."""
    flags = resp.get("flags") or {}
    quotes = list(resp.get("quotes") or [])
    head: list[str] = [f"<h2>{esc(txt.RESULT_TITLE)}</h2>"]

    if flags.get("refusal"):  # a religious question: the refusal notice only, nothing that reads as an answer
        t = msg(m, "notice", "refusal") or ""
        return [f"<aside>ℹ️ {esc(t)}</aside>" + _footer(resp, m, site_url)]

    if image and resp.get("ocr_text"):
        ocr = str(resp["ocr_text"])
        if len(ocr) > render.OCR_MAX:
            ocr = ocr[: render.OCR_MAX] + " …"
        head.append(
            f"<details open><summary>{esc(txt.OCR_TITLE)}</summary><blockquote>{esc(ocr)}</blockquote></details>"
        )
    banners = [k for k in ("chain_message", "pii_suspected") if flags.get(k)]
    if resp.get("extraction_degraded"):
        banners.append("extraction_degraded")
    for k in banners:
        note = msg(m, "notice", k)
        if note:
            head.append(f"<blockquote>ℹ️ {esc(note)}</blockquote>")

    if not quotes:
        t = msg(m, "notice", "no_quotes") or ""
        return ["".join(head) + f"<p>{esc(t)}</p>" + _footer(resp, m, site_url)]

    head.append(f"<p>{_status_strip(quotes, m)} · <b>{esc(txt.quotes_count(len(quotes)))}</b></p>")
    docs: list[str] = []
    cur = "".join(head)
    for i, q in enumerate(quotes, 1):
        block = "<hr/>" + quote_html(q, i, len(quotes), m, image=image)
        if len(cur) + len(block) > RICH_BUDGET and cur:
            docs.append(cur)
            cur = ""
        cur += block
    cur += _footer(resp, m, site_url)
    docs.append(cur)
    return docs


def _footer(resp: JSON, m: Messages, site_url: str) -> str:
    out = "<hr/>"
    t = msg(m, "fixed", str(resp.get("transparency_key") or "transparency_notice"))
    h = str(resp.get("determinism_hash") or "")
    fp = f"<br/>{esc(txt.FINGERPRINT)}: <code>{esc(h[:16])}</code>" if h else ""
    if t:
        out += f"<footer>{esc(t)}{fp}</footer>"
    if site_url:
        out += f"<tg-button-row>{_button(txt.OPEN_SITE, url=site_url.rstrip('/') + '/check', style='success')}</tg-button-row>"
    return out


# ------------------------------------------------------------------ static screens
def welcome(m: Messages, site_url: str) -> str:
    fixed = m.get("fixed", {})
    labels = m.get("labels", {})
    states = "".join(f"<tr><td>{txt.STATUS_ICON[s]} <b>{esc(labels.get(s, s))}</b></td></tr>" for s in ORDER)
    return (
        f"<h1>{esc(txt.WELCOME_TITLE)}</h1>"
        f"<p><b>{esc(txt.WELCOME_LEAD)}</b><br/><i>{esc(txt.WELCOME_LEAD_EN)}</i></p>"
        f"<h3>{esc(txt.HOW_TITLE)}</h3><ol><li>{esc(txt.HOW_1)}</li><li>{esc(txt.HOW_2)}</li><li>{esc(txt.HOW_3)}</li></ol>"
        f"<h3>{esc(txt.WHAT_YOU_GET)}</h3><ul><li>{esc(txt.WYG_1)}</li><li>{esc(txt.WYG_2)}</li><li>{esc(txt.WYG_3)}</li></ul>"
        f"<h3>{esc(txt.STATE_LEGEND)}</h3><table bordered striped compact>{states}</table>"
        f"<details><summary>{esc(txt.ABOUT_TITLE)}</summary>"
        f"<p>{esc(fixed.get('transparency_notice', ''))}</p><p>{esc(fixed.get('privacy_notice', ''))}</p></details>"
        f"<hr/><footer>{esc(fixed.get('footer', ''))}</footer>"
        f"<tg-button-row>{_button(txt.OPEN_SITE, url=site_url.rstrip('/') + '/check', style='success')}</tg-button-row>"
    )


def sources(items: Sequence[Mapping[str, Any]], api_url: str) -> str:
    rows = "".join(
        f"<tr><td><b>{esc(str(s.get('name', '')))}</b></td><td>{esc(str(s.get('version', '')))}</td>"
        f"<td>{(f'{s["records"]:,}' if isinstance(s.get('records'), int) else '—')}</td></tr>"
        for s in items
    )
    lic = "".join(
        f"<li><b>{esc(str(s.get('name', '')))}</b> — {esc(str(s.get('license', '')))}</li>" for s in items
    )
    return (
        f"<h2>{esc(txt.SOURCES_TITLE)}</h2>"
        f"<table bordered striped compact><tr><th>{esc(txt.META_SOURCE)}</th><th>{esc(txt.SOURCE_VERSION)}</th><th>{esc(txt.SOURCE_RECORDS)}</th></tr>{rows}</table>"
        f"<details><summary>{esc(txt.SOURCE_LICENSE)}</summary><ul>{lic}</ul></details>"
        f"<footer><code>{esc(api_url)}/v1/sources</code></footer>"
    )


def limits(text: str, api_url: str) -> str:
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    first, rest = (paras[0], paras[1:]) if paras else ("", [])
    body = "".join(f"<p>{esc(p).replace(chr(10), '<br/>')}</p>" for p in rest)
    url = f"{api_url}/v1/rules?ui_lang=ar"
    return (
        f"<h2>📏 {esc(txt.LIMITS_TITLE)}</h2><p><i>{esc(first)}</i></p>"
        f"<details open><summary>{esc(txt.LIMITS_TITLE)}</summary>{body}</details>"
        f"<tg-button-row>{_button(txt.LIMITS_FULL, url=url)}</tg-button-row>"
    )


def thinking(image: bool) -> str:
    """Placeholder shown while the API works (``<tg-thinking>`` is draft-only, so a styled paragraph)."""
    return f"<p>⏳ <i>{esc(txt.THINKING_IMAGE if image else txt.THINKING)}</i></p>"


def paragraph(classic_html: str) -> str:
    """Wrap a classic-HTML status line (b/i/a/code/blockquote only) as a rich document."""
    return "<p>" + classic_html.replace("\n", "<br/>") + "</p>"
