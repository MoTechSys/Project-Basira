# STATE.md — Living status board (read this every session; update at session end)

**Last updated:** 2026-10-01 (session 4 — WP-01..04 shipped) · **Branch:** `main` · **Last commit:** see `git log -1`
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

**Owner model (D-011): every day = new account + new sandbox + new agent → recovery from GitHub only.**
**Per-session ritual:** `make gates && make smoke` at start; commit after every logical change; update this file at end.

## 0.5 Team & models (D-008/D-009)
**New agent? Read `docs/agent/README.md` then `docs/AGENT_PLAYBOOK.md`.** Risk register: `docs/RISKS.md`. Multi-model team charter: `docs/TEAM.md`. Experiments log: `docs/experiments/`. Sub-agent runner: `scripts/agents/orchestrator.py --selftest`. Evidence-based model selection: `docs/model-analysis/` (README = verdict; 01–06 = axes, weaknesses, roster). Live proxy capacity: `docs/CAPABILITIES.md`.

## 0.7 Competition (read before building anything user-facing)
**`docs/COMPETITION.md`** = public-safe master analysis (dates, deliverables, judging weights 25/20/15/15/10/10/5, rubric→features, idea-deck commitments, conflicts C1–C5, win plan). Official files + private digest: `docs/internal/competition/` (never publish). **Open: D-012 (C1 baseline transparency) — ask the owner once per session until answered.**

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
| **Providers (WP-01)** | `backend/app/providers/{base,mock,openai_compat,__init__}.py` | ✅ | `relocate()` re-locates every proposal verbatim, model offsets ignored (ADR-005); factory falls back to mock without key; 8 tests incl. lying/slow/broken providers |
| **Pipeline (WP-02)** | `backend/app/pipeline.py`, `backend/app/links.py` | ✅ | extract→exact→(fuzzy)→decide→render→verify; deterministic tie order (Quran › showable OHD › Sahihain › idx); HadeethEnc `link` mode = empty body + grade/takhrij/link (V1 extended); all referral URL schemes HTTP-verified live; 20 e2e tests |
| **API (WP-03)** | `backend/app/main.py` | ✅ | `/health` 503 gate, `POST /v1/check`, `POST /v1/check/image` (mock OCR, degrades honestly), `GET /v1/sources`, `GET /v1/messages/{lang}`, error envelope, CORS, rate limit 30/min + `X-Eval-Key`; live run: 6236/62169/3582 loaded, 33 ms per 2-quote request, RSS 1043 MB |
| **Fixture + API tests (WP-04)** | `corpus/build_fixture.py`, `backend/tests/{conftest,test_api,test_pipeline,test_providers}.py` | ✅ | fixture = 271 ayat + 111 OHD + 32 HadeethEnc (git-ignored, auto-built from full index, tests skip without corpus); **80/80 tests**, mypy strict 24 files, SMOKE OK |
| **Eval harness (WP-05)** | `eval/{PLAN,gen_cases,materialize,metrics,run_eval,false_alarm}.py`, `eval/cases.yaml` (150, A–M), `eval/REPORT.md` | ✅ | **Full index, 3 repeats: 150/150 pass · 0 unsafe · recall@found 1.0 (78/78) · precision 1.0 · false-alarm 0/500 · forbidden 0 · variance 0**; cases reference records by ID + mechanical mutations (no religious text in repo); `make eval` (fixture, CI gate) / `make eval-full` |
| Extractor v2 | `backend/app/extract/rules.py`, `tests/test_rules.py` | ✅ | longest-introducer-first (fixes «قال الله تعالى» swallowing «تعالى»), new introducers («قوله تعالى», «وفي الحديث»…), **trailers** («… صدق الله العظيم», «… رواه X»), optional ﷺ; 14 tests |
| **Frontend (WP-06)** | `frontend/` React 19 + Vite 8 + TS strict (`noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`) | ✅ scaffold+core | `api.ts` typed client · `i18n.ts` imports `messages/*.json` (single source) + UI chrome catalogue · `Check.tsx` (health gate, abort, Ctrl+Enter, copy report, image upload) · `QuoteCard` / `DiffView` (byte-exact source, `<mark>` only, no transform) / `StatusBadge` / `SourcesFooter` (from `/v1/sources`) · template palette `#12183F #6150EA #2EF2C2 #F2F4FF` · logical CSS only · `dir`/`lang` on `<html>` · **vitest 8/8** (key-set parity, byte-exact source, forbidden-lexicon sweep, envelope errors, 503 gate) · `tsc -b` clean · build 79 kB gz · dev proxy `/v1`,`/health` → :8000 · real fixtures captured from live API in `src/__fixtures__/` |
| Cross-family review r2 | `docs/reviews/` | ⚠ 2/5 landed | security review (gpt-6-astra) + safety audit (opus-5-5) stored verbatim; 3 jobs hit HTTP 524 again even at ≤4 files → see §3 |
| **Real providers live (E-021)** | `scripts/serve.sh`, `make serve` | ✅ | OCR + LLM extraction via platform proxy (gpt-5.4); verified on 3 images; `/health.providers` shows `openai-compatible:gpt-5.4` |
| **Image policy (E-020)** | `pipeline.py`, `main.py` (`ocr_text`), frontend OCR card | ✅ | image-sourced quotes → `needs_review/image_unconfirmed`, OCR text shown to user |
| **Manual test pack** | `docs/manual-test/` | ✅ | 20 texts + 5 images + 8 UI checks, expectations verified live |
| Competition study | `docs/COMPETITION.md`, `docs/internal/competition/` | ✅ | 4 official files archived + analysed; E-014 |
| **IslamicEval 2025 Subtask 1B (external benchmark)** | `eval/islamiceval/{run_1b.py,REPORT_1B.md,predictions_1B_dev.tsv,details_1B_dev.json}`, `make islamiceval` | ✅ | Official data cloned to `.scratch/islamiceval/` (git-ignored; `git clone https://github.com/qcri/IslamicEval-2025-Subtask-1`). Product's own stages, no LLM: **dev acc 89.47 % (221/247, Wilson 85.0–92.7) · Acc-Q 91.11 · Acc-H 85.07 · false confirmations 5/100 wrong spans · 4 s**. Published TEST: TCE 89.82, Burhan 88.60, HUMAIN 86.14, majority 70.00 (Table 2). Every disagreement hand-analysed in REPORT_1B.md against the task's own reference JSON + expert corrections (dev ABC file). |
| **Rasm fidelity (E-023..E-026)** | `normalize.py` (canonical composition), `store.py` (`G2/GS2` twin-rasm streams, `strict_alt_tokens_of`, `*_range`, `spans_range`), `exact.py` (gate accepts either rasm; `mixed_rasm_hit`), `window.py` (`fuzzy_search_surah_stream`), `diff.py` (`source_alt_tokens`), `pipeline.py` (`_fuzzy_evidence`, `_display_gpos`, `_is_fragment`, `quran_fragment` notice), `eval/materialize.py` + `gen_cases.py` (`ortho_foldable`) | ✅ | Index rebuilt sha `54d34102…` (55 s). Tests 101/101; `make eval-full` 150/150 · 0 unsafe · FA 0/500 unchanged; 1B dev 87.45 → 89.47 with the dangerous direction 7 → 5. Live-verified: 26:119–120 near-miss now shows «الآيات 119–120» with the single differing word highlighted on the Uthmani text. |
| Config / schemas | `backend/app/config.py`, `schemas.py` | ✅ | defaults: LLM_PROVIDER=mock, HADEETHENC_MODE=link, OHD_MODE=display, RETRIEVAL_VECTORS=off |

