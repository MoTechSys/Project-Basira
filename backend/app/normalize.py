"""Arabic normalization with two orthographic tiers and position tracking.

Two tiers (ADR-002):

* ``loose``  — BUILD_SPEC §3.1 exactly. Collapses أإآٱ→ا, ى→ي, ة→ه, ؤ→و, ئ→ي.
               Used for *retrieval* and *fuzzy scoring* only.
* ``strict`` — drops the same diacritics / Quranic marks / tatweel / direction
               marks and maps only ٱ→ا (wasla is a rasm notation, not a letter)
               plus the Persian ی/ک folds. It **keeps** hamza forms, ة/ه and ى/ي.
               Required to be equal before a quote may be reported ``found``.

Both tiers share identical token boundaries (the separator set is the same), so
every token carries one ``(start, end)`` span into the original string and both
forms. This lets the UI highlight differences on the *original* text.

Deterministic, pure Python, no I/O. Applied identically to user input and corpus.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from functools import lru_cache

# --- character classes -------------------------------------------------------

_PRE_MAP = {
    "\ufdfa": "",  # ﷺ  (would become 4 words under NFKC)
    "\ufdfb": "",  # ﷻ
    "\u06cc": "\u064a",  # ی → ي
    "\u06a9": "\u0643",  # ک → ك
}

# Marks removed in BOTH tiers.
_REMOVE_RANGES = (
    (0x0610, 0x061A),  # Arabic signs (honorifics)
    (0x064B, 0x065F),  # tashkeel incl. shadda, sukun, hamza above/below (combining)
    (0x0670, 0x0670),  # superscript (dagger) alef
    (0x06D6, 0x06ED),  # Quranic annotation signs, small waw/yeh, stops
)
_REMOVE_CHARS = frozenset("\u0640\u200e\u200f\u061c")  # tatweel, LRM, RLM, ALM

_LOOSE_FOLD = {
    "\u0625": "\u0627",  # إ
    "\u0623": "\u0627",  # أ
    "\u0622": "\u0627",  # آ
    "\u0671": "\u0627",  # ٱ
    "\u0649": "\u064a",  # ى → ي
    "\u0629": "\u0647",  # ة → ه
    "\u0624": "\u0648",  # ؤ → و
    "\u0626": "\u064a",  # ئ → ي
}
_STRICT_FOLD = {
    "\u0671": "\u0627",  # ٱ → ا  (only fold in strict tier)
}

_ARABIC_LETTER_MIN = 0x0621
_ARABIC_LETTER_MAX = 0x064A
_SEP = " "
_DROP = ""

# Canonical composition of a base letter + combining hamza/madda into the precomposed letter
# (Unicode NFC pairs). Tanzil Uthmani writes «آ» as ا + U+0653; most other texts (and Tanzil
# simple) use U+0622. Without this fold the strict tier would call a byte-faithful «كَمَآ» an
# orthographic difference (E-023). Only true canonical pairs are listed — ى/و/ي + madda (Uthmani
# elongation marks) are NOT letters and keep being dropped.
_COMPOSE: dict[tuple[str, str], str] = {
    ("\u0627", "\u0653"): "\u0622",  # ا + madda  → آ
    ("\u0627", "\u0654"): "\u0623",  # ا + hamza above → أ
    ("\u0627", "\u0655"): "\u0625",  # ا + hamza below → إ
    ("\u0648", "\u0654"): "\u0624",  # و + hamza above → ؤ
    ("\u064a", "\u0654"): "\u0626",  # ي + hamza above → ئ
    ("\u0649", "\u0654"): "\u0626",  # ى + hamza above → ئ (NFC maps to U+0626)
}
_COMPOSE_MARKS = frozenset(m for _, m in _COMPOSE)


def _is_removed(ch: str) -> bool:
    cp = ord(ch)
    if ch in _REMOVE_CHARS:
        return True
    return any(lo <= cp <= hi for lo, hi in _REMOVE_RANGES)


@lru_cache(maxsize=4096)
def _map_char(ch: str) -> tuple[str, str]:
    """Return ``(loose, strict)`` output for one *original* character.

    Each output is "" (dropped), " " (separator) or one-or-more Arabic letters.
    NFKC is applied per character so the mapping back to the original index is
    exact (a ligature such as U+FEFB ﻻ yields two letters from one source char).
    """
    ch = _PRE_MAP.get(ch, ch)
    if ch == "":
        return _DROP, _DROP
    loose_out: list[str] = []
    strict_out: list[str] = []
    for c in unicodedata.normalize("NFKC", ch):
        if _is_removed(c):
            continue
        cp = ord(c)
        if _ARABIC_LETTER_MIN <= cp <= _ARABIC_LETTER_MAX or c in ("\u0671",):
            loose_out.append(_LOOSE_FOLD.get(c, c))
            strict_out.append(_STRICT_FOLD.get(c, c))
        else:
            loose_out.append(_SEP)
            strict_out.append(_SEP)
    lo = "".join(loose_out)
    st = "".join(strict_out)
    # a char that produced only separators collapses to one separator
    if lo and lo.strip() == "":
        return _SEP, _SEP
    # a single source char that expands to letters + a mark (e.g. U+0675 → ا + U+0674):
    # keep the letters, drop the mark — a token must never contain a separator
    if _SEP in lo:
        lo = lo.replace(_SEP, "")
        st = st.replace(_SEP, "")
    return lo, st


# --- public API --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Token:
    loose: str
    strict: str
    start: int  # inclusive char offset into the original string
    end: int  # exclusive


def tokenize(text: str) -> list[Token]:
    """Tokenize ``text`` into aligned loose/strict tokens with original spans."""
    tokens: list[Token] = []
    cur_loose: list[str] = []
    cur_strict: list[str] = []
    tok_start = -1
    last_letter_end = -1

    def flush() -> None:
        nonlocal cur_loose, cur_strict, tok_start
        if cur_loose:
            tokens.append(Token("".join(cur_loose), "".join(cur_strict), tok_start, last_letter_end))
            cur_loose = []
            cur_strict = []
            tok_start = -1

    n = len(text)
    i = -1
    while i + 1 < n:
        i += 1
        ch = text[i]
        # canonical composition: look ahead one char for a combining hamza/madda (E-023)
        if i + 1 < n and text[i + 1] in _COMPOSE_MARKS:
            composed = _COMPOSE.get((ch, text[i + 1]))
            if composed is not None:
                lo, st = _map_char(composed)
                if tok_start < 0:
                    tok_start = i
                cur_loose.append(lo)
                cur_strict.append(st)
                i += 1
                last_letter_end = i + 1
                continue
        lo, st = _map_char(ch)
        if lo == _DROP:
            continue  # diacritic etc. — stays inside the current token span
        if lo == _SEP:
            flush()
            continue
        if tok_start < 0:
            tok_start = i
        cur_loose.append(lo)
        cur_strict.append(st)
        last_letter_end = i + 1
    flush()
    return tokens


def loose_tokens(text: str) -> list[str]:
    return [t.loose for t in tokenize(text)]


def strict_tokens(text: str) -> list[str]:
    return [t.strict for t in tokenize(text)]


def loose_join(text: str) -> str:
    """Space-joined loose tokens (the indexed form of a record)."""
    return " ".join(loose_tokens(text))


def strict_join(text: str) -> str:
    return " ".join(strict_tokens(text))


def char_trigrams(token: str) -> list[str]:
    """Character 3-grams of a single token with boundary markers."""
    padded = f"#{token}#"
    if len(padded) < 3:
        return [padded]
    return [padded[i : i + 3] for i in range(len(padded) - 2)]


BASMALA_LOOSE: tuple[str, ...] = ("بسم", "الله", "الرحمن", "الرحيم")
