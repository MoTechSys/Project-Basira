# Risk register

Product risks for Basira, ordered by severity. Every mitigation names the code that enforces it and the test that
fails if the mitigation is removed. Likelihood and impact are qualitative (L / M / H; impact may be *Critical*).
Review this file before every release and whenever a new failure mode is observed.

## 1. Religious-text integrity

| ID | Risk | L | I | Mitigation (where) | Guarded by |
|---|---|---|---|---|---|
| R-01 | An altered quotation is reported as `found` | M | Critical | Strict-tier byte match after canonical composition (`match/exact.py`); every `found` is re-proven independently by validator V6 (`verify.py`) | `test_verify.py::test_v6_forged_found_is_downgraded_to_unproven`, `test_v6_strict_tier_rejects_loose_only_equality`; eval `unsafe = 0` (`eval/REPORT.md`) |
| R-02 | A written vowel mark that contradicts the Mushaf is ignored | M | H | Harakat gate (`match/harakat.py`, D-013): a contradicting mark is `needs_review` with a letter-level diff | `test_safety_gates.py::test_39_53_wrong_vowel_is_never_found`, `test_precision.py::test_contradicting_diacritics_are_never_found` |
| R-03 | Foreign characters inside a quotation are invisible to matching | M | H | Foreign-material gate (`extract/foreign.py`, E-044) | `test_safety_gates.py::test_foreign_material_inside_quote_is_never_found` |
| R-04 | A model writes or alters religious text shown to the user | H | Critical | Models return positions only; every proposal is re-located verbatim or dropped (`providers/base.py::relocate`); displayed text comes from the corpus by record id (V1) | `test_providers.py::test_relocate_drops_non_verbatim`, `test_pipeline.py::test_lying_provider_cannot_inject_text_or_offsets`, `test_verify.py::test_tampered_source_text_is_rejected` |
| R-05 | The model changes a verdict | M | Critical | The four-state machine (`state.py`) is the only place a status is assigned; model output cannot reach it | `test_byok.py::test_check_headers_are_ignored_and_verdict_is_model_independent` |
| R-06 | Text read from an image is confirmed as `found` | M | H | Image-sourced quotes are never `found` (E-020, `pipeline.py`) | `test_api.py::test_image_endpoint_mock_ocr` |

## 2. Wording and judgement

| ID | Risk | L | I | Mitigation (where) | Guarded by |
|---|---|---|---|---|---|
| R-07 | UI or API wording implies a religious ruling («صحيح / ضعيف / موضوع») | M | Critical | All prose comes from `messages/*.json` and `frontend/src/site/strings.ts`; forbidden-lexicon scanner at boot and on every response (V3); site lexicon gate | `test_verify.py::test_forbidden_word_in_our_label_is_rejected`, `scripts/check_site_lexicon.py` (0 hits) |
| R-08 | A hadith grade is shown without a licensed source | L | H | A grade is displayed only when it comes from a HadeethEnc record (V4) | `test_verify.py::test_grade_must_come_from_hadeethenc_record` |
| R-09 | `not_found` is read as "fabricated" | M | H | Neutral wording and colour (E-032): «لم نجده في مصادرنا» plus referral links; never red | `test_precision.py::test_unknown_not_found_is_neutral` |

## 3. Sources

| ID | Risk | L | I | Mitigation (where) | Guarded by |
|---|---|---|---|---|---|
| R-10 | A downloaded corpus file is corrupted or tampered with | L | Critical | Every file is sha256-pinned in `corpus/manifest.json`; `fetch.py` refuses a mismatch. A TLS-certificate failure may fall back only for pinned files (the content is still verified); `--strict-tls` forbids it (E-013) | `corpus/fetch.py` exit status in CI |
| R-11 | A source's licence changes or a rights chain is unresolved | M | H | `OHD_MODE=off` kill-switch turns hadith text display into links; HadeethEnc defaults to `link` mode (`SOURCES.md`) | `test_pipeline.py::test_hadeethenc_link_mode_never_embeds_text` |
| R-12 | A boot snapshot does not match the records it claims | L | H | The snapshot stores `records_sha256` and is rejected on mismatch (`snapshot.py`) | `test_snapshot.py::test_snapshot_is_rejected_when_records_change` |

## 4. Security and privacy

| ID | Risk | L | I | Mitigation (where) | Guarded by |
|---|---|---|---|---|---|
| R-13 | User text is stored or logged | L | H | No storage (ADR-004); logs carry error classes only | code review rule in `CONTRIBUTING.md`; no persistence layer exists |
| R-14 | The provider key leaks through the API | L | Critical | Key stored once server-side (mode 0600), masked in every response, never echoed | `test_byok.py::test_repr_and_mask_never_leak_key` |
| R-15 | Rate limit bypassed by spoofing `X-Forwarded-For` | M | M | The header is trusted only from configured proxies (`BASIRA_TRUSTED_PROXIES`) | `test_api.py::test_rate_limit_key_is_not_spoofable_by_default` |
| R-16 | A non-image upload reaches the vision provider | M | M | Magic-byte sniffing before any provider call | `test_api.py::test_image_endpoint_sniffs_bytes_not_only_the_declared_mime` |
| R-17 | A vulnerable or compromised dependency | M | H | `package-lock.json` + `npm ci`; `pip-audit` and `npm audit` block CI; gitleaks over full history | `.github/workflows/ci.yml` |

## 5. Operations

| ID | Risk | L | I | Mitigation (where) | Guarded by |
|---|---|---|---|---|---|
| R-18 | The model provider is slow or unavailable | M | M | Rules-only extraction keeps every deterministic verdict; the response says `extraction_degraded` | `test_api.py::test_image_endpoint_rejects_bad_mime_and_degrades_on_ocr_failure` |
| R-19 | Cold start too slow for a free-tier host | M | M | mmap snapshot boot (≈ 0.8 s measured in CI, RSS ≈ 314 MB) | CI docker job asserts `"boot":"snapshot"` |
| R-20 | Results drift between runs | L | H | Deterministic core; `X-Basira-Determinism-Hash` on every check; eval runs 3 repeats and reports variance | `test_snapshot.py::test_determinism_hash_changes_with_input_and_is_stable`; eval `variance 0` |

## 6. Accepted limitations

- Hadith coverage is the nine books (Open-Hadith-Data) plus HadeethEnc. Anything outside them is «not found in our
  sources», which is a statement about coverage, not about the text.
- A verbatim *fragment* of an ayah is confirmed and labelled as a fragment (`quran_fragment`); it is not treated
  as a misquotation.
- Evaluation numbers on IslamicEval are on the public DEV sets, not the hidden TEST sets
  (`eval/islamiceval/REPORT_*.md`).
