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
from app.normalize import loose_tokens, tokenize

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

# English introducers (G-6): captured so the quote is *reported* as ``needs_review_non_arabic`` with
# referral links instead of silently ignored. Our corpora are Arabic-only; nothing is matched.
_INTRO_EN = re.compile(
    r"(?:the\s+)?(?:prophet|messenger(?:\s+of\s+allah)?)\s*(?:\(?(?:pbuh|saw|saws|ﷺ|peace\s+be\s+upon\s+him)\)?)?\s+said\s*[:,]?\s*"
    r"|allah\s+(?:says|said)\s*(?:in\s+the\s+qur'?an)?\s*[:,]?\s*"
    r"|(?:the\s+)?qur'?an\s+(?:says|states)\s*[:,]?\s*"
    r"|hadith\s*[:,]\s*",
    re.IGNORECASE,
)
_SENTENCE_END_EN = re.compile(
    r"[.!?\n]|(?=\s*[\[(]\s*(?:quran|qur'an|sahih|bukhari|muslim|tirmidhi|\d+:\d+))", re.IGNORECASE
)

# I13 — attribution asserted by the wording around the quote (not by retrieval).
_ASSERT_HADITH = re.compile(
    r"رسول الله|النبي|صلى الله عليه|ﷺ|عليه الصلاة والسلام|في الحديث|رواه|أخرجه|متفق عليه|الصحيحين"
    r"|prophet|messenger|hadith|bukhari|muslim\b",
    re.IGNORECASE,
)
_ASSERT_QURAN = re.compile(
    r"قال تعالى|قال الله|يقول تعالى|قوله تعالى|قال سبحانه|قال عز وجل|صدق الله|سورة|الآية|آية"
    r"|allah\s+says|qur'?an",
    re.IGNORECASE,
)

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
    _introduced_en(text, spans)
    spans = merge_overlaps(spans)
    spans = [sp for sp in spans if not _is_noise(text, sp)]
    for sp in spans:
        sp.claimed_source = find_claimed_source(text, sp.start, sp.end)
    return spans


def _is_noise(text: str, sp: RuleSpan) -> bool:
    """N-4 — drop pseudo-quotes that are only a label («في الحديث القدسي:») or that end in a colon
    with < 3 tokens. Marked spans (explicit brackets) are never dropped."""
    if sp.marked:
        return False
    seg = text[sp.start : sp.end].strip()
    toks = loose_tokens(seg)
    if seg.endswith((":", "：")) and len(toks) < 4:
        return True
    label_only = {"في", "الحديث", "القدسي", "الشريف", "النبوي", "الصحيح", "قال", "وقال", "ايضا"}
    return bool(toks) and all(t in label_only for t in toks)


def _introduced_en(text: str, spans: list[RuleSpan]) -> None:
    for m in _INTRO_EN.finditer(text):
        start = m.end()
        if start >= len(text):
            continue
        if text[start] in {o for o, _ in _BRACKET_PAIRS}:
            continue  # bracket rule already caught it (latin_words >= 3)
        end_m = _SENTENCE_END_EN.search(text, start)
        end = end_m.start() if end_m else len(text)
        seg = text[start:end]
        if len(re.findall(r"[A-Za-z]{2,}", seg)) >= 3 and _arabic_token_count(seg) == 0:
            while end > start and text[end - 1].isspace():
                end -= 1
            if not any(sp.start < end and start < sp.end for sp in spans):
                spans.append(
                    RuleSpan(
                        start,
                        end,
                        "hadith_matn"
                        if "said" in m.group(0).lower() and "allah" not in m.group(0).lower()
                        else "quran",
                        False,
                    )
                )


def asserted_kind(text: str, sp: RuleSpan, window: int = 60) -> str:
    """I13 — what the surrounding wording asserts about the quote: "quran", "hadith" or "".

    Looks at the text immediately BEFORE the span (introducer side) and, for trailers, immediately
    AFTER it («رواه …» / «صدق الله العظيم»). Quranic brackets ﴿﴾ assert Quran. If both are asserted
    (e.g. a hadith qudsi introduced with «قال الله تعالى في الحديث القدسي») nothing is asserted."""
    before = text[max(0, sp.start - window) : sp.start]
    after = text[sp.end : min(len(text), sp.end + window)]
    # cut `before` at the previous sentence boundary so an earlier quote's introducer does not leak
    cut = max((m.end() for m in _SENTENCE_START.finditer(before)), default=0)
    # but keep a trailing «:» that belongs to this introducer («قال تعالى: …»)
    if cut and before[cut - 1] == ":":
        prev = max((m.end() for m in _SENTENCE_START.finditer(before[: cut - 1])), default=0)
        cut = prev
    before = before[cut:]
    after_cut = _SENTENCE_START.search(after)
    after = after[: after_cut.start()] if after_cut else after
    q = bool(_ASSERT_QURAN.search(before)) or (sp.start > 0 and text[sp.start - 1] == "﴿")
    h = bool(_ASSERT_HADITH.search(before)) or bool(re.search(r"رواه|أخرجه|متفق عليه", after))
    if q and not h:
        return "quran"
    if h and not q:
        return "hadith"
    return ""


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
            is_ref_only = _QURAN_REF.fullmatch(inner.strip()) is not None
            latin_words = len(re.findall(r"[A-Za-z]{2,}", inner))
            if not is_ref_only and (_arabic_token_count(inner) >= min_tokens or latin_words >= 3):
                kind = "quran" if open_ == "﴿" else "unknown"
                spans.append(RuleSpan(a + 1, b, kind, True))
            i = b + 1


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
_INTRO_LOOSE: tuple[tuple[str, ...], ...] = tuple(
    sorted({tuple(loose_tokens(i)) for i in _INTRODUCERS}, key=len, reverse=True)
)


def _introduced(text: str, spans: list[RuleSpan], min_tokens: int) -> None:
    """Introducers are matched on LOOSE TOKENS (so tashkeel, «صلَّى اللهُ عَلَيْهِ وسلَّمَ», ﷺ or an
    honorific after the introducer never leak into the quote). Longest introducer first; a shorter one
    overlapping an already matched longer one is skipped («قال الله تعالى» must not also fire as «قال الله»)."""
    toks = tokenize(text)
    loose = [t.loose for t in toks]
    taken: list[tuple[int, int]] = []  # token ranges
    for intro in _INTRO_LOOSE:
        n = len(intro)
        for i in range(len(loose) - n + 1):
            if tuple(loose[i : i + n]) != intro:
                continue
            j = i + n
            # swallow trailing honorifics («ﷺ» is dropped by the normalizer already)
            progressed = True
            while progressed:
                progressed = False
                for h in _HONORIFICS:
                    if tuple(loose[j : j + len(h)]) == h:
                        j += len(h)
                        progressed = True
                        break
            if any(a < j and i < b for a, b in taken):
                continue
            taken.append((i, j))
            if j >= len(toks):
                continue
            start = toks[j].start
            if text[start] in {o for o, _ in _BRACKET_PAIRS}:
                continue
            # a bracket may open between the introducer and the next token («قال ﷺ: «…»»)
            between = text[toks[j - 1].end : start]
            if any(o in between for o, _ in _BRACKET_PAIRS):
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
