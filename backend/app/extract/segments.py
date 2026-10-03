"""Citation segmentation — turns each extracted quote into typed segments.

IslamicEval 2026 decomposes every citation into ``Ayah`` | ``matn`` | ``isnad`` | ``claimed_source``.
Basira already finds the quoted text (``rules.extract_spans`` ∪ provider proposals); this module adds
the deterministic parts around it, all as code-point offsets into the ORIGINAL text:

* **explicit model tags** — LLM answers often wrap citations in ``<aya_start>…<aya_end>`` /
  ``<hadith_start>…<hadith_end>``; those are authoritative boundaries and kinds;
* **claimed_source** — the attribution right after (preferred) or before the quote:
  «(البقرة: 255)», «[سورة البقرة، الآية 255]», «رواه البخاري ومسلم», «متفق عليه», «صحيح مسلم: 2564»;
* **isnad** — the narration chain that introduces a hadith: «عن أبي هريرة رضي الله عنه قال: قال رسول
  الله ﷺ:», «حدثنا … عن … قال»; it runs from the narrator marker to the end of the introducer;
* **boundary tightening** — trailing sentence punctuation / closing marks / markdown are not part of
  a quote; leading ones neither.

Nothing here touches the status decision: segments are presentation + evaluation metadata. The quote
text that is checked is unchanged except for boundary trimming of punctuation (never letters).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.extract.rules import _QURAN_REF, BOOK_ALIASES

SegType = Literal["Ayah", "matn", "isnad", "claimed_source"]

# ---------------------------------------------------------------- explicit tags

_TAG = re.compile(r"<(aya|hadith)_start>(.*?)<\1_end>", re.S)


@dataclass(slots=True)
class TaggedSpan:
    start: int
    end: int
    kind: str  # quran | hadith_matn


def tagged_spans(text: str) -> list[TaggedSpan]:
    out: list[TaggedSpan] = []
    for m in _TAG.finditer(text):
        a, b = m.start(2), m.end(2)
        a, b = tighten(text, a, b)
        if b > a:
            out.append(TaggedSpan(a, b, "quran" if m.group(1) == "aya" else "hadith_matn"))
    return out


def strip_tags_mask(text: str) -> list[tuple[int, int]]:
    """Char ranges of the tag tokens themselves (so they are never part of any segment)."""
    return [(m.start(), m.end()) for m in re.finditer(r"</?(?:aya|hadith)_(?:start|end)>", text)]


# ---------------------------------------------------------------- boundaries

_EDGE = set(" \t\n\r.,،؛;:!?؟*_`>#-–—…\"'“”«»﴾﴿()[]{}")
_OPEN = set("\"'“«﴿([{")
_CLOSE = set("\"'”»﴾)]}")


def tighten(text: str, a: int, b: int) -> tuple[int, int]:
    """Drop leading/trailing punctuation, quote marks and markdown from a span (never letters)."""
    while a < b and text[a] in _EDGE:
        a += 1
    while b > a and text[b - 1] in _EDGE:
        b -= 1
    # drop a tag that sits on an edge
    for tag in ("<aya_end>", "<hadith_end>", "<aya_start>", "<hadith_start>"):
        if text[a:b].endswith(tag):
            b -= len(tag)
        if text[a:b].startswith(tag):
            a += len(tag)
    while a < b and text[a] in _EDGE:
        a += 1
    while b > a and text[b - 1] in _EDGE:
        b -= 1
    return a, b


# ---------------------------------------------------------------- claimed source

_BOOK_WORDS = sorted(
    {a for al in BOOK_ALIASES.values() for a in al if not a.isascii()}, key=len, reverse=True
)
_BOOK_RX = "|".join(re.escape(w) for w in _BOOK_WORDS)
_SRC_HADITH = re.compile(
    r"(?:(?:رواه|أخرجه|اخرجه|خرّجه|روى|روي|أورده|ذكره|في)\s+)?(?:الإمام\s+|الامام\s+)?"
    r"(?:صحيح\s+|سنن\s+|مسند\s+|جامع\s+)?(?:" + _BOOK_RX + r")"
    r"(?:\s*(?:و|،|,)\s*(?:" + _BOOK_RX + r"))*"
    r"(?:\s+في\s+صحيحه|\s+في\s+سننه|\s+في\s+مسنده)?"
    r"(?:\s*[\(\[]?\s*(?:رقم|حديث|ح)?\s*[:：]?\s*[\d٠-٩/\-–]+\s*[\)\]]?)?"
    r"|متفق\s+عليه|رواه\s+الشيخان|أخرجه\s+الشيخان"
)
_SRC_QURAN = re.compile(
    r"(?:سورة\s+)?[\u0621-\u064A]{2,}(?:\s+[\u0621-\u064A]{2,})?\s*[،,:：\-–]?\s*(?:الآية|الاية|آية|اية|الآيات|آيات)?\s*[:：]?\s*[\d٠-٩]{1,3}(?:\s*[-–]\s*[\d٠-٩]{1,3})?"
    r"|سورة\s+[\u0621-\u064A]{2,}(?:\s+[\u0621-\u064A]{2,})?"
)


@dataclass(slots=True)
class Segment:
    type: SegType
    start: int
    end: int


@dataclass(slots=True)
class Citation:
    kind: str  # quran | hadith_matn
    text: Segment
    extra: list[Segment] = field(default_factory=list)


def _find_source(text: str, a: int, b: int, kind: str, *, after: bool) -> Segment | None:
    """Claimed source in a short window after (or before) the quote, inside brackets or bare."""
    if after:
        win_a, win_b = b, min(len(text), b + 90)
    else:
        win_a, win_b = max(0, a - 90), a
    seg = text[win_a:win_b]
    # stop at the next quote opening / paragraph to avoid stealing the next citation's source
    stop = re.search(r"\n\s*\n|[«﴿]|<(?:aya|hadith)_start>", seg) if after else None
    if stop:
        seg = seg[: stop.start()]
    rx_order = (_SRC_QURAN, _SRC_HADITH) if kind == "quran" else (_SRC_HADITH, _SRC_QURAN)
    best: tuple[int, int] | None = None
    for rx in rx_order:
        ms = list(rx.finditer(seg))
        if not ms:
            continue
        m = ms[0] if after else ms[-1]
        if after and m.start() > 40:
            continue
        if not after and len(seg) - m.end() > 40:
            continue
        cand = (win_a + m.start(), win_a + m.end())
        if rx is _SRC_QURAN and not _looks_like_quran_ref(text[cand[0] : cand[1]]):
            continue
        best = cand
        break
    if best is None:
        return None
    s, e = tighten(text, *best)
    return Segment("claimed_source", s, e) if e > s else None


def _looks_like_quran_ref(s: str) -> bool:
    if "سورة" in s:
        return True
    m = _QURAN_REF.search(s)
    if not m:
        return False
    from app.extract.surahs import surah_number  # noqa: PLC0415

    name = (m.group(1) or "").strip()
    return bool(name) and surah_number(name) is not None


# ---------------------------------------------------------------- isnad

_NARRATOR = re.compile(
    r"(?:(?:روى|وروى|أخرج|وأخرج)\s+(?:الإمام\s+)?(?:" + _BOOK_RX + r")[^\n:«\"]{0,60}?)?"
    r"(?:حدثنا|حدثني|أخبرنا|أخبرني|عن|وعن)\s+(?:أبي|ابي|أبو|ابو|ابن|أم|ام|عبد|عائشة|أنس|جابر|معاذ|عمر|علي|عثمان|"
    r"سعد|سعيد|ابن\s+عمر|ابن\s+عباس|ابن\s+مسعود|النعمان|البراء|سلمان|بلال|حذيفة|عقبة|أسامة|زيد|سهل|تميم|[\u0621-\u064A]+)"
    r"[^\n«\"“﴿]{0,140}?(?:قال|قالت|يقول|أنه\s+قال|أن\s+رسول\s+الله|أن\s+النبي)"
    r"(?:\s*[:：]?\s*(?:قال|سمعت)\s+(?:رسول\s+الله|النبي)[^\n«\"“]{0,40}?(?:يقول|قال)?)?\s*[:：]?"
)


def _find_isnad(text: str, a: int) -> Segment | None:
    """A narration chain ending right before the matn (allowing quote marks / markdown between)."""
    win_a = max(0, a - 220)
    seg = text[win_a:a]
    best = None
    for m in _NARRATOR.finditer(seg):
        gap = seg[m.end() :]
        if len(re.sub(r"<(?:aya|hadith)_(?:start|end)>|[\s\"'«“*:]", "", gap)) <= 2:
            best = m
    if best is None:
        return None
    s, e = win_a + best.start(), win_a + best.end()
    while e > s and text[e - 1] in " \n\t":
        e -= 1
    return Segment("isnad", s, e)


# ---------------------------------------------------------------- assembly


def segment(text: str, a: int, b: int, kind: str) -> Citation:
    """Typed segments for one quote. ``kind``: quran | hadith_matn | unknown."""
    a, b = tighten(text, a, b)
    k = "quran" if kind == "quran" else "hadith_matn"
    cit = Citation(k, Segment("Ayah" if k == "quran" else "matn", a, b))
    src = _find_source(text, a, b, k, after=True) or _find_source(text, a, b, k, after=False)
    if src is not None and not (src.start < b and a < src.end):
        cit.extra.append(src)
    if k == "hadith_matn":
        isn = _find_isnad(text, a)
        if isn is not None and isn.end <= a:
            cit.extra.append(isn)
    return cit