Quality gates at last commit: `ruff` ✅ · `mypy --strict` ✅ (24 files) · `pytest` **101/101** ✅ · `make smoke` ✅ · `make eval-full` 150/150, 0 unsafe, FA 0/500 ✅ · `make islamiceval` 89.47 % ✅ · frontend `tsc -b` ✅ · vitest 8/8 ✅.
**Run everything:** backend `make serve` (port 8000, ~25 s to ready) + `cd frontend && npm run dev` (port 5173, proxies API).

**NEXT (in this order): (0) IslamicEval **1A** span detection (char-level macro-F1, `Evaluation_scripts/Subtask_1A`) with rules + gpt-5.4 proposals, and the three-way comparison (Basira / chatbot / manual) promised on deck slide 8 — both into `eval/islamiceval/`; (a) triage `docs/reviews/*` → fix accepted P1s (X-Forwarded-For trust list, bounded limiter, HTTPException envelope, `grade_line` only on `found`, log class-only) with tests; (b) §2 item 9 delivery docs (WP-07); (c) WP-08 deck in official pptx; (d) WP-10 deploy. Old pointer: §2 item 8 (frontend — WP-06, palette `#12183F #6150EA #2EF2C2 #F2F4FF`), 9 (delivery docs — WP-07). Then cross-family review of WP-01..04 via `scripts/agents/orchestrator.py` (reviewer=gpt-6-astra `high`, tester=gpt-6.1-sol). Run the server: `cd backend && .venv/bin/uvicorn app.main:app --port 8000` (ready after ~25 s; `/health` is 503 until then). Pending owner: D-012 (C1).**

