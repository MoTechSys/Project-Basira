"""Deterministic quote extractor (BUILD_SPEC §3.2 `rules.py`) — always runs.

Captures:
  * text between ﴿ ﴾, « », " ", “ ”, ( ) when it contains ≥ min tokens of Arabic;
  * text after an introducer («قال تعالى», «قال الله», «قال رسول الله», «قال النبي»,
    «عن النبي … قال», «ﷺ», «وفي الحديث», «قوله تعالى») up to the end of the sentence;
  * text BEFORE a trailer («… صدق الله العظيم», «… رواه البخاري») back to the previous sentence
    boundary, when nothing else already covers it;
  * a claimed source expression near the quote («رواه البخاري», «سورة البقرة: 255»,
    «Quran 9:11», «[البقرة: 255]») parsed by dictionary, never by a model.

Also provides the deterministic detectors used by the pipeline:
  * ``detect_chain_message``  — «انشرها تؤجر» family (descriptive flag only);
  * ``detect_refusal``        — the user is asking for a ruling / grading / tafsir;
  * ``detect_pii``            — phone / e-mail / national-id-like patterns.

All spans are code-point offsets into the ORIGINAL input string.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.extract.surahs import surah_number
from app.normalize import Token, loose_tokens, tokenize

_AR = r"\u0600-\u06FF"
_BRACKET_PAIRS = (("﴿", "﴾"), ("«", "»"), ("“", "”"), ('"', '"'), ("(", ")"), ("[", "]"), ("{", "}"))
_INTRODUCERS = (
    "قال تعالى",
    "قال الله تعالى",
    "قال الله عز وجل",
    "قال الله",
    "يقول الله تعالى",
    "يقول تعالى",
    "قال سبحانه",
    "قال عز وجل",
    "قال رسول الله صلى الله عليه وسلم",
    "قال رسول الله ﷺ",
    "قال رسول الله",
    "قال النبي صلى الله عليه وسلم",
    "قال النبي ﷺ",
    "قال النبي",
    "قال صلى الله عليه وسلم",
    "قال ﷺ",
    "عن النبي صلى الله عليه وسلم قال",
    "عن النبي ﷺ قال",
    "عن رسول الله صلى الله عليه وسلم قال",
    "عن رسول الله ﷺ قال",
    "أن رسول الله صلى الله عليه وسلم قال",
    "أن النبي صلى الله عليه وسلم قال",
    "قال عليه الصلاة والسلام",
    "قال عليه السلام",
    "وفي الحديث الشريف",
    "في الحديث الشريف",
    "وفي الحديث",
    "في الحديث",
    "جاء في الحديث",
    "ورد في الحديث",
    "وفي الصحيحين",
    "في الصحيحين",
    "قوله تعالى",
    "قوله سبحانه",
    "قوله عز وجل",
    "لقوله تعالى",
    "قوله صلى الله عليه وسلم",
    "قوله ﷺ",
    "لقوله ﷺ",
    "لقوله صلى الله عليه وسلم",
)
# Trailers: the quote PRECEDES these («… صدق الله العظيم», «… رواه البخاري»); span runs back to the
# previous sentence boundary (or text start).
_TRAILERS = ("صدق الله العظيم", "صدق الله", "رواه", "أخرجه", "متفق عليه")
_SENTENCE_START = re.compile(r"[.!?؟\n؛:]")
_SENTENCE_END = re.compile(r"[.!?؟\n؛]|(?=\s+(?:رواه|أخرجه|متفق|صدق الله|سورة|\[|\(|«|﴿))")

# --- claimed source dictionaries -------------------------------------------------------------

BOOK_ALIASES: dict[str, tuple[str, ...]] = {
    "sahih_al-bukhari": ("البخاري", "بخاري", "bukhari", "al-bukhari"),
    "sahih_muslim": ("مسلم", "muslim"),
    "sunan_abu-dawud": ("أبو داود", "ابو داود", "أبي داود", "ابي داود", "abu dawud", "abu dawood"),
    "sunan_al-tirmidhi": ("الترمذي", "ترمذي", "tirmidhi", "al-tirmidhi"),
    "sunan_al-nasai": ("النسائي", "نسائي", "nasai", "al-nasai", "an-nasai"),
    "sunan_ibn-maja": ("ابن ماجه", "ابن ماجة", "ibn majah", "ibn maja"),
    "maliks_muwataa": ("مالك", "الموطأ", "malik", "muwatta"),
    "musnad_ahmad": ("أحمد", "احمد", "المسند", "ahmad", "musnad"),
    "sunan_al-darimi": ("الدارمي", "دارمي", "darimi", "al-darimi"),
}
_MUTTAFAQ = ("متفق عليه", "رواه الشيخان", "أخرجه الشيخان")
_NARRATED = re.compile(r"(?:رواه|أخرجه|خرّجه|خرجه|صحّحه|صححه|حسّنه|حسنه|ذكره|عند)\s+([^\n.،,;؛)\]»﴾]{2,60})")
_QURAN_REF = re.compile(
    r"(?:سورة\s+)?([\u0621-\u064A\s]{2,20}?)\s*[:،,\-–/]\s*(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?"
    r"|(?:Quran|Qur'an|Q\.?|Surah|Sura)\s*(\d{1,3})\s*[:.]\s*(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?"
    r"|\b(\d{1,3})\s*:\s*(\d{1,3})\b",
    re.IGNORECASE,
)

_CHAIN_PATTERNS = (
    "انشرها تؤجر",
    "انشرها تأجر",
    "انشرها ولك الأجر",
    "انشر ولك الأجر",
    "أمانة في رقبتك",
    "امانة في رقبتك",
    "من لم ينشرها",
    "من لم ينشر",
    "لا تكتمها",
    "أرسلها لعشرة",
    "ارسلها لعشرة",
    "أرسلها إلى",
    "ارسلها الى",
    "ستسمع خبرا",
    "ستسمع خبراً",
    "لا تحذفها",
    "من قرأها ولم ينشرها",
    "شاركها مع",
    "انشرها في كل",
    "share this or",
    "forward this to",
)
_REFUSAL_PATTERNS = (
    "هل هذا الحديث صحيح",
    "هل الحديث صحيح",
    "هل هو صحيح",
    "ما درجة الحديث",
    "ما درجة هذا الحديث",
    "ما حكم",
    "هل يجوز",
    "أفتوني",
    "افتوني",
    "ما تفسير",
    "فسر لي",
    "اشرح لي معنى",
    "هل هذا حلال",
    "هل هذا حرام",
    "is this hadith authentic",
    "is this hadith sahih",
    "is it permissible",
    "is it haram",
    "what is the ruling",
    "give me a fatwa",
)
_PII = (
    re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)\d{3}[\s-]?\d{3,4}(?!\d)"),  # phone
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),  # email
    re.compile(r"(?<!\d)[12]\d{9}(?!\d)"),  # Saudi national/iqama id (10 digits starting 1/2)
    re.compile(r"(?<!\d)\d{13,19}(?!\d)"),  # card-like
)


@dataclass(slots=True)
class RuleSpan:
    start: int
    end: int
    kind: str  # quran | hadith_matn | unknown
    marked: bool  # inside explicit quote marks
    claimed_source: dict[str, Any] | None = None
    extras: dict[str, Any] = field(default_factory=dict)


def _arabic_token_count(s: str) -> int:
    return len(loose_tokens(s))


def _kind_from_introducer(intro: str) -> str:
    """``intro`` may be raw or loose-joined."""
    if (
        any(w in intro for w in ("تعالى", "تعالي", "الله", "سبحانه", "عز وجل"))
        and "رسول" not in intro
        and "النبي" not in intro
        and "الحديث" not in intro
        and "الصحيحين" not in intro
    ):
        return "quran"
    return "hadith_matn"


def extract_spans(text: str, *, min_tokens_marked: int = 2, min_tokens_intro: int = 3) -> list[RuleSpan]:
    spans: list[RuleSpan] = []
    _bracketed(text, spans, min_tokens_marked)
    _introduced(text, spans, min_tokens_intro)
    _trailed(text, spans, min_tokens_intro)
    spans = merge_overlaps(spans)
    for sp in spans:
        sp.claimed_source = find_claimed_source(text, sp.start, sp.end)
        if sp.kind == "unknown":
            sp.kind = _kind_from_context(text, sp)
    return spans


def _kind_from_context(text: str, sp: RuleSpan) -> str:
    """Kind of a bracketed quote from its surroundings (E-029): an introducer right before the
    opening bracket («قال تعالى: "…"», «قال رسول الله ﷺ: "…"»), else a claimed source (surah:ayah →
    quran; a hadith book → hadith_matn), else «unknown». Only affects labels/messages for quotes
    that are not found; a strict Quran hit always wins regardless (state I4)."""
    before = text[max(0, sp.start - 120) : sp.start]
    toks = tokenize(before)
    loose = [t.loose for t in toks]
    for _i, j, intro in _intro_positions(before, toks, loose):
        if j >= len(toks):  # introducer is the last thing before the bracket
            return _kind_from_introducer(" ".join(intro))
    cs = sp.claimed_source or {}
    parsed = cs.get("parsed", {}) if isinstance(cs, dict) else {}
    if isinstance(parsed, dict):
        if "surah" in parsed:
            return "quran"
        if parsed.get("books"):
            return "hadith_matn"
    return "unknown"


def _bracketed(text: str, spans: list[RuleSpan], min_tokens: int) -> None:
    for open_, close in _BRACKET_PAIRS:
        i = 0
        while True:
            a = text.find(open_, i)
            if a < 0:
                break
            b = text.find(close, a + 1)
            if b < 0:
                break
            inner = text[a + 1 : b]
            latin_words = len(re.findall(r"[A-Za-z]{2,}", inner))
            if not _is_attribution(inner) and (_arabic_token_count(inner) >= min_tokens or latin_words >= 3):
                kind = "quran" if open_ == "﴿" else "unknown"
                spans.append(RuleSpan(a + 1, b, kind, True))
            i = b + 1


def _is_attribution(inner: str) -> bool:
    """Bracketed text that is a *reference*, not a quotation (E-030): «(البقرة: 255)», «(رواه مسلم)»,
    «(متفق عليه)», «(سورة البقرة, آية 257)», «(عليه الصلاة والسلام)». Such brackets are never checked
    as quotes — the user would otherwise see «رواه مسلم» reported as "not found"."""
    inner = inner.strip()
    if not inner or _QURAN_REF.fullmatch(inner) is not None:
        return True
    low = inner.lower()
    if any(p in inner for p in _MUTTAFAQ) or _NARRATED.match(inner) is not None:
        return True
    if re.match(r"^(?:سورة\s+\S+|آية|الآية|الآيات)\b", inner) and re.search(r"\d", inner):
        return True
    loose = tuple(loose_tokens(inner))
    if loose in _HONORIFICS or loose in {("صلي", "الله", "عليه", "وسلم"), ("رضي", "الله", "عنهم")}:
        return True
    return bool(re.fullmatch(r"[\d\s:/\-–،,]+", low))


_HONORIFICS: tuple[tuple[str, ...], ...] = (  # loose-token sequences that may follow an introducer
    ("صلي", "الله", "عليه", "وسلم"),
    ("صلي", "الله", "عليه", "واله", "وسلم"),
    ("عليه", "الصلاه", "والسلام"),
    ("عليه", "السلام"),
    ("رضي", "الله", "عنه"),
    ("رضي", "الله", "عنها"),
    ("عز", "وجل"),
    ("سبحانه", "وتعالي"),
    ("تعالي",),
    ("جل", "جلاله"),
)
# «ﷺ» is dropped by the normalizer, so «قال ﷺ» would collapse to the bare «قال» and fire on every
# «قال فلان» in a text (E-028). Introducers whose loose form is a single generic verb are therefore
# kept only in their explicit forms; «ﷺ» after «قال/قوله» is handled by the honorific swallowing
# *after* a longer introducer, and by the dedicated check in ``_introduced``.
_GENERIC_VERBS = frozenset({"قال", "قوله", "لقوله", "يقول"})
_INTRO_LOOSE: tuple[tuple[str, ...], ...] = tuple(
    sorted(
        {
            t
            for t in (tuple(loose_tokens(i)) for i in _INTRODUCERS)
            if not (len(t) == 1 and t[0] in _GENERIC_VERBS)
        },
        key=len,
        reverse=True,
    )
)
_SAWS = "\ufdfa"  # ﷺ


def _intro_positions(
    text: str, toks: list[Token], loose: list[str]
) -> list[tuple[int, int, tuple[str, ...]]]:
    """Yield (first_token, token_after_introducer_and_honorifics, introducer) for every introducer
    occurrence, longest introducer first, overlapping shorter matches skipped («قال الله تعالى» must
    not also fire as «قال الله»). A bare generic verb («قال», «قوله») counts only when the ﷺ ligature —
    invisible to the tokenizer — sits right after it in the raw text (E-028)."""
    out: list[tuple[int, int, tuple[str, ...]]] = []
    taken: list[tuple[int, int]] = []
    saws = [(i,) for i in _GENERIC_VERBS]
    for intro in [*_INTRO_LOOSE, *saws]:
        n = len(intro)
        for i in range(len(loose) - n + 1):
            if tuple(loose[i : i + n]) != intro:
                continue
            if n == 1 and intro[0] in _GENERIC_VERBS:
                nxt = toks[i + 1].start if i + 1 < len(toks) else len(text)
                if _SAWS not in text[toks[i].end : nxt]:
                    continue
            j = _swallow_honorifics(loose, i + n)
            if any(a < j and i < b for a, b in taken):
                continue
            taken.append((i, j))
            out.append((i, j, intro))
    return out


def _swallow_honorifics(loose: list[str], j: int) -> int:
    progressed = True
    while progressed:
        progressed = False
        for h in _HONORIFICS:
            if tuple(loose[j : j + len(h)]) == h:
                j += len(h)
                progressed = True
                break
    return j


def _introduced(text: str, spans: list[RuleSpan], min_tokens: int) -> None:
    """Introducers are matched on LOOSE TOKENS (so tashkeel, «صلَّى اللهُ عَلَيْهِ وسلَّمَ», ﷺ or an
    honorific after the introducer never leak into the quote). The quote runs from the token after the
    introducer to the sentence end, unless a bracket opens there (the bracket rule owns that case)."""
    toks = tokenize(text)
    loose = [t.loose for t in toks]
    openers = {o for o, _ in _BRACKET_PAIRS}
    for _i, j, intro in _intro_positions(text, toks, loose):
        if j >= len(toks):
            continue
        start = toks[j].start
        between = text[toks[j - 1].end : start]
        if text[start] in openers or any(o in between for o in openers):
            continue  # the bracket rule already caught it
        end_m = _SENTENCE_END.search(text, start)
        end = end_m.start() if end_m else len(text)
        if _arabic_token_count(text[start:end]) >= min_tokens:
            while end > start and text[end - 1].isspace():
                end -= 1
            spans.append(RuleSpan(start, end, _kind_from_introducer(" ".join(intro)), False))


def _trailed(text: str, spans: list[RuleSpan], min_tokens: int) -> None:
    """Quote BEFORE a trailer («… صدق الله العظيم», «… رواه البخاري») back to the previous sentence
    boundary — only where no span already covers that text."""
    for tr in _TRAILERS:
        for m in re.finditer(r"(?<![\u0621-\u064A])" + re.escape(tr), text):
            end = m.start()
            while end > 0 and (text[end - 1].isspace() or text[end - 1] in "،,-–—"):
                end -= 1
            if end == 0:
                continue
            starts = [x.end() for x in _SENTENCE_START.finditer(text, 0, end)]
            start = starts[-1] if starts else 0
            while start < end and text[start].isspace():
                start += 1
            if any(sp.start < end and start < sp.end for sp in spans):
                continue
            if _arabic_token_count(text[start:end]) >= min_tokens:
                spans.append(RuleSpan(start, end, "quran" if tr.startswith("صدق") else "hadith_matn", False))


def merge_overlaps(spans: list[RuleSpan]) -> list[RuleSpan]:
    """Merge overlapping/nested spans; a marked span wins over an unmarked one that contains it."""
    if not spans:
        return []
    spans = sorted(spans, key=lambda s: (s.start, -(s.end - s.start)))
    out: list[RuleSpan] = []
    for s in spans:
        if not out:
            out.append(s)
            continue
        last = out[-1]
        if s.start >= last.end:
            out.append(s)
            continue
        # overlap
        if s.marked and not last.marked and last.start <= s.start and s.end <= last.end:
            out[-1] = s  # prefer the explicit quote
        elif last.marked and not s.marked:
            continue
        else:
            last.end = max(last.end, s.end)
            if last.kind == "unknown":
                last.kind = s.kind
    return out


def find_claimed_source(text: str, start: int, end: int, window: int = 80) -> dict[str, Any] | None:
    """Look for a source claim right after (preferred) or before the span."""
    after = text[end : min(len(text), end + window)]
    before = text[max(0, start - window) : start]
    for seg, where in ((after, "after"), (before, "before")):
        r = parse_claimed_source(seg)
        if r:
            r["position"] = where
            return r
    return None


def parse_claimed_source(seg: str) -> dict[str, Any] | None:
    low = seg.lower()
    for phrase in _MUTTAFAQ:
        if phrase in seg:
            return {
                "raw": phrase,
                "parsed": {"books": ["sahih_al-bukhari", "sahih_muslim"], "muttafaq": True},
            }
    m = _NARRATED.search(seg)
    if m:
        books = _books_in(m.group(1))
        if books:
            return {"raw": m.group(0).strip(), "parsed": {"books": books}}
    for book, aliases in BOOK_ALIASES.items():
        for a in aliases:
            if re.search(r"(?<![\w\u0621-\u064A])" + re.escape(a.lower()) + r"(?![\w\u0621-\u064A])", low):
                if book in ("maliks_muwataa", "musnad_ahmad") and not re.search(
                    r"رواه|أخرجه|مسند|موطأ|musnad|muwatta", low
                ):
                    continue  # bare «مالك»/«أحمد» are too ambiguous
                return {"raw": a, "parsed": {"books": [book]}}
    q = _QURAN_REF.search(seg)
    if q:
        return _parse_quran_ref(q)
    return None


def _books_in(s: str) -> list[str]:
    low = s.lower()
    found: list[str] = []
    for book, aliases in BOOK_ALIASES.items():
        if any(a.lower() in low for a in aliases) and book not in found:
            found.append(book)
    return found


def _parse_quran_ref(m: re.Match[str]) -> dict[str, Any] | None:
    if m.group(1) is not None:
        num = surah_number(m.group(1))
        if num is None:
            return None
        return {
            "raw": m.group(0).strip(),
            "parsed": {
                "surah": num,
                "ayah": int(m.group(2)),
                "ayah_to": int(m.group(3)) if m.group(3) else None,
            },
        }
    if m.group(4) is not None:
        s, a = int(m.group(4)), int(m.group(5))
    else:
        s, a = int(m.group(7)), int(m.group(8))
    if not (1 <= s <= 114 and 1 <= a <= 286):
        return None
    to = m.group(6) if m.group(4) is not None else None
    return {"raw": m.group(0).strip(), "parsed": {"surah": s, "ayah": a, "ayah_to": int(to) if to else None}}


# --- detectors -------------------------------------------------------------------------------


def detect_chain_message(text: str) -> bool:
    lo = " ".join(loose_tokens(text))
    low = text.lower()
    return any((" ".join(loose_tokens(p)) in lo) if p[0] > "\u0600" else (p in low) for p in _CHAIN_PATTERNS)


def detect_refusal(text: str) -> bool:
    lo = " ".join(loose_tokens(text))
    low = text.lower()
    return any(
        (" ".join(loose_tokens(p)) in lo) if p[0] > "\u0600" else (p in low) for p in _REFUSAL_PATTERNS
    )


def detect_pii(text: str) -> bool:
    return any(p.search(text) for p in _PII)


def language_of(segment: str) -> str:
    toks = tokenize(segment)
    ar = sum(t.end - t.start for t in toks)
    latin = len(re.findall(r"[A-Za-z]", segment))
    if ar >= 2 * max(latin, 1) or (ar > 0 and latin == 0):
        return "ar"
    if latin > ar:
        return "en" if re.search(r"[A-Za-z]{3,}", segment) else "other"
    return "other"
