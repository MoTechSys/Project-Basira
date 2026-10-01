"""The four-state machine (ADR-003, BUILD_SPEC §3.5, SAFETY §1–2).

This module is the ONLY place where a quote is assigned a status. It is pure:
it receives already-computed evidence (exact hits, fuzzy window hits) and the
thresholds, and returns a ``Decision``. No I/O, no model, no free text — only
message KEYS, which the UI renders from ``messages/*.json``.

Religious-safety invariants enforced here (each has a test in tests/test_state.py):

  I1  Quran is never ``partial_match``. Any difference from the Mushaf text → ``needs_review``.
  I2  ``found`` requires an exact loose hit whose STRICT tokens also match (strict gate).
      A loose-only hit (e.g. «علي» for «على») → ``needs_review`` with reason
      ``orthographic_difference`` and a strict-token diff. Never a silent ``found``.
  I3  Quran ``not_found`` shows NO candidates (a wrong ayah next to a false claim is harmful).
  I4  A strict-exact Quran hit wins over any hadith evidence regardless of the claimed kind/source.
  I5  Short quotes (< ``short_quote_tokens``): only exact → ``found``; fuzzy ≥ ``short_review`` →
      ``needs_review``; otherwise ``not_found``. Never ``partial_match``.
  I6  Grade (HadeethEnc) is attached only when the matched record IS a HadeethEnc record and the
      status is ``found`` or ``partial_match``; verbatim fields only. Otherwise ``grade=None``.
  I7  Non-Arabic quotes → ``needs_review`` (``non_arabic``); if a parsable Quran ref is claimed,
      the Arabic text at that ref is offered with ``arabic_text_at_ref`` (display, no judgment).
  I8  ``claimed_source_mismatch`` never changes the status; it only adds a notice.
  I9  Message keys used here must exist in messages/*.json (checked by a test).
  I12 A claimed Quran reference («[البقرة: 5]») that differs from the matched ayah sets
      ``claimed_source_mismatch`` + notice ``claimed_ayah_mismatch`` (status unchanged — I8 applies).
  I13 Attribution cross-notice: a strict-exact QURAN hit introduced as a hadith («قال رسول الله»,
      «رواه …») adds ``attribution_quran_not_hadith``; a strict-exact HADITH hit introduced as Quran
      («قال تعالى», ﴿…﴾) adds ``attribution_hadith_not_quran``. Descriptive, never a judgment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.config import Thresholds

Status = Literal["found", "partial_match", "needs_review", "not_found"]
Corpus = Literal["tanzil", "ohd", "hadeethenc"]


@dataclass(frozen=True, slots=True)
class Evidence:
    """One candidate record, already scored. ``strict_ok`` is meaningful only when ``score == 1.0``."""

    corpus: Corpus
    rec_idx: int
    score: float  # 1.0 for exact loose hits; window similarity otherwise
    strict_ok: bool  # exact hit AND strict tokens equal
    book: str = ""  # ohd book key (for claimed-source comparison)
    is_exact: bool = False


@dataclass(frozen=True, slots=True)
class QuoteFacts:
    n_tokens: int
    language: str  # ar | en | other
    kind: str  # quran | hadith_matn | isnad | attributed_saying | unknown
    marked: bool  # inside explicit quotation marks
    claimed_books: tuple[str, ...] = ()
    claimed_quran_ref: tuple[int, int] | None = None
    source_modality: str = "text"
    # I13 — what the *introducer/brackets* asserted, independent of the retrieval kind:
    #   "quran" (﴿…﴾ / قال تعالى …), "hadith" (قال رسول الله / ﷺ / رواه …) or "" (nothing asserted)
    asserted: str = ""
    claimed_ayah_to: int | None = None  # end of a claimed range «[البقرة: 1-5]»
    # I12 — the ayah actually matched (surah, ayah) for winners; filled by the pipeline when known
    matched_quran_ref: tuple[int, int] | None = None


@dataclass(slots=True)
class Decision:
    status: Status
    score: float
    message_key: str
    corpus_scope: Literal["quran", "hadith", "none"]
    winners: list[Evidence] = field(default_factory=list)  # records to render (≤ max shown decided by caller)
    review_reason: str | None = None
    notice_keys: list[str] = field(default_factory=list)
    claimed_source_mismatch: bool = False
    show_candidates: bool = True
    attach_grade: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def _quran(ev: list[Evidence]) -> list[Evidence]:
    return [e for e in ev if e.corpus == "tanzil"]


def _hadith(ev: list[Evidence]) -> list[Evidence]:
    return [e for e in ev if e.corpus != "tanzil"]


def _best(ev: list[Evidence]) -> Evidence | None:
    return max(ev, key=lambda e: (e.score, e.strict_ok, e.is_exact), default=None)


def decide(facts: QuoteFacts, evidence: list[Evidence], th: Thresholds) -> Decision:  # noqa: PLR0911
    """Assign a status. See module docstring for the invariants."""
    # I7 — non-Arabic quotes are out of P0 scope
    if facts.language != "ar":
        d = Decision(
            "needs_review",
            0.0,
            "needs_review_non_arabic",
            "none",
            review_reason="non_arabic",
            show_candidates=False,
        )
        if facts.claimed_quran_ref is not None:
            d.notice_keys.append("arabic_text_at_ref")
            d.extra["show_ref"] = facts.claimed_quran_ref
        return d

    quran_ev = _quran(evidence)
    hadith_ev = _hadith(evidence)
    quran_strict = [e for e in quran_ev if e.is_exact and e.strict_ok]
    hadith_strict = [e for e in hadith_ev if e.is_exact and e.strict_ok]

    # I4 — strict Quran exact wins over everything
    if quran_strict:
        d = Decision("found", 1.0, "found", "quran", winners=quran_strict)
        if facts.kind not in ("quran", "unknown") or facts.claimed_books:
            d.notice_keys.append("quran_wins")
        if facts.asserted == "hadith":  # I13
            d.notice_keys.append("attribution_quran_not_hadith")
        return _apply_claim_checks(d, facts)

    # hadith strict exact
    if hadith_strict:
        d = Decision("found", 1.0, "found", "hadith", winners=hadith_strict, attach_grade=True)
        if facts.asserted == "quran":  # I13
            d.notice_keys.append("attribution_hadith_not_quran")
        return _apply_claim_checks(d, facts)

    # I2 — loose-exact but strict-different: an orthographic difference, never `found`
    quran_loose = [e for e in quran_ev if e.is_exact and not e.strict_ok]
    hadith_loose = [e for e in hadith_ev if e.is_exact and not e.strict_ok]
    if quran_loose:
        return Decision(
            "needs_review",
            1.0,
            "needs_review_quran",
            "quran",
            winners=quran_loose,
            review_reason="orthographic_difference",
        )
    if hadith_loose:
        d = Decision(
            "needs_review",
            1.0,
            "needs_review",
            "hadith",
            winners=hadith_loose,
            review_reason="orthographic_difference",
            notice_keys=["matched_other_wording"],
        )
        return _apply_claim_checks(d, facts)

    # fuzzy region — pick the better corpus by best score
    bq = _best(quran_ev)
    bh = _best(hadith_ev)
    short = facts.n_tokens < th.short_quote_tokens and not facts.marked

    # Decide which corpus the fuzzy evidence points to. Quran is considered first when it
    # scores at least as high; a Quran near-miss is more consequential than a hadith one.
    if bq is not None and (bh is None or bq.score >= bh.score):
        return _decide_quran_fuzzy(bq, quran_ev, facts, th, short)
    if bh is not None:
        return _apply_claim_checks(_decide_hadith_fuzzy(bh, hadith_ev, facts, th, short), facts)

    # nothing at all
    scope: Literal["quran", "hadith"] = "quran" if facts.kind == "quran" else "hadith"
    key = "not_found_quran" if scope == "quran" else "not_found"
    return Decision("not_found", 0.0, key, scope, show_candidates=False)


def _decide_quran_fuzzy(
    best: Evidence, ev: list[Evidence], facts: QuoteFacts, th: Thresholds, short: bool
) -> Decision:
    # I1: never partial. I5: short rule. I3: not_found shows nothing.
    threshold = th.short_review if short else th.quran_review
    if best.score >= threshold:
        return Decision(
            "needs_review",
            best.score,
            "needs_review_short" if short else "needs_review_quran",
            "quran",
            winners=[best],
            review_reason="short_quote" if short else "near_miss",
        )
    return Decision("not_found", best.score, "not_found_quran", "quran", show_candidates=False)


def _decide_hadith_fuzzy(
    best: Evidence, ev: list[Evidence], facts: QuoteFacts, th: Thresholds, short: bool
) -> Decision:
    if short:
        if best.score >= th.short_review:
            return Decision(
                "needs_review",
                best.score,
                "needs_review_short",
                "hadith",
                winners=[best],
                review_reason="short_quote",
            )
        return Decision("not_found", best.score, "not_found", "hadith", show_candidates=False)
    if best.score >= th.hadith_partial:
        return Decision(
            "partial_match",
            best.score,
            "partial_match",
            "hadith",
            winners=[best],
            notice_keys=["hadith_variant"],
            attach_grade=True,
        )
    if best.score >= th.hadith_review:
        top = sorted(ev, key=lambda e: -e.score)[:3]
        return Decision(
            "needs_review", best.score, "needs_review", "hadith", winners=top, review_reason="near_miss"
        )
    return Decision("not_found", best.score, "not_found", "hadith", show_candidates=False)


def _apply_claim_checks(d: Decision, facts: QuoteFacts) -> Decision:
    """I8/I12 — claimed-source comparison adds a notice only; it never changes the status."""
    if not d.winners:
        return d
    if d.corpus_scope == "quran":
        # I12 — a claimed ayah reference that points elsewhere. ``matched_quran_ref`` is the FIRST
        # ayah of the best winner; a quote that *starts* at the claimed ayah (or a claimed range that
        # contains it) is consistent. Everything else is a mismatch notice.
        c = facts.claimed_quran_ref
        m = facts.matched_quran_ref
        if c is not None and m is not None and not _ref_consistent(c, m, facts):
            d.claimed_source_mismatch = True
            d.notice_keys.append("claimed_ayah_mismatch")
            d.extra["claimed_ref"] = c
        # claimed a hadith book, found a Quran verse — quran_wins notice already covers it
        return d
    if not facts.claimed_books:
        return d
    found_books = {e.book for e in d.winners if e.corpus == "ohd" and e.book}
    if found_books and not (found_books & set(facts.claimed_books)):
        d.claimed_source_mismatch = True
        d.notice_keys.append("claimed_source_mismatch")
    return d


def _ref_consistent(claimed: tuple[int, int], matched: tuple[int, int], facts: QuoteFacts) -> bool:
    """Same surah and the matched first ayah lies within [claimed.ayah, claimed.ayah_to or ayah]."""
    if claimed[0] != matched[0]:
        return False
    lo = claimed[1]
    hi = facts.claimed_ayah_to or lo
    return lo <= matched[1] <= hi


def collection_tier(corpus: Corpus, book: str, sahihain: frozenset[str]) -> str:
    if corpus == "tanzil":
        return "quran"
    if corpus == "hadeethenc":
        return "hadeethenc"
    return "sahihain" if book in sahihain else "other_nine"


SAHIHAIN: frozenset[str] = frozenset({"sahih_al-bukhari", "sahih_muslim"})
