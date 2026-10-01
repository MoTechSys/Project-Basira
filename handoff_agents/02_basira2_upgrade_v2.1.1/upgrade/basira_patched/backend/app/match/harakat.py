"""Per-letter harakat (vowel-mark) comparison between a user's quote and the vocalized Mushaf (E-037).

Why this exists: the matching tiers deliberately strip tashkeel (a reader quoting «قل هو الله أحد»
without vowels is quoting correctly). But when the user DOES write vowels and one of them differs
from the Mushaf — «إِنَّمَا يَخْشَى اللَّهُ … الْعُلَمَاءَ» (subject/object swapped) or
«وَرَسُولِهِ» for «وَرَسُولُهُ» (9:3, the classic) — the meaning changes while every letter is identical.
No strict-tier match can see it. This module can.

Design (pure, deterministic, no I/O):
  * A token is decomposed into a *skeleton* of base letters, each carrying the SET of harakat that
    follow it (fatha/damma/kasra/tanwīn ×3/shadda/sukun). Everything else (dagger alif, small
    waw/yeh, stop signs, tatweel, honorifics) is ignored here — it is not a haraka.
  * Reference text = Tanzil "Simple (vocalized)" — same simple rasm as the user's typical
    orthography, so skeletons align letter-for-letter; the Uthmani rasm (small letters, wasla) does
    not, and is never used for this comparison.
  * Classification per token:
      equal        all marks the user wrote agree with the Mushaf (missing marks are fine)
      unvocalized  user wrote no marks on this token
      conflict     at least one letter where both sides have marks and they are INCOMPATIBLE
                   (compatible = one set ⊆ the other, e.g. user «لّ» vs Mushaf «لِّ»)
      skeleton     letters differ → not our job (the word diff already shows it)
  * Quote-level verdict:
      "none"       user wrote no harakat at all              → say nothing
      "consistent" some/all harakat written, none conflict  → optional quiet confirmation
      "conflict"   ≥1 conflicting letter                     → notice + per-letter positions for the UI

The verdict NEVER changes the four-state status (a vowel conflict is still the same letters).
It adds `harakat_conflicts` with character offsets into BOTH original strings so the UI can
underline the exact letter, and a notice key. Descriptive only — we report "differs from the
Mushaf", never "wrong meaning" (that is a scholar's sentence).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Literal

HARAKAT: dict[int, str] = {
    0x064B: "fathatan",
    0x064C: "dammatan",
    0x064D: "kasratan",
    0x064E: "fatha",
    0x064F: "damma",
    0x0650: "kasra",
    0x0651: "shadda",
    0x0652: "sukun",
}
_DAGGER_ALIF = 0x0670
_TATWEEL = 0x0640

Verdict = Literal["none", "consistent", "conflict"]


@dataclass(frozen=True, slots=True)
class Letter:
    char: str
    marks: frozenset[str]
    start: int  # offset of the base letter in the original string
    end: int  # exclusive, includes the marks that follow it


@dataclass(frozen=True, slots=True)
class Conflict:
    letter_index: int  # index within the token skeleton
    quote_chars: tuple[int, int]  # offsets in the quote's ORIGINAL text (letter + its marks)
    source_chars: tuple[int, int]  # offsets in the vocalized reference text
    quote_marks: tuple[str, ...]
    source_marks: tuple[str, ...]


def extend_marks(text: str, end: int) -> int:
    """Token spans from ``normalize.tokenize`` end after the last LETTER; the case ending that follows
    it (the meaning-carrying vowel: «العلماءُ» vs «العلماءَ») is outside the span. Extend ``end`` over
    any directly following harakat / combining marks so the comparison sees them."""
    n = len(text)
    while end < n:
        cp = ord(text[end])
        if cp in HARAKAT or cp == _DAGGER_ALIF or unicodedata.category(text[end]).startswith("M"):
            end += 1
        else:
            break
    return end


def skeleton(text: str, start: int = 0, end: int | None = None) -> list[Letter]:
    """Decompose ``text[start:end]`` into base letters with their following harakat.

    ``end`` is extended over trailing marks automatically (see ``extend_marks``)."""
    end = extend_marks(text, len(text) if end is None else end)
    out: list[Letter] = []
    cur_char = ""
    cur_marks: set[str] = set()
    cur_start = -1
    i = start
    while i < end:
        ch = text[i]
        cp = ord(ch)
        name = HARAKAT.get(cp)
        if name is not None:
            if cur_char:
                cur_marks.add(name)
            i += 1
            continue
        if cp in (_DAGGER_ALIF, _TATWEEL) or unicodedata.category(ch).startswith("M"):
            i += 1
            continue  # not a haraka
        if cur_char:
            out.append(Letter(cur_char, frozenset(cur_marks), cur_start, i))
        cur_char, cur_marks, cur_start = ch, set(), i
        i += 1
    if cur_char:
        out.append(Letter(cur_char, frozenset(cur_marks), cur_start, i))
    # trailing marks are already attached; fix `end` of the last letter to include them
    return out


_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})


def _fold(ch: str) -> str:
    """Loose letter fold so that orthographic variants of the SAME letter still align."""
    return ch.translate(_FOLD)


_TANWIN_OF = {"fathatan": "fatha", "dammatan": "damma", "kasratan": "kasra"}


def _compatible(a: frozenset[str], b: frozenset[str], *, final: bool = False) -> bool:
    """Mark sets agree when one is a subset of the other. At the LAST letter of a word, tanwīn vs its
    plain vowel is also accepted: pausal/Uthmani orthography drops the tanwīn (18:1 «عِوَجَا» vs simple
    «عِوَجًا»), and a reader writing «جميعاً» vs «جميعًا» has not changed the meaning."""
    if a <= b or b <= a:
        return True
    if final:
        fa = frozenset(_TANWIN_OF.get(m, m) for m in a)
        fb = frozenset(_TANWIN_OF.get(m, m) for m in b)
        return fa <= fb or fb <= fa
    return False


def compare_token(
    quote: str,
    q_span: tuple[int, int],
    source: str,
    s_span: tuple[int, int],
) -> tuple[Literal["equal", "unvocalized", "conflict", "skeleton"], list[Conflict]]:
    q = skeleton(quote, *q_span)
    s = skeleton(source, *s_span)
    if len(q) != len(s) or any(_fold(a.char) != _fold(b.char) for a, b in zip(q, s, strict=True)):
        # The letter skeletons do not line up one-to-one (user «ملك» vs Mushaf «مالك»; Uthmani «ءَا»
        # vs simple «آ»). That is a rasm/letter question handled by the strict tier and the qiraah
        # notice — comparing marks positionally here would mis-attribute them. Skip the token.
        return "skeleton", []
    if not any(letter.marks for letter in q):
        return "unvocalized", []
    conflicts: list[Conflict] = []
    last = len(q) - 1
    for i, (a, b) in enumerate(zip(q, s, strict=True)):
        # tanwīn fatḥ sits on the letter BEFORE a final alif («جميعًا»): treat the last two letters as final
        final = i >= last - 1
        if a.marks and b.marks and not _compatible(a.marks, b.marks, final=final):
            conflicts.append(
                Conflict(
                    letter_index=i,
                    quote_chars=(a.start, a.end),
                    source_chars=(b.start, b.end),
                    quote_marks=tuple(sorted(a.marks)),
                    source_marks=tuple(sorted(b.marks)),
                )
            )
    return ("conflict" if conflicts else "equal"), conflicts


def compare_quote(
    quote: str,
    q_spans: list[tuple[int, int]],
    source: str,
    s_spans: list[tuple[int, int]],
) -> tuple[Verdict, list[Conflict], int]:
    """Token-aligned comparison. Returns (verdict, conflicts, vocalized_token_count).

    ``q_spans``/``s_spans`` are the ORIGINAL-text spans of aligned tokens (same length; the caller
    only passes windows the strict tier already matched token-for-token).
    """
    all_conflicts: list[Conflict] = []
    vocalized = 0
    for qs, ss in zip(q_spans, s_spans, strict=True):
        kind, conf = compare_token(quote, qs, source, ss)
        if kind in ("unvocalized", "skeleton"):
            continue
        vocalized += 1
        all_conflicts.extend(conf)
    if vocalized == 0:
        return "none", [], 0
    if all_conflicts:
        return "conflict", all_conflicts, vocalized
    return "consistent", [], vocalized
