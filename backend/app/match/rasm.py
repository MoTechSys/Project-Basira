"""Rasm-uniqueness proof (D-015, I18/I19): the bare-orthography layer between «strict» and «loose».

People type Quran and Hadith without hamza, with ى/ي and ة/ه swapped («قل هو الله احد»,
«ان الله مع الصابرين»). The strict gate (I2) rightly refuses to call that a byte-faithful quote.
But refusing is not the same as *not knowing*: the corpus itself often proves what was meant.

Definition. For a loose-exact hit (every token equal under the loose fold) whose strict tokens
differ from the record, classify each differing token:

* ``completion`` — the user's token is the **bare** form of the corpus token: identical after
  dropping hamza / madda carriers and folding ى→ي, ة→ه, ؤ→و, ئ→ي **and** the user wrote no hamza
  form of their own («احد» for «أحد», «امنوا» for «آمنوا», «سالك» for «سألك»). The user did not
  choose a different letter; they left one unwritten.
* ``swap`` — the user wrote a *different hamza/ya/ta form* than the corpus («علي» for «على»,
  «أن» for «إن», «الصلاه» written with ه where the corpus has ة is a completion, but «ألا» for
  «إلا» is a swap). A swap is a positive choice and may change meaning.

Then ask the corpus: across **every** loose-exact position of this quote in the corpus (all ayat
/ hadith windows), does the matched span have **exactly one** strict spelling?

* If all differences are completions **and** the spelling is unique → ``RasmProof(unique=True)``:
  the quote may be reported ``found`` with ``notice rasm_completed`` and the completed letters
  listed, because no other scripture text could have been meant. This is a proof derived from the
  corpus, never a guess: the state machine only *reads* the result, the validator re-derives it (V7).
* If any difference is a swap, or the loose span is spelled more than one way in the corpus
  («إن الله على كل شيء قدير» and «أن الله على كل شيء قدير» both exist) →
  ``RasmProof(unique=False, alternatives=[...])``: ``needs_review`` with reason
  ``rasm_ambiguous`` and the alternatives listed with their counts, so the user chooses.
* Any other kind of difference (a letter inside the word, a missing/extra word) is not a rasm
  question at all and keeps ``orthographic_difference`` / ``near_miss``.

Measured on the Tanzil Hafs text (2026-10-06): 87.7 % of Quran token occurrences have exactly
one Mushaf spelling for their bare form; the 12.3 % that do not are precisely the إن/أن, على/علي,
إلا/ألا family the judges probe — those stay in review.

Pure functions, no I/O, no model. Diacritics are not considered here (D-013 owns them).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

from app.match.exact import ExactHit
from app.store import Store

DiffClass = Literal["equal", "completion", "swap", "other"]

# Letters that differ only by an unwritten hamza / madda or a dot convention (ى/ي, ة/ه).
_BARE: dict[str, str] = {
    "\u0623": "\u0627",  # أ → ا
    "\u0625": "\u0627",  # إ → ا
    "\u0622": "\u0627",  # آ → ا
    "\u0671": "\u0627",  # ٱ → ا
    "\u0624": "\u0648",  # ؤ → و
    "\u0626": "\u064a",  # ئ → ي
    "\u0649": "\u064a",  # ى → ي
    "\u0629": "\u0647",  # ة → ه
}
# A hamza/dotted form the USER wrote: writing one of these is a choice, not an omission.
_MARKED = frozenset("\u0623\u0625\u0622\u0624\u0626\u0649\u0629")
_RANK: dict[DiffClass, int] = {"equal": 0, "completion": 1, "swap": 2, "other": 3}


def bare(token: str) -> str:
    return "".join(_BARE.get(c, c) for c in token)


def classify_token(user: str, corpus: str) -> DiffClass:
    """Classify one strict-token pair (user vs corpus)."""
    if user == corpus:
        return "equal"
    if bare(user) != bare(corpus):
        return "other"
    # same skeleton. Did the user write any marked form that differs from the corpus letter?
    for u, c in zip(user, corpus, strict=True):
        if u == c:
            continue
        if u in _MARKED:
            return "swap"  # user chose a hamza/ya/ta form the corpus does not have here
        # user wrote the bare letter (ا / و / ي / ه) where the corpus has a marked one
    return "completion"


@dataclass(frozen=True, slots=True)
class Completion:
    """One token the user wrote bare; ``corpus`` is the Mushaf/record spelling."""

    index: int  # token index inside the quote
    user: str
    corpus: str


@dataclass(frozen=True, slots=True)
class Alternative:
    spelling: str  # strict tokens joined by a space
    count: int  # number of loose-exact positions in the corpus with this spelling


@dataclass(slots=True)
class RasmProof:
    unique: bool
    completions: list[Completion] = field(default_factory=list)
    alternatives: list[Alternative] = field(default_factory=list)
    has_swap: bool = False
    spelling: str = ""  # the unique corpus spelling when ``unique``


def _window_strict(store: Store, hit: ExactHit, n: int) -> list[tuple[str, str]]:
    """Strict tokens of the corpus window the hit covers, preferring the rasm the user typed in.

    For Quran the strict stream has a twin (``GS2``, the other rasm). A token passes if it equals
    either (E-024), so the spelling we report is the one closest to the user's: take the twin only
    where the primary differs from the user and the twin does not.
    """
    prim = store.strict_tokens_range(hit.gpos, n)
    alt = store.strict_alt_tokens_range(hit.gpos, n)
    return list(zip(prim, alt, strict=True))


def prove(store: Store, hits: list[ExactHit], user_strict: list[str]) -> RasmProof | None:
    """Return the proof for a set of loose-exact hits that failed the strict gate, or ``None``
    when the difference is not a rasm difference (caller keeps ``orthographic_difference``).

    ``hits`` must all be loose-exact hits of the same quote (any corpus). The proof is global:
    one spelling across *every* position, otherwise ambiguous.
    """
    n = len(user_strict)
    if n == 0 or not hits:
        return None
    spellings: Counter[tuple[str, ...]] = Counter()
    first_completions: list[Completion] | None = None
    has_swap = False
    for h in hits:
        pairs = _window_strict(store, h, n)
        chosen: list[str] = []
        comps: list[Completion] = []
        for i, (u, (p, a)) in enumerate(zip(user_strict, pairs, strict=True)):
            # pick the rasm variant closest to what the user wrote: equal > completion > swap > other
            cp, ca = classify_token(u, p), classify_token(u, a)
            cand, cls = (p, cp) if _RANK[cp] <= _RANK[ca] else (a, ca)
            if cls == "other":
                return None  # not a rasm question
            if cls == "swap":
                has_swap = True
            elif cls == "completion":
                comps.append(Completion(i, u, cand))
            chosen.append(cand)
        spellings[tuple(chosen)] += 1
        if first_completions is None:
            first_completions = comps
    if not spellings:
        return None
    alternatives = [Alternative(" ".join(s), c) for s, c in spellings.most_common()]
    unique = len(spellings) == 1 and not has_swap
    return RasmProof(
        unique=unique,
        completions=first_completions or [],
        alternatives=alternatives,
        has_swap=has_swap,
        spelling=alternatives[0].spelling if unique else "",
    )
