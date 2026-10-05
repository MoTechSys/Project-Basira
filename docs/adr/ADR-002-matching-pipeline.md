# ADR-002 — Normalization, retrieval & matching

**Status:** Accepted · 2026-09-30

## Context
A measured check showed that loose normalization maps «على»→«علي», so a misspelled ayah returns `found` with an empty diff on 11 verses (594 exposed; 98 collision groups). RRF top-100 truncation can also drop the exact hit before the exact stage.

## Decision
1. **Two normalizations** over the same token positions:
   - `loose` (folds hamza forms, ى→ي, ة→ه) → retrieval & fuzzy scoring.
   - `strict` → remove diacritics (U+064B–065F, U+0670, U+06D6–06ED), RLM/LRM/tatweel, presentation forms U+FDF0–FDFD expanded; **keep** ة/ه, ى/ي, أ/إ/آ/ٱ/ا, ؤ/ئ distinctions. Used as the **gate for `found`**.
2. **Exact stage on the full inverted index** (loose tokens) — no truncation. Candidate passes to `found` only if `strict` tokens also equal the source window; else `needs_review` with a strict-token diff.
3. **Fuzzy stage** (only when no exact hit): BM25 (words) + char-3gram (Quran only) → RRF k=60 → top-100 → windowed token-Levenshtein `{0.8n, n, 1.2n}`, banded, with a per-request compute budget.
4. **Thresholds (initial values, to be recalibrated and published):** hadith `partial ≥0.75`, `review ≥0.70`; Quran `review 0.60 ≤ s < 1.0` (never partial); precedence: corpus row first, then short-quote row. Boundary cases at ±0.002 in `eval/`.
5. **Corpus display:** Quran Uthmani verbatim (Tanzil), hadith `mushakkala` file verbatim with U+200F removed at display (documented). Index both Quran rasms and both hadith files.
6. **Basmala** stripped in index only for ayah 1 (except 1:1); `basmala_token_offset` returned so the client can align highlights.
7. Vector channel disabled in P0 (`RETRIEVAL_VECTORS=off`).

## Consequences
- The adversarial case «إن الله علي كل شيء قدير» yields `needs_review` with «على/علي» highlighted — this is a mandatory test.
- Property test: `found ⇒ strict tokens equal source segment`.