## 2. In progress / next (exact order — do not reorder without a DECISIONS entry)
1. ~~state.py~~ ✅ done. 2. ~~verify.py~~ ✅ done.
3. ~~providers~~ ✅ (WP-01) — was: **`backend/app/providers/`** — `base.py` (`LLMClient.extract`, `VisionClient.ocr`), `mock.py` (wraps `rules.extract_spans`), factory by env. Real adapters only on competition day (D-004).
4. ~~pipeline~~ ✅ (WP-02) — was: **`backend/app/pipeline.py`** — extract (rules ∪ provider) → validate spans → per quote: exact → (if none) retrieve+window → state → verify; timings.
5. ~~main.py~~ ✅ (WP-03) — was: **`backend/app/main.py`** — FastAPI: lifespan loads store+retriever; `/health` 503 until loaded (E-011) with counts/rss/build_sha; `POST /v1/check`; `GET /v1/sources` from manifest; error envelope `{error:{code,message_ar,message_en}}`; CORS from settings; rate limit 30/min + `X-Eval-Key` bypass (T5).
6. ~~Tests~~ ✅ (WP-04) — was: **Tests**: `test_state.py` (adversarial typo → `needs_review`, Quran never partial, threshold boundary ±0.002 at 0.75/0.70/0.60), property test `found ⇒ strict tokens equal`, `test_verify.py` (forbidden word injected → rejected), `test_api.py` (httpx AsyncClient, uses a **small fixture index** built from 3 surahs + 50 hadith so CI has no 229 MB dependency — write `tests/conftest.py` that builds it from `corpus/data` if present, else skips).
7. ~~eval~~ ✅ (WP-05) — was: `eval/cases.yaml` (150 cases, categories A–L per BUILD_SPEC §6.1), `eval/PLAN.md`, `eval/false_alarm.py` (500 verbatim segments, seed 20261004), `eval/metrics.py`, `eval/run_eval.py`.
8. ~~Frontend~~ ✅ core (WP-06; remaining: Playwright E2E needs system libs — see §3; Lighthouse CI; font self-hosting) — was: Frontend scaffold `frontend/` (Vite+React+TS, RTL, imports `messages/*.json`): `Check.tsx`, `QuoteCard`, `DiffView`, `StatusBadge`, `SourcesFooter`.
9. Delivery docs: `SOURCES.md` (generate from manifest — script `corpus/gen_sources_md.py`), `SAFETY.md` (rewritten), `AI_USAGE.md` (D-006 wording), `CHANGELOG.md`, `LICENSE` (Apache-2.0 placeholder, Q1), `THIRD_PARTY_NOTICES.md`, `.env.example`, `Makefile`, `docs/API.md`, `docs/ARCHITECTURE.md`, `backend/README.md`.
10. Memory optimization (P1): retriever peak ~1 GB during build → stream trigram CSR without `gram_rows` list; target <700 MB peak.
12. Test that `docs/agent/context/RED_LINES.md` code block == `orchestrator.RED_LINES` (drift guard).
13. ~~524 retry~~ ✅ done (RETRY_CODES, reviewer→`high`) — but see §3: the review run still hit 524×4 on 12-file briefs → split briefs ≤4 files (retry w/ backoff); default long reviews to `high` not `xhigh` (R-O2).
14. Review owner's template from yesterday's agent (SK-09) when provided; merge best parts into TEAM.md.
16. Re-run cross-family review of WP-01..05 with split briefs (≤4 files each): reviewer (pipeline+verify), reviewer (main+providers), tester (adversarial tests), safety (messages+pipeline notices).
17. Orchestrator: add `stream: true` + default review effort `medium`; cap findings at 10 — to beat the 120 s proxy timeout.
18. Frontend: install Playwright system deps → run `npm run e2e`; add Lighthouse CI; self-host Arabic WOFF2 (rule 7 in research/06).
15. Package agent memory as an installable Genspark skill via official `skill-creator` (SK-13) so a new account bootstraps with one command.
11. ~~Widen `make lint`~~ ✅ done (covers corpus/, eval/, scripts/smoke.py) (currently backend-only). `build_index.py` has one `PLC0415`
    (lazy `import openpyxl` — intentional, keep stdlib-only import path for fetch; add a targeted `# noqa: PLC0415` with reason).

