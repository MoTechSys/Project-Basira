# STATE.md — Living status board (read this every session; update at session end)

**Last updated:** 2026-10-01 (session 3) · **Branch:** `main` · **Last commit:** see `git log -1`
**Repo:** PRIVATE rehearsal. On **Oct 4** a fresh repo is created and work migrated «as if new» (D-002).

## 0. How to resume (new agent / new account / new machine) — ONE command
```bash
git clone https://github.com/MoTechSys/Project-Basira.git && cd Project-Basira
bash scripts/bootstrap.sh     # fetch+verify corpora → venv → build index → ruff/mypy/pytest → templates check  (~3 min)
make smoke                    # 8 canonical cases on the real corpus, incl. the adversarial typo → must print SMOKE OK
```
Verified 2026-09-30 in a clean `/tmp` clone: bootstrap OK, 38/38 tests, SMOKE OK, index sha256 reproducible
(`3175b625…8488` identical on two machines).
**Re-verified 2026-10-01 on a brand-new sandbox** (no venv, no data): bootstrap OK · ruff/mypy/pytest 38/38 · SMOKE OK ·
index sha256 `3175b625…8488` reproduced a third time. Wall-clock ≈ 2 min.

> ⚠ **If step 1/5 fails with `CERTIFICATE_VERIFY_FAILED` for tanzil.net** — that is upstream (their cert expired 2026-09-30).
> `fetch.py` now handles it automatically (E-013): one unverified retry **only** for sha256-pinned files, with a loud warning;
> integrity is still enforced by the pin. Use `python3 corpus/fetch.py --strict-tls` to forbid the fallback (e.g. in CI once tanzil renews).

Then read in this order: `AGENTS.md` → this file → `docs/DECISIONS.md` → `docs/adr/` →
`docs/internal/AUDIT_HANDOFF_PACKAGE.md §12.5`. The confidential source package (`.intake/`) exists ONLY on the
original sandbox; `docs/internal/` is its complete substitute. Never publish `docs/internal/`.

**Per-session ritual:** `make gates && make smoke` at start; commit after every logical change; update this file at end.

## 0.5 Team & models (D-008/D-009)
**New agent? Read `docs/AGENT_PLAYBOOK.md` first.** Multi-model team charter: `docs/TEAM.md`. Experiments log: `docs/experiments/`. Sub-agent runner: `scripts/agents/orchestrator.py --selftest`. Evidence-based model selection: `docs/model-analysis/` (README = verdict; 01–06 = axes, weaknesses, roster). Live proxy capacity: `docs/CAPABILITIES.md`.

## 1. Done (verified, committed)
| Layer | File(s) | Status | Evidence |
|---|---|---|---|
| Docs scaffold | AGENTS.md, DECISIONS.md, GLOSSARY.md, ADR-001..005 | ✅ | — |
| Corpus manifest | `corpus/manifest.json` | ✅ all sha256 pinned (Tanzil×2, OHD 18 files, HadeethEnc) | `fetch.py` → «all sources present and verified» |
| Fetch/verify | `corpus/fetch.py` (stdlib) | ✅ | fails on mismatch, counts rows; TLS-cert fallback for pinned files only (E-013), `--strict-tls` |
| Index build | `corpus/build_index.py`, `corpus/surah_names.json` | ✅ | 6236 + 62169 + 3582 records; OHD plain/display loose-token mismatch = 0; matn detected on 22 844/62 169 rows |
| Normalizer | `backend/app/normalize.py` | ✅ | loose (BUILD_SPEC §3.1) + strict (ADR-002), aligned spans; 13 tests incl. hypothesis |
| Store | `backend/app/store.py` | ✅ | 4.53 M tokens, per-surah contiguous stream (cross-ayah exact), CSR postings; load 10 s; 304 MB RSS |
| Exact match + strict gate | `backend/app/match/exact.py` | ✅ | «إن الله علي كل شيء قدير» → 13 hits all `strict_ok=False` (adversarial case behaves); 2:153/8:46, 55:13… ×31, 1:2–1:3 cross-ayah, Ibn-Maja 220 all found; <2 ms/quote |
| Retrieval | `backend/app/retrieve/index.py` | ✅ | BM25 words + char-3gram, RRF k=60, 3 ms/query; build 10 s; steady RSS 694 MB, peak ~1 GB (**optimize later**) |
| Fuzzy window | `backend/app/match/window.py` | ✅ code, ⚠ not yet exercised end-to-end | |
| Word diff | `backend/app/match/diff.py` | ✅ | |
| Rules extractor + detectors | `backend/app/extract/rules.py`, `surahs.py` | ✅ smoke-tested | brackets, introducers, claimed source (books/surah:ayah/Quran 9:11), chain/refusal/PII |
| Messages | `messages/ar.json`, `messages/en.json`, `backend/app/messages.py` | ✅ | rewritten (not copied); forbidden-lexicon scanner; `self_check_templates` = clean |
| **State machine** | `backend/app/state.py` | ✅ | 9 invariants I1–I9, 14 tests incl. property test; thresholds boundary ±0.002 |
| **Post-validator** | `backend/app/verify.py` | ✅ | V1–V5, 7 tests (tampered text, wrong ref, grade on wrong record, forbidden label) |
| Bootstrap / smoke | `scripts/bootstrap.sh`, `scripts/smoke.py`, `Makefile` | ✅ | fresh-clone rehearsal passed; found+fixed missing `numpy` dep |
| Config / schemas | `backend/app/config.py`, `schemas.py` | ✅ | defaults: LLM_PROVIDER=mock, HADEETHENC_MODE=link, OHD_MODE=display, RETRIEVAL_VECTORS=off |

