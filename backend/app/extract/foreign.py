"""Foreign material inside a quote (audit B02).

``normalize.tokenize`` turns every non-Arabic-letter character into a separator, so «قل هو HELLO الله
أحد» produces exactly the tokens of 112:1 and used to come back `found`. The strict gate only ever
sees letters; this module looks at what the tokenizer threw away **between** the quote's tokens.

A run of dropped characters is *foreign* when it contains anything that is not:

* whitespace, Arabic/Latin punctuation, quotation marks, brackets, dashes, ellipsis;
* Arabic diacritics / Quranic annotation signs / tatweel / bidi controls (already dropped as marks);
* an ayah-number marker: digits (ASCII or Arabic-Indic) **enclosed in ornate or round brackets**
  such as «﴿١﴾», «(255)», «[٢٥٥]» — publishers put these inside the quote;
* the honorific ligatures ﷺ / ﷻ and the Quranic ornaments ۞ / ۝.

Everything else — Latin letters, bare digits, emoji, other scripts — is reported with its exact char
range inside the quote so the UI can highlight it. Nothing is removed or rewritten.
"""

from __future__ import annotations

import re
import unicodedata
from itertools import pairwise

from app.normalize import Token

_ALLOWED_PUNCT = set(" \t\n\r.,،؛;:!?؟*_`>#-–—…\"'“”«»﴾﴿()[]{}/\\|~^+=<>·•")
_ALLOWED_SYMBOLS = {
    "\ufdfa",
    "\ufdfb",
    "\u06de",
    "\u06dd",
    "\u06e9",
    "\u200c",
    "\u200d",
}  # ﷺ ﷻ ۞ ۝ ۩ ZWNJ ZWJ
# ayah-number markers inside brackets: ﴿١﴾ (255) [٢٥٥] ﴾1﴿
_AYAH_MARKER = re.compile(r"[﴿﴾(\[【]\s*[0-9\u0660-\u0669\u06f0-\u06f9]{1,3}\s*[﴾﴿)\]】]")


def _is_mark(ch: str) -> bool:
    cp = ord(ch)
    if unicodedata.category(ch) in ("Mn", "Me", "Cf"):
        return True
    return (
        0x0610 <= cp <= 0x061A
        or 0x064B <= cp <= 0x065F
        or cp == 0x0670
        or 0x06D6 <= cp <= 0x06ED
        or cp == 0x0640
    )


def _is_allowed(ch: str) -> bool:
    return ch in _ALLOWED_PUNCT or ch in _ALLOWED_SYMBOLS or _is_mark(ch) or ch.isspace()


def foreign_runs(text: str, tokens: list[Token]) -> list[tuple[int, int]]:
    """Char ranges (into ``text``) of foreign material strictly between the first and last token."""
    if len(tokens) < 2:
        return []
    out: list[tuple[int, int]] = []
    for prev, nxt in pairwise(tokens):
        gap_a, gap_b = prev.end, nxt.start
        if gap_b <= gap_a:
            continue
        gap = text[gap_a:gap_b]
        # blank out legitimate ayah markers before scanning
        scrub = _AYAH_MARKER.sub(lambda m: " " * len(m.group(0)), gap)
        run_start = -1
        for k, ch in enumerate(scrub):
            bad = not _is_allowed(ch)
            if bad and run_start < 0:
                run_start = k
            elif not bad and run_start >= 0:
                out.append((gap_a + run_start, gap_a + k))
                run_start = -1
        if run_start >= 0:
            out.append((gap_a + run_start, gap_b))
    return out
