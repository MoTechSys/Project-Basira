# CHANGELOG

كل التواريخ بتوقيت الرياض (UTC+3). يُحدَّث يوميًا خلال فترة التحدي (4–6 أكتوبر 2026).

## [Unreleased] — upgrade pack v2 (prepared 1 Oct 2026, to be applied on day 1)

### Fixed — scholar-lens gaps (zero-defect audit)
- **I12** `claimed_ayah_mismatch`: an ayah cited with a wrong surah/ayah reference («[البقرة: 5]» for 94:6) now raises a notice and `claimed_source_mismatch=true`. Previously silent for Quran.
- **I13** `attribution_quran_not_hadith` / `attribution_hadith_not_quran`: an ayah introduced as a hadith (or a hadith between ﴿﴾) gets a descriptive cross-attribution notice. Hadith qudsi (both asserted) → no notice.
- `qiraah_note`: «مَلِكِ» vs Ḥafṣ «مَٰلِكِ» (dagger-alif only) is `found` with a note about the reading instead of a silent match.
- `partial_ayah_context`: a fragment of a longer ayah shows the full ayah so it is not read clipped.
- `basmala_note`: the basmala matches 1:1 and 27:30 — explained.
- `repeated_in_text`: identical quote repeated in one text is reported once (`repeated_spans`).
- Noise: label-only pseudo-quotes («في الحديث القدسي:») are no longer extracted.
- English introducers («The Prophet said:», «Allah says:») are captured and reported as `needs_review_non_arabic` with referral links instead of being ignored.

### Added
- **E-030 (withdrawn in v2.1)** whole-text Quran scan `extract/scan.py` removed: upstream `main` already ships an implicit-quote detector covering Quran *and* Hadith; two detectors would double-report. Nothing else depended on it.
- **E-035 progressive stage** `options.stage: "rules"|"full"` (default full). `rules` skips the LLM provider entirely → deterministic preliminary result in milliseconds for the progressive UI; response carries `extraction_stage`. Tests prove rules ⊆ full and hash stability.
- **E-036 CSP nonce** `app/csp.py`: per-request nonce stamped on inline `<script>` tags in `index.html`; `script-src 'self' 'nonce-…'` (no `unsafe-inline`). Fixes dark-mode bootstrap + JSON-LD being blocked.
- **Dockerfile**: `brand/dist` copy is now optional (glob trick), image builds without the brand kit.
- **E-037 harakat layer** (`match/harakat.py`, Tanzil *Simple vocalized* as a third, non-indexed text): when the user writes vowel marks and one contradicts the Mushaf — «وَرَسُولِهِ» for «وَرَسُولُهُ» (9:3), «يَخْشَى اللَّهُ … الْعُلَمَاءَ» (35:28), «إِبْرَاهِيمُ رَبَّهُ» (2:124) — the match carries `harakat_verdict="conflict"` with per-letter offsets on both the quote and the vocalized reference; the UI shows both lines with the exact letter marked. Status is never changed (I14). Unvocalized / partially vocalized quotes are never flagged; final tanwīn≡vowel; Uthmani-only rasm tokens are skipped (I15). Verified on all 6,236 ayat: 0 false alarms self-vs-self and Uthmani-vs-vocalized. Record field `tv`; `Match.harakat_*`; notices `harakat_conflict`/`harakat_consistent`.
- **E-038 spliced quotes** (`match/splice.py`): a bracketed quote that is ≥2 genuine Quran passages glued together («إن الله مع الصابرين والعصر إن الإنسان لفي خسر») is decomposed greedily on the positional index into its parts with exact ayah labels (2:153 + 103:1–2); notice `spliced_quote`, `QuoteResult.splice_parts`, UI list. Status unchanged; single passages and typos never flagged.
- **Invariant numbering**: I10/I11 in v2 → **I12/I13** to avoid collision with upstream's I10/I11.
- **E-031 binary snapshot** (`snapshot.py`): mmap'd numpy + pickled records. **Boot 25 s → 1.9 s, RSS 1,001 MB → 250 MB**, output byte-identical (test). Auto-invalidated by `records.jsonl` sha.
- **E-032 `determinism_hash`** on every response; `/health` exposes `index_sha256`, `boot` mode and `boot_seconds`.
- 35 new tests (`test_scholar_lens.py`, `test_snapshot.py`) → **132 total**; ruff + mypy clean.
- Mandatory deliverables: `LICENSE` (Apache-2.0), `SOURCES.md` (+ generator), `THIRD_PARTY_NOTICES.md`, `AI_USAGE.md`, `SAFETY.md`, `SECURITY.md`, `CHANGELOG.md`, `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`, `.dockerignore`.
- Brand kit v1.0 under `brand/` (logo, 40 icons, tokens, fonts, PWA/OG assets).

### Verified
- eval: 150/150 cases ×3 repeats, 0 unsafe, 0/500 false alarms — on fixture **and** full index.
