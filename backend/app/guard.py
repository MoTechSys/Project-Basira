"""Guard — put Basira between a chatbot and its user (docs/GUARD.md).

Input: a chatbot answer. Output: a verdict about the *quotations* in it, never about the answer:

    clear      every detected quotation is ``found`` (byte-exact in a licensed source);
    flagged    at least one quotation is not ``found`` (partial_match / needs_review / not_found);
    no_quotes  no Quran/Hadith quotation was detected.

The summaries are built from fixed templates only (``app.guard_messages``) — counts, nothing else. No
religious text appears in a summary; the per-quote detail (with verbatim ``source_text``) is in ``quotes``.
A ``flagged`` verdict means «review before publishing», not «the answer is wrong».
Nothing is stored; the answer text is used only to compute the response.
"""

from __future__ import annotations

from typing import Any, Literal

from app.config import Settings
from app.devgate import UiLang, compact_check, validate_lang, validate_text
from app.guard_messages import render
from app.pipeline import Pipeline
from app.schemas import CheckOptions, CheckRequest

Verdict = Literal["clear", "flagged", "no_quotes"]


def verdict_of(statuses: list[str]) -> Verdict:
    if not statuses:
        return "no_quotes"
    return "clear" if all(s == "found" for s in statuses) else "flagged"


async def guard_answer(
    pipeline: Pipeline, settings: Settings, answer: str, ui_lang: str = "ar"
) -> dict[str, Any]:
    lang: UiLang = validate_lang(ui_lang)
    answer = validate_text(answer, settings)
    resp = await pipeline.check(
        CheckRequest(text=answer, ui_lang=lang, options=CheckOptions(max_candidates=1))
    )
    compact = compact_check(resp, settings, lang)
    quotes = compact["quotes"]
    statuses = [q["status"] for q in quotes]
    verdict = verdict_of(statuses)
    n = len(statuses)
    k = sum(1 for s in statuses if s != "found")
    return {
        "verdict": verdict,
        "counts": {
            "quotes": n,
            "found": n - k,
            "flagged": k,
            "by_status": {
                s: statuses.count(s)
                for s in ("found", "partial_match", "needs_review", "not_found")
                if statuses.count(s)
            },
        },
        "flagged_quote_ids": [q["id"] for q in quotes if q["status"] != "found"],
        "quotes": quotes,
        "flags": compact["flags"],
        "extraction_degraded": compact["extraction_degraded"],
        "summary_ar": render(verdict, "ar", n=n, k=k),
        "summary_en": render(verdict, "en", n=n, k=k),
        "determinism_hash": resp.determinism_hash,
        "corpus": compact["corpus"],
    }
