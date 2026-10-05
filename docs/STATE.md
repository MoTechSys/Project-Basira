# Project state

Snapshot of what is shipped and how it was verified. Updated with every release; the dated history of *why* lives
in `DECISIONS.md`, and the per-version list of changes in `../CHANGELOG.md`.

**Version:** 0.3.1 · **Branch:** `main` · **Last verified:** 2026-10-05 (clean clone + CI)

## 1. Shipped

| Area | What | Where |
|---|---|---|
| Matching core | Two-tier normalisation, exact phrase match on the full index, windowed fuzzy fallback, letter-level diff | `backend/app/normalize.py`, `match/` |
| Safety gates | Harakat gate (D-013), foreign-material gate (E-044), byte-identical repeat merging (E-045), image quotes never `found` (E-020) | `match/harakat.py`, `extract/foreign.py`, `pipeline.py` |
| Four states | `found` / `partial_match` / `needs_review` / `not_found`, assigned only in the state machine | `state.py` (ADR-003) |
| Validator | V1–V6; every `found` independently re-proven from the store | `verify.py` |
| English gate | Approved translations → candidates cross-referenced to verbatim Arabic | `english_gate.py`, `docs/ENGLISH_GATE.md` |
| Developer surfaces | REST, Guard, receipts, rules, model catalog, MCP server (6 tools) | `main.py`, `devgate.py`, `mcp_server.py`, `docs/API.md` |
| Web app | Multi-page bilingual RTL PWA, identity v4, mobile result reveal | `frontend/`, `docs/design/` |
| Delivery | One Docker image (snapshot boot), CI with corpora, release workflow | `Dockerfile`, `.github/workflows/` |

## 2. Verified on 2026-10-05

| Gate | Result | Command |
|---|---|---|
| Backend lint + types | ruff check/format clean · mypy strict, 37 files | `make lint` |
| Backend tests | **304 passed**, none skipped | `make test` |
| Smoke | 8 canonical checks on the full corpus | `make smoke` |
| Evaluation | **150/150**, unsafe 0, variance 0 over 3 repeats | `make eval-full` |
| False alarms | **0/500** verbatim corpus segments | `make eval-full` |
| IslamicEval 2025 1B (dev) | **78.54 %** (CI 73.0–83.2), false confirmations **2** | `make islamiceval` |
| IslamicEval 2025 1A (dev) | macro-F1 rules **61.76**, rules+llm **67.89** | `make islamiceval-1a` |
| Frontend | tsc · oxlint 0 errors · vitest **30/30** · build 86.7 kB gzip JS | `make web-gates` |
| Browser e2e | **4/4** incl. 320×568 and 390×664 phone viewports, axe clean | `npm run e2e` |
| Site lexicon | 656 strings, 0 with judgement vocabulary | `scripts/check_site_lexicon.py` |
| Dependencies | pip-audit 0 · npm audit 0 | CI |
| Image | snapshot boot 0.78 s · RSS 314 MB · `/health` reports the commit | CI `docker` job |

## 3. Live

https://basirapp.site — deployed from `main` of MoTechSys/Project-Basira by `deploy/vps/autodeploy.sh`
(60 s timer). `/health` reports the deployed commit in `build_sha`. Model providers stay `mock` until a
key is entered in `/settings` (DEPLOYMENT §3).

## 4. Open items

| Item | Why it is open | Next step |
|---|---|---|
| Scholarly review of the four-state wording | Must be signed by a qualified reviewer; it cannot be written by the developer | Collect the signed note and add it as `docs/SCHOLAR_REVIEW.md` (SAFETY §7) |
| IslamicEval 1B vocalised spans | 30 vocalised spans are `needs_review` under the harakat policy (D-013) while the gold ignores marks | Policy is deliberate; revisit only with a new D- decision |