Quality gates at last commit: `ruff` ✅ · `mypy --strict` ✅ · `pytest` 38/38 ✅.

## 2. In progress / next (exact order — do not reorder without a DECISIONS entry)
1. ~~state.py~~ ✅ done. 2. ~~verify.py~~ ✅ done.
3. **`backend/app/providers/`** — `base.py` (`LLMClient.extract`, `VisionClient.ocr`), `mock.py` (wraps `rules.extract_spans`), factory by env. Real adapters only on competition day (D-004).
4. **`backend/app/pipeline.py`** — extract (rules ∪ provider) → validate spans → per quote: exact → (if none) retrieve+window → state → verify; timings.
5. **`backend/app/main.py`** — FastAPI: lifespan loads store+retriever; `/health` 503 until loaded (E-011) with counts/rss/build_sha; `POST /v1/check`; `GET /v1/sources` from manifest; error envelope `{error:{code,message_ar,message_en}}`; CORS from settings; rate limit 30/min + `X-Eval-Key` bypass (T5).
6. **Tests**: `test_state.py` (adversarial typo → `needs_review`, Quran never partial, threshold boundary ±0.002 at 0.75/0.70/0.60), property test `found ⇒ strict tokens equal`, `test_verify.py` (forbidden word injected → rejected), `test_api.py` (httpx AsyncClient, uses a **small fixture index** built from 3 surahs + 50 hadith so CI has no 229 MB dependency — write `tests/conftest.py` that builds it from `corpus/data` if present, else skips).
7. `eval/cases.yaml` (150 cases, categories A–L per BUILD_SPEC §6.1), `eval/PLAN.md`, `eval/false_alarm.py` (500 verbatim segments, seed 20261004), `eval/metrics.py`, `eval/run_eval.py`.
8. Frontend scaffold `frontend/` (Vite+React+TS, RTL, imports `messages/*.json`): `Check.tsx`, `QuoteCard`, `DiffView`, `StatusBadge`, `SourcesFooter`.
9. Delivery docs: `SOURCES.md` (generate from manifest — script `corpus/gen_sources_md.py`), `SAFETY.md` (rewritten), `AI_USAGE.md` (D-006 wording), `CHANGELOG.md`, `LICENSE` (Apache-2.0 placeholder, Q1), `THIRD_PARTY_NOTICES.md`, `.env.example`, `Makefile`, `docs/API.md`, `docs/ARCHITECTURE.md`, `backend/README.md`.
10. Memory optimization (P1): retriever peak ~1 GB during build → stream trigram CSR without `gram_rows` list; target <700 MB peak.
11. Widen `make lint` to cover `corpus/*.py` and `scripts/*.py` (currently backend-only). `build_index.py` has one `PLC0415`
    (lazy `import openpyxl` — intentional, keep stdlib-only import path for fetch; add a targeted `# noqa: PLC0415` with reason).

## 3. Known facts discovered (not in the package)
- **2026-10-01:** tanzil.net TLS certificate expired (Let's Encrypt, notAfter 2026-09-30 11:47 UTC). Files served are byte-identical
  to the pinned sha256 (both rasms re-downloaded and re-hashed). Mitigated in `fetch.py` (E-013). Re-check with `--strict-tls` later.
- **2026-10-01:** `corpus/*.py` and `scripts/*.py` are **not** covered by `make lint` (which only runs inside `backend/`). They were
  linted manually this session with the backend ruff/mypy config and are clean. → added to §2 as a small gate-widening task.

### Session 2 (2026-09-30)
- BUILD_SPEC's Darimi display filename was wrong; real name `sunan_al-darimi_ahadith_mushakkala_mufassala.utf8.csv` (2 cols). Fixed in manifest.
- HadeethEnc xlsx sha256 `d5d397cb…1ec1` (v1.7.0, 2025-11-12) pinned.
- Uthmani vs simple rasm: 3 985 ayat differ after loose normalization, **363 differ in token count** («يأيها» vs «يا أيها») → both rasms MUST be indexed (done).
- Both rasms: 6 055 distinct loose strings / 98 collision groups (same for strict) — confirms audit numbers.
- Quran strict gate: a common-orthography quote («شيء») strictly equals the *simple* rasm, not Uthmani («شىء») → gate passes if ANY rasm passes (implemented in `dedupe_hits`).
- OHD display file (with tashkeel + RLM) tokenizes identically to plain for all 62 169 rows → highlight spans point into display text safely.

## 4. Open owner questions (defaults applied; see DECISIONS Q1–Q4)
Q1 licence (Apache-2.0 default) · Q2 HadeethEnc mode (`link`) · Q3 Guard API stays P2 · Q4 OHD posture (`display` + kill-switch).
Plain-language explanations were given to the owner on 2026-09-30 (see GLOSSARY.md); awaiting yes/no.
