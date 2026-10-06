# CHANGELOG

All notable changes. Dates in Riyadh time (UTC+3). Decision ids (`E-nnn`, `D-nnn`) refer to `docs/DECISIONS.md`.
Format follows [Keep a Changelog](https://keepachangelog.com/); versions are git tags.

## [Unreleased]

### Added
- **D-015 rasm-uniqueness proof (I18/I19)**: bare-typed quotes («قل هو الله احد») are `found` with notice `rasm_completed` and the completed letters when the corpus spells the span one way; competing spellings («إن/أن الله على كل شيء قدير») → `needs_review/rasm_ambiguous` with alternatives + counts. Validator **V7** re-derives the proof. `QuoteResult.rasm` exposes it. 25 new tests.
- **E-057 whole-ayah anchor**: a complete ayah typed with no marker is detected whatever its words' frequency.
- Evaluation: category B expectations are now resolved *by construction* from the corpus (`eval/materialize.rasm_expectation`).

### Verified
pytest 329 · ruff + mypy strict · eval-full **150/150 · unsafe 0 · 0/500** (fixture and full index) · IslamicEval 1B unchanged **78.54 %, false confirmations 2**.

## [0.3.1] — 2026-10-05 — publication release

### Fixed
- Backend package declares every runtime dependency (numpy, rapidfuzz, openpyxl) and targets Python 3.12; a clean install now passes the full suite.
- `eval/islamiceval/run_1b.py` runs the same stages as `Pipeline.check()` (it crashed with `ValueError`). Re-measured: 1B dev accuracy **78.54 %** (CI 73.0–83.2), false confirmations **2** (was 5); 1A macro-F1 rules 61.76, rules+llm 67.89.
- Docker: the web stage keeps the repo layout (`../messages`), and `BUILD_SHA` reaches `/health`.
- Release workflow extracts the CHANGELOG section with a literal match and fails when it is missing.

### Added
- Identity v4 «ختم المعارضة» (generated 8-fold seal, dāra state glyphs, Amiri + Reem Kufi) and the mobile result reveal.
- CI: corpora → index → fixture before tests, blocking `pip-audit` / `npm audit`, gitleaks, image boot test.
- `docs/RISKS.md` rewritten as a product risk register in which every mitigation names its test.

### Verified
pytest 304 · ruff + mypy strict · eval-full 150/150 · unsafe 0 · false alarms 0/500 · vitest 30/30 · tsc · oxlint 0 errors · pip-audit 0 · npm audit 0.

## [0.3.0] — 2026-10-03 — "everything a judge can click is live"

### Added
- **Safety gates B01–B03** (`D-013`, `D-014`, `E-044`–`E-046`): harakat policy with letter-level diff (conflict / missing / waqf), foreign-material gate inside quotes, byte-identical repeat merging, `diacritic_unverified`. New vocalised reference corpus `tanzil_simple` (sha256-pinned). 15 failing-first tests.
- **English gate** (`E-047`, `E-048`): QuranEnc + HadeethEnc translations (BM25, 14 800 docs), candidates cross-referenced to byte-exact Arabic, rule picker + optional constrained model picker. 17 tests; recall@5 0.9565; 0 wrong selections across 3 models.
- **Developer gate** (`E-049`): MCP server at `/mcp` (Streamable HTTP, stateless) with `verify_text`, `verify_quote`, `guard_answer`, `list_sources`, `grounding_rules`; `POST /v1/guard`; `GET /v1/rules`; `X-Basira-Determinism-Hash` header; real OpenAPI examples.
- **UI v3 platform** (`E-050`): multi-page PWA (`/`, `/check`, `/services`, `/developers`, `/trust`, `/about`), Lens hero on a recorded engine response, trust numbers generated from `eval/` with file+line provenance, lexicon gate over 600+ strings, WebGL backdrop for capable devices only.
- **Server-side model configuration** (`E-051`): `/settings` enters a Genspark key once; `PUT /v1/models/config` verifies upstream then stores it (0600) and hot-swaps providers; `GET /v1/models` returns the **measured** catalog of 10 models (`docs/MODELS.md`, 20 models benchmarked on the real prompt).
- **Verification receipt** (`E-052`): `POST /v1/receipt` → stateless token; `GET /v/{token}?h=` replays and reports `verified_now` / `stale`; MCP tool `issue_receipt` (6th).
- **V6 independent proof** of every `found` and **attribution-only** wording (`E-052`, `I17`).
- **Audit fixes** (`E-053`): claimed reference compared against every verbatim position (B06) + `claimed_ref_invalid`; `source_segments[]` per covered ayah (B07); extraction/OCR truncation declared (B10); trusted-proxy `X-Forwarded-For` + image magic-byte sniffing (B12).
- **UI wiring** (`E-054`): English, Guard, receipt and MCP shown as live and connected to the API; zero «قريبًا» badges.
- Docs: `ARCHITECTURE.md`, `DEPLOYMENT.md`, `MODELS.md`, `CONTRIBUTING.md`.

### Fixed
- `app.mount("/", mcp_app)` shadowed the SPA fallback — the whole site returned 404 with `BASIRA_MCP=1` (`E-051`).
- Docker image was read-only while `/settings` needed to write one file → `/data` volume.
- Test isolation: `static_dir=None`, `BASIRA_MODEL_CONFIG` temp path, raised fd soft limit (intermittent `ENFILE`).
- Decision-id collisions across parallel branches (E-047/E-050) renumbered at merge.

### Changed
- Repository hygiene: non-product material separated from the product; stale branches deleted; README rewritten.

### Verified (on `main`, full corpus)
pytest **304** · ruff + mypy strict · smoke OK · eval **150/150** · unsafe 0 · false alarms **0/500** · variance 0 ·
tsc · oxlint 0 · vitest 26/26 · bundle **86.7 kB gzip** · pip-audit 0 · npm audit 0 · lexicon 656/0 · 0 console errors.

## [0.2.0] — 2026-10-01 — upgrade pack


### Fixed — scholar-lens gaps (zero-defect audit)
- **I10** `claimed_ayah_mismatch`: an ayah cited with a wrong surah/ayah reference («[البقرة: 5]» for 94:6) now raises a notice and `claimed_source_mismatch=true`. Previously silent for Quran.
- **I11** `attribution_quran_not_hadith` / `attribution_hadith_not_quran`: an ayah introduced as a hadith (or a hadith between ﴿﴾) gets a descriptive cross-attribution notice. Hadith qudsi (both asserted) → no notice.
- `qiraah_note`: «مَلِكِ» vs Ḥafṣ «مَٰلِكِ» (dagger-alif only) is `found` with a note about the reading instead of a silent match.
- `partial_ayah_context`: a fragment of a longer ayah shows the full ayah so it is not read clipped.
- `basmala_note`: the basmala matches 1:1 and 27:30 — explained.
- `repeated_in_text`: identical quote repeated in one text is reported once (`repeated_spans`).
- Noise: label-only pseudo-quotes («في الحديث القدسي:») are no longer extracted.
- English introducers («The Prophet said:», «Allah says:») are captured and reported as `needs_review_non_arabic` with referral links instead of being ignored.

### Added
- **Deterministic whole-text Quran detection**: ayat quoted with no marker («اللهم ربنا آتنا…») are detected by pure index lookup (4-gram seed, greedy extension); since 0.3.0 this is `extract/anchor.py` (E-041). 0 false alarms on prose probes. Toggle `QURAN_SCAN`, `QURAN_SCAN_MIN_TOKENS`.
- **E-031 binary snapshot** (`snapshot.py`): mmap'd numpy + pickled records. **Boot 25 s → 1.9 s, RSS 1,001 MB → 250 MB**, output byte-identical (test). Auto-invalidated by `records.jsonl` sha.
- **E-032 `determinism_hash`** on every response; `/health` exposes `index_sha256`, `boot` mode and `boot_seconds`.
- 35 new tests (`test_scholar_lens.py`, `test_snapshot.py`) → **132 total**; ruff + mypy clean.
- Mandatory deliverables: `LICENSE` (Apache-2.0), `SOURCES.md` (+ generator), `THIRD_PARTY_NOTICES.md`, `AI_USAGE.md`, `SAFETY.md`, `SECURITY.md`, `CHANGELOG.md`, `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`, `.dockerignore`.
- Brand kit v1.0 under `brand/` (logo, 40 icons, tokens, fonts, PWA/OG assets).

### Verified
- eval: 150/150 cases ×3 repeats, 0 unsafe, 0/500 false alarms — on fixture **and** full index.