## 3. Known facts discovered (not in the package)
- **2026-10-01 (s5):** **Tanzil Uthmani encodes «آ» as ا + U+0653 (combining madda) in 2 044 ayat; U+0622 never appears.** Tanzil *simple* uses U+0622 (1 286 ayat). Same for hamza seats in some words. Any byte-level Arabic comparison against Tanzil Uthmani must canonically compose first (E-023) — otherwise «كَمَآ» typed on a keyboard ≠ Mushaf «كَمَآ».
- **2026-10-01 (s5):** IslamicEval 2025 1B dev: of 100 "Wrong" spans, 5 are byte-faithful Quran/hadith text labelled wrong because of the **completeness** guideline (C1: incomplete ayah = error) — and 2 of those (B-Q28_9 11:41–43, B-Q28_13 21:76–77) are *complete* consecutive ayat with «،» between them; diff vs the expert's own correction = 0 tokens. Gold also labels a Tirmidhi hadith as CorrectAyah (B-Q35_2). Published systems that score higher on this metric necessarily accept more non-verbatim text; the metric rewards leniency we deliberately refuse.
- **2026-10-01 (s5):** IslamicEval dev files use **different question IDs** per split (`B-Qnn` in `dev_SubtaskB`, `Qnnn` in `dev_SubtasksABC`); the expert corrections (`Correction` column) are only in the ABC file — join on `Original_Span[:60]`. TSV must be read with `quoting=csv.QUOTE_NONE` (spans contain quotes).
- **2026-10-01 (s5):** Eval harness caught a real interaction: after E-024 the mutation «فاذكروني → فاذكرونى» (ى fold) became *faithful Quran* (Uthmani «فَٱذْكُرُونِىٓ»), so B-028 flipped to `found` (correctly!). Mutation generators must know the twin rasm → `ortho_foldable` shared by `gen_cases`/`materialize`; cases.yaml regenerated with exactly one line changed (B-028 → `hamza_drop`).
- **2026-10-01 (s4):** The Genspark proxy (`OPENAI_BASE_URL`) serves vision for `gpt-5.4` (OCR of Arabic PNG in 5–10 s, accurate incl. ﷺ and «»). It also silently *normalises* orthography («علي»→«على») → E-020.
- **2026-10-01 (s4):** Owner's working model clarified: **finish a complete product TODAY**; on Oct 5–6 a new repo is created and ~⅔ of this work is re-committed there in several commits by the agent. STATE must stay a precise re-creation script.
- **2026-10-01 (s4):** Review round 2 with ≤4 files/brief: **2 of 5 still 524** (gpt-6-astra ×2, risk ×1); the two that succeeded took 115 s each → the proxy origin timeout is ≈120 s, so anything the model takes >120 s on dies regardless of size. Rule: use `reasoning_effort: "medium"` for reviews or ask for ≤10 findings; Opus with 16k thinking also finished in 115 s (borderline). Consider streaming (`stream: true`) in the orchestrator — STATE §2 item 17.
- **2026-10-01 (s4):** Playwright Chromium cannot launch in this sandbox: `libatk-1.0.so.0` missing (needs `sudo apt-get install libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 libgbm1 libasound2` or `npx playwright install-deps`). E2E spec `frontend/e2e/check.spec.ts` (RTL, real check, axe WCAG 2.2 AA, 24 px targets, no text-transform) is written and ready — run after installing deps.
- **2026-10-01 (s4):** Vite 8 dev server returns **403** for non-localhost Host headers → `server.allowedHosts: true` (dev only). Also: Vite 8 scaffold omits `"strict": true` — added full strict tsconfig.
- **2026-10-01 (s4):** `pkill -f <pattern>` from the Bash tool kills the tool's own shell when the pattern appears in the command line (happened twice). Use `run_in_background` shells and `KillBash`, or `pkill -f` with a pattern that excludes the calling shell.
- **2026-10-01 (s4):** Cross-family review of WP-01..04 (reviewer/tester/safety, 12 attached files ≈ 60 KB brief) → **all three HTTP 524 after 4 retries (504 s each)**. The proxy's origin timeout (~120 s) is hit by long briefs regardless of model/effort. Rule: **≤ 4 files / ≤ 20 KB per brief**; split reviews per module. Re-run pending (STATE §2 item 16).
- **2026-10-01 (s4):** First false-alarm run on the full index: 132/500 misses — ALL were extraction misses (wrappers «… صدق الله العظيم» and «وفي الحديث: …» had no rule). Fixed with trailers + new introducers → 0/500. Lesson: the FA set tests the *extractor* as much as the matcher; wrappers must stay diverse.
- **2026-10-01 (s4):** Introducer bug: «قال الله تعالى …» matched both «قال الله تعالى» and «قال الله», the latter swallowing «تعالى» into the quote → 6 verbatim ayat came back `needs_review`. Fixed (longest-first, overlap skip). This was invisible to the 8 smoke cases — the 150-case eval caught it.
- **2026-10-01 (s4):** Referral URL schemes verified by HTTP: `quranpedia.net/surah/1/{s}/{a}` → 301 → ayah page 200; `quranpedia.net/surah/{s}/{a}` is **404** (don't use); `dorar.net/hadith/search?q=` 200 (403 with curl default UA — browser UA fine); `shamela.ws/search?q=` 200; `hadeethenc.com/ar/browse/hadith/{id}` 200; OHD GitHub blob at pinned commit 200.
- **2026-10-01 (s4):** FastAPI `Form/File` needs `python-multipart` → added to deps. Rules introducer left a leading «ﷺ» in spans → fixed in `rules.py`.
- **2026-10-01 (s4):** HadeethEnc 66511 and OHD Bukhari 1 tie at 0.875 for «إنما الأعمال بالنية…»; deterministic `_order` (E-015) prefers showable OHD + Sahihain so the user sees the highlighted diff.
- **2026-10-01 (s4):** `pkill -f uvicorn` from the Bash tool kills the tool's own shell — run uvicorn in a background shell and kill by PID.
- **2026-10-01:** tanzil.net TLS certificate expired (Let's Encrypt, notAfter 2026-09-30 11:47 UTC). Files served are byte-identical
  to the pinned sha256 (both rasms re-downloaded and re-hashed). Mitigated in `fetch.py` (E-013). Re-check with `--strict-tls` later.
- **2026-10-01:** `/mnt/aidrive` is **not a mount** in this sandbox (empty root dir). AI Drive is **out of scope by owner decision (D-011)** — GitHub only.
- **2026-10-01:** Owner supplied the official *Genspark Code* guide: sandbox idle-stop 1h, deletion within hours → push ≤30 min; Supervisor **not** installed despite guide. Audited line-by-line in `docs/agent/research/09`.
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
