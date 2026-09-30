# STATE.md — Living status board (read this every session; update at session end)

**Last updated:** 2026-09-30 (session 2) · **Branch:** `main` · **Last commit:** see `git log -1`
**Repo:** PRIVATE rehearsal. On **Oct 4** a fresh repo is created and work migrated «as if new» (D-002).

## 0. How to resume in 5 minutes (new agent / new account)
```bash
cd /home/user/webapp
python3 corpus/fetch.py                       # downloads + sha256-verifies 4 sources (~15 s)
python3 -m venv backend/.venv && backend/.venv/bin/pip install -e "backend[dev]"
backend/.venv/bin/python corpus/build_index.py   # ~45 s → corpus/index/records.jsonl (229 MB, git-ignored)
cd backend && .venv/bin/ruff check app tests && .venv/bin/mypy && .venv/bin/pytest   # all green
```
Then read `AGENTS.md` → this file → `docs/DECISIONS.md` → `docs/adr/` → `docs/internal/AUDIT_HANDOFF_PACKAGE.md §12.5`.
The confidential source package lives ONLY in `.intake/` on the original sandbox (git-ignored); if it is gone, the
audit in `docs/internal/` is the complete substitute.

## 1. Done (verified, committed)
| Layer | File(s) | Status | Evidence |
|---|---|---|---|
| Docs scaffold | AGENTS.md, DECISIONS.md, GLOSSARY.md, ADR-001..005 | ✅ | — |
| Corpus manifest | `corpus/manifest.json` | ✅ all sha256 pinned (Tanzil×2, OHD 18 files, HadeethEnc) | `fetch.py` → «all sources present and verified» |
| Fetch/verify | `corpus/fetch.py` (stdlib) | ✅ | fails on mismatch, counts rows |
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

## 3. Known facts discovered this session (not in the package)
- BUILD_SPEC's Darimi display filename was wrong; real name `sunan_al-darimi_ahadith_mushakkala_mufassala.utf8.csv` (2 cols). Fixed in manifest.
- HadeethEnc xlsx sha256 `d5d397cb…1ec1` (v1.7.0, 2025-11-12) pinned.
- Uthmani vs simple rasm: 3 985 ayat differ after loose normalization, **363 differ in token count** («يأيها» vs «يا أيها») → both rasms MUST be indexed (done).
- Both rasms: 6 055 distinct loose strings / 98 collision groups (same for strict) — confirms audit numbers.
- Quran strict gate: a common-orthography quote («شيء») strictly equals the *simple* rasm, not Uthmani («شىء») → gate passes if ANY rasm passes (implemented in `dedupe_hits`).
- OHD display file (with tashkeel + RLM) tokenizes identically to plain for all 62 169 rows → highlight spans point into display text safely.

## 4. Open owner questions (defaults applied; see DECISIONS Q1–Q4)
Q1 licence (Apache-2.0 default) · Q2 HadeethEnc mode (`link`) · Q3 Guard API stays P2 · Q4 OHD posture (`display` + kill-switch).
Plain-language explanations were given to the owner on 2026-09-30 (see GLOSSARY.md); awaiting yes/no.
