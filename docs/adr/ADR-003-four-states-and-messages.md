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

## Implementation notes (2026-09-30, session 2)
- Implemented in `backend/app/state.py` as a **pure function** `decide(facts, evidence, thresholds) → Decision`; it returns message KEYS only.
- Nine invariants I1–I9 are written in the module docstring and each has a test in `backend/tests/test_state.py`, including a Hypothesis property test `found ⇒ every winner is exact ∧ strict_ok` and `quran ⇒ never partial_match`.
- Fuzzy arbitration: Quran is considered first when its best score ≥ hadith best score (a Quran near-miss is more consequential to surface as «يحتاج مراجعة»).
- `backend/app/verify.py` re-derives truth from the Store (byte-equal `source_text`, existing ref, grade only from the HadeethEnc record itself, lexicon scan on our strings, `found` without matches impossible). Tests in `tests/test_verify.py`.
