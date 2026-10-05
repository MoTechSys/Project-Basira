"""Harakat (vocalisation) gate — QURAN ONLY (invariant I11, safety gate B01, DECISIONS D-013).

Hadith vocalisation in any edition is editorial, not canonical, so it is never gated.

Policy
------
1. A vowel mark the user **wrote** that contradicts the Mushaf on the same letter is a difference —
   **wherever** the letter sits, including the last letter of the word («يَخْشَى اللَّهُ» vs «ٱللَّهَ»
   flips subject and object in 35:28). Any such *conflict* → the quote is never `found`.
2. A mark the user did **not** write is never a contradiction. Every letter whose Mushaf mark is
   absent is reported as *missing* (the pipeline only runs this gate when the quote carries any mark
   at all, so a bare quote is never annotated) so the reader sees exactly
   what was dropped (39:53 half-vocalised). Status stays `found`; a notice is added.
3. The single exception: a **sukun on the last letter of the whole quote** where the Mushaf has a
   vowel or tanween is the pausal form (waqf) — reported as *waqf*, status `found`, a note is added.
   The same sukun anywhere else in the quote is a conflict.
4. A completely bare quote (no vowel marks at all) produces nothing — unchanged behaviour.

Reference text
--------------
Comparison runs against Tanzil «simple» (fully vocalised, common orthography) when it is word-aligned
with the quote — its letters are exactly what users type, so marks align letter-for-letter. The Uthmani
display text is the fallback. If the base-letter counts of a word pair differ in both references the
word is *unalignable* → ``None`` → the caller must not claim the vocalisation was verified.

Marks: fatha/damma/kasra, the three tanween (incl. open Uthmani forms U+08F0–U+08F2), shadda, sukun
(U+0652 and the Uthmani round/oval zeros U+06E1/U+06DF/U+06E0). Dagger alif, small letters, madda,
stop signs are rasm notation — ignored. Shadda is compared only when the user wrote it (a missing
shadda is "missing", a written shadda where the Mushaf has none is a conflict).

The module never alters any displayed text; it returns character ranges inside the user's word and the
reference word so the UI can highlight exactly the letter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

_FATHA, _DAMMA, _KASRA = "\u064e", "\u064f", "\u0650"
_FATHATAN, _DAMMATAN, _KASRATAN = "\u064b", "\u064c", "\u064d"
_SHADDA, _SUKUN = "\u0651", "\u0652"
_UTH_SUKUN = frozenset({"\u06e1", "\u06df", "\u06e0"})  # Uthmani round/oval zero = no vowel
# open (Uthmani) tanween forms map to the ordinary ones
_UTH_TANWEEN = {"\u08f0": _FATHATAN, "\u08f1": _DAMMATAN, "\u08f2": _KASRATAN}

_VOWELS = frozenset({_FATHA, _DAMMA, _KASRA, _FATHATAN, _DAMMATAN, _KASRATAN})
_TRACKED = _VOWELS | {_SHADDA, _SUKUN} | _UTH_SUKUN | set(_UTH_TANWEEN)


# wasla → alif, Uthmani alif-maqsura carrier → ya, Persian ye/kaf (the strict gate already proved the
# letters equal in one rasm; this is only a guard against comparing two different words)
_FOLD = {"\u0671": "\u0627", "\u0649": "\u064a", "\u06cc": "\u064a", "\u06a9": "\u0643"}


def _fold(ch: str) -> str:
    return _FOLD.get(ch, ch)


def _is_base_letter(ch: str) -> bool:
    cp = ord(ch)
    return 0x0621 <= cp <= 0x064A or ch in "\u0671\u06cc\u06a9"


@dataclass(frozen=True, slots=True)
class LetterMarks:
    pos: int  # char offset of the base letter in the word
    end: int  # char offset after its marks
    vowel: str | None  # one of _VOWELS, "" for sukun, None when unvocalised
    shadda: bool


def skeleton(word: str) -> list[LetterMarks]:
    """Base letters of ``word`` with the vocalisation attached to each (Arabic letters only)."""
    out: list[LetterMarks] = []
    i, n = 0, len(word)
    while i < n:
        ch = word[i]
        if not _is_base_letter(ch):
            i += 1
            continue
        j = i + 1
        vowel: str | None = None
        shadda = False
        while j < n and not _is_base_letter(word[j]):
            m = _UTH_TANWEEN.get(word[j], word[j])
            if m in _VOWELS:
                vowel = m
            elif m == _SHADDA:
                shadda = True
            elif m == _SUKUN or m in _UTH_SUKUN:
                vowel = vowel or ""
            elif m.isspace():
                break
            j += 1
        out.append(LetterMarks(i, j, vowel, shadda))
        i = j
    return out


DiffKind = Literal["conflict", "missing", "waqf"]


@dataclass(frozen=True, slots=True)
class LetterDiff:
    kind: DiffKind
    quote_chars: tuple[int, int]  # inside the user's word
    source_chars: tuple[int, int]  # inside the reference word


def compare_words(  # noqa: PLR0912 — one branch per policy rule, kept flat for auditability
    user_word: str, ref_word: str, *, quote_final: bool
) -> list[LetterDiff] | None:
    """Letter-by-letter vocalisation comparison of two words with equal strict letters.

    ``quote_final`` — this is the LAST word of the quote (enables the pausal-sukun exception on its
    last letter). Returns ``None`` when the words cannot be aligned letter-for-letter.
    """
    u, s = skeleton(user_word), skeleton(ref_word)
    if not u or len(u) != len(s):
        return None
    if [_fold(user_word[m.pos]) for m in u] != [_fold(ref_word[m.pos]) for m in s]:
        return None  # different base letters — the strict gate's business, not ours
    out: list[LetterDiff] = []
    last = len(u) - 1
    for idx, (a, b) in enumerate(zip(u, s, strict=True)):
        qc, sc = (a.pos, a.end), (b.pos, b.end)
        if a.vowel is None and not a.shadda:
            # user wrote nothing on this letter
            if b.vowel or b.shadda:
                out.append(LetterDiff("missing", qc, sc))
            continue
        if a.vowel is None and a.shadda:
            # shadda alone: compared as a shadda; the vowel (if any) is simply missing
            if not b.shadda:
                out.append(LetterDiff("conflict", qc, sc))
            elif b.vowel:
                out.append(LetterDiff("missing", qc, sc))
            continue
        if a.vowel == "" and quote_final and idx == last and b.vowel:
            out.append(LetterDiff("waqf", qc, sc))
            continue
        conflict = False
        if a.vowel is not None and b.vowel is not None and a.vowel != b.vowel:
            conflict = True  # includes sukun ("") vs vowel in either direction
        elif a.vowel is not None and b.vowel is None and a.vowel != "":
            conflict = True  # user vocalised a letter the Mushaf leaves bare (e.g. a long-vowel carrier)
        if a.shadda and not b.shadda:
            conflict = True
        if conflict:
            out.append(LetterDiff("conflict", qc, sc))
        elif a.vowel is not None and not a.shadda and b.shadda:
            out.append(LetterDiff("missing", qc, sc))
    return out


# ---------------------------------------------------------------- legacy API (kept for callers/tests)


@dataclass(frozen=True, slots=True)
class Conflict:
    quote_chars: tuple[int, int]  # inside the user's word
    source_chars: tuple[int, int]  # inside the source word


def word_conflicts(user_word: str, source_word: str) -> list[Conflict]:
    """Conflicts only (no missing/waqf), every letter judged. Unalignable words → []."""
    res = compare_words(user_word, source_word, quote_final=False)
    if not res:
        return []
    return [Conflict(d.quote_chars, d.source_chars) for d in res if d.kind == "conflict"]


def user_vocalised(text: str) -> bool:
    """True when the user's text carries any short-vowel mark at all (cheap pre-check)."""
    return any(c in _VOWELS or c in (_SHADDA, _SUKUN) for c in text)
