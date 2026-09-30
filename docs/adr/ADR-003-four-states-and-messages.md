# ADR-003 — Four states, arbitration, and user-facing prose

**Status:** Accepted · 2026-09-30

## Decision
- States: `found | partial_match | needs_review | not_found`; `needs_review` carries `reason ∈ {near_miss, short_quote, stage_failure, validator_reject, non_arabic, image_unconfirmed}`.
- **Quran:** `found` (strict 1.0) / `needs_review` (diff + سورة:آية + qirāʾa caveat, one render unit) / `not_found` with **no candidates shown**. Never `partial_match`.
- **Hadith:** `found` / `partial_match` (diff + transmission-variant caveat) / `needs_review` / `not_found` + referral links (dorar.net/hadith, shamela.ws).
- **Cross-corpus:** a strict 1.0 Quran match wins regardless of `kind`/attribution; `claimed_source_mismatch` note explains.
- **Collection tier:** `sahihain` vs `other_nine`; other-nine adds the Dorar referral line. Numbers are always «رقمه في مجموعة Open-Hadith-Data».
- **Grade:** only HadeethEnc `grade`+`takhrij`, verbatim, attributed, on a direct HadeethEnc match, rendered in the same visual unit as its attribution (layout test).
- **Prose:** `messages/ar.json`, `messages/en.json` are the only user-facing text. A forbidden-lexicon scanner (whole-word, incl. feminine/plural forms) runs on every response, whitelisting literal corpus fields and manifest book names.
- **Refusal detector** (levels ب/ج/د) is a deterministic lexicon; on hit → `refusal` notice, no extraction.
- Minimum quote length 2 (Quran) / 3 (hadith) tokens unless quote-marked; ≤30 spans; ≤5 positions shown with total.
