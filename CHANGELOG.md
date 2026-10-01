# CHANGELOG

كل التواريخ بتوقيت الرياض (UTC+3). يُحدَّث يوميًا خلال فترة التحدي (4–6 أكتوبر 2026).

## [Unreleased] — upgrade pack v2 (prepared 1 Oct 2026, to be applied on day 1)

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
- **E-030 deterministic whole-text Quran scan** (`extract/scan.py`): ayat quoted with no marker («اللهم ربنا آتنا…») are detected by pure index lookup (4-gram seed, greedy extension). 0 false alarms on prose probes. Toggle `QURAN_SCAN`, `QURAN_SCAN_MIN_TOKENS`.
- **E-031 binary snapshot** (`snapshot.py`): mmap'd numpy + pickled records. **Boot 25 s → 1.9 s, RSS 1,001 MB → 250 MB**, output byte-identical (test). Auto-invalidated by `records.jsonl` sha.
- **E-032 `determinism_hash`** on every response; `/health` exposes `index_sha256`, `boot` mode and `boot_seconds`.
- 35 new tests (`test_scholar_lens.py`, `test_snapshot.py`) → **132 total**; ruff + mypy clean.
- Mandatory deliverables: `LICENSE` (Apache-2.0), `SOURCES.md` (+ generator), `THIRD_PARTY_NOTICES.md`, `AI_USAGE.md`, `SAFETY.md`, `SECURITY.md`, `CHANGELOG.md`, `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`, `.dockerignore`.
- Brand kit v1.0 under `brand/` (logo, 40 icons, tokens, fonts, PWA/OG assets).

### Verified
- eval: 150/150 cases ×3 repeats, 0 unsafe, 0/500 false alarms — on fixture **and** full index.
