"""Diacritic consistency gate (invariant I11, IslamicEval 2025 guideline C2) — QURAN ONLY.

Hadith vocalisation in any edition is editorial, not canonical, so it is never gated.

Rule: *absence* of a diacritic is never a difference; a diacritic the user **wrote** that
**contradicts** the source's diacritic on the same letter is. «حُرِّمَ … الْمَيْتَةُ» against the Mushaf
«حَرَّمَ … الْمَيْتَةَ» (2:173) is therefore a difference, while «حرم عليكم الميتة» is not.

How it works, per aligned word pair (the strict letters are already equal when this runs):

1. Each word is reduced to a *vowel skeleton*: for every base letter, the set of short-vowel /
   tanween / shadda / sukun marks attached to it. Quranic annotation signs, small letters, madda,
   dagger alef and stop marks are ignored — they are rasm notation, not vocalisation a user types.
2. Letters are aligned through the **strict** letter sequence (identical on both sides), so the
   comparison is letter-to-letter.
3. A letter conflicts when the user wrote at least one *vowel* mark (fatha/damma/kasra or a
   tanween) and the source has a *different* vowel mark on that letter. Shadda is compared only
   when the user wrote it and the source has a vowel but no shadda (or vice-versa) — a missing
   shadda is not a conflict. Sukun (U+0652 and the Uthmani round-zero U+06E1/U+06DF) is treated as
   "no vowel": a user's sukun conflicts only with a source vowel.

The module never alters any displayed text; it returns character ranges inside the user's word so
the UI can highlight exactly the conflicting letter.
"""

from __future__ import annotations

from dataclasses import dataclass

_FATHA, _DAMMA, _KASRA = "\u064e", "\u064f", "\u0650"
_FATHATAN, _DAMMATAN, _KASRATAN = "\u064b", "\u064c", "\u064d"
_SHADDA, _SUKUN = "\u0651", "\u0652"
_UTH_SUKUN = frozenset({"\u06e1", "\u06df", "\u06e0"})  # Uthmani round/oval zero = no vowel
# open (Uthmani) tanween forms map to the ordinary ones
_UTH_TANWEEN = {"\u08f0": _FATHATAN, "\u08f1": _DAMMATAN, "\u08f2": _KASRATAN}

_VOWELS = frozenset({_FATHA, _DAMMA, _KASRA, _FATHATAN, _DAMMATAN, _KASRATAN})
_TRACKED = _VOWELS | {_SHADDA, _SUKUN} | _UTH_SUKUN | set(_UTH_TANWEEN)


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


@dataclass(frozen=True, slots=True)
class Conflict:
    quote_chars: tuple[int, int]  # inside the user's word
    source_chars: tuple[int, int]  # inside the source word


def word_conflicts(user_word: str, source_word: str) -> list[Conflict]:
    """Letter-level conflicts between two words whose strict letters are equal.

    If the base-letter counts differ (e.g. Uthmani small/omitted letters), nothing is reported —
    the strict gate already handles letter differences; this gate is about vocalisation only.
    """
    u, s = skeleton(user_word), skeleton(source_word)
    if not u or len(u) != len(s):
        return []
    out: list[Conflict] = []
    last = len(u) - 1
    for idx, (a, b) in enumerate(zip(u, s, strict=True)):
        if idx == last:
            continue  # word-final letter: case ending / waqf vs wasl — never judged (I11)
        bad = False
        if (
            (a.vowel and b.vowel and a.vowel != b.vowel)
            or (a.vowel and b.vowel == "")
            or (a.vowel == "" and b.vowel)
            or (a.shadda and not b.shadda and b.vowel is not None)
        ):  # both wrote a (non-sukun) vowel, different
            bad = True
        if bad:
            out.append(Conflict((a.pos, a.end), (b.pos, b.end)))
    return out


def user_vocalised(text: str) -> bool:
    """True when the user's text carries any short-vowel mark at all (cheap pre-check)."""
    return any(c in _VOWELS for c in text)
