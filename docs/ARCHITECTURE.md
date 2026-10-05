# Architecture

> One process, one pipeline object, zero storage. Everything a judge can click is the same code path an AI
> assistant calls over MCP. This document is the map; decisions are in `DECISIONS.md` and `adr/`.

## 1. System context

```
                      ┌────────────────────────────────────────────────────────────┐
  browser (PWA)  ───► │  FastAPI process (backend/app/main.py)                     │
  curl / SDK     ───► │   ├─ REST  /v1/check /v1/check/image /v1/guard /v1/receipt  │
  MCP client     ───► │   ├─ MCP   /mcp  (6 tools, Streamable HTTP, stateless)     │
                      │   ├─ GET   /v/{token}  receipt replay                      │
                      │   └─ SPA   /  /check  /settings …  (frontend/dist)          │
                      │                                                            │
                      │   app.state.pipeline ── Pipeline (ONE instance)            │
                      │   app.state.store    ── Store (mmap snapshot, ~300 MB)     │
                      │   app.state.llm / vision / english.picker (swappable)     │
                      └──────────────┬─────────────────────────────┬───────────────┘
                                     │ optional, per deployment     │ sha256-pinned at build
                              ┌──────▼──────┐                ┌──────▼──────────────────┐
                              │ LLM proxy   │                │ corpus/index/           │
                              │ (Genspark / │                │  records.jsonl + snapshot│
                              │  OpenAI-    │                │  translations.pkl       │
                              │  compatible)│                └─────────────────────────┘
                              └─────────────┘
```

No database, no cache server, no queue, no third-party analytics. The only external dependency at runtime is the
optional model proxy; without it the product runs rules-only and says so (`extraction_degraded`).

## 2. Request pipeline (`backend/app/pipeline.py`)

| Stage | Module | What happens | Deterministic? |
|---|---|---|---|
| 1. Extract | `extract/rules.py`, `extract/anchor.py`, `extract/segments.py` | Bracket/introducer rules find marked quotes; corpus anchors (4-gram seed + greedy extension) find unmarked verbatim runs; segments split isnad / matn / claimed source | yes |
| 1b. Model proposal | `providers/openai_compat.py` | Optional. Model lists passages *presented as quotes*; every proposal is `relocate()`d to a verbatim substring or dropped. Model text never reaches the user. | no — but cannot change a verdict on a marked quote |
| 2. Gates | `extract/foreign.py`, `match/harakat.py` | Foreign tokens inside a quote → `needs_review/foreign_material`; vowel differences → letter-level diff (`conflict`/`missing`/`waqf`) | yes |
| 3. Retrieve | `retrieve/index.py` | Two-tier normalisation (strict keeps orthography; loose folds), n-gram inverted index over 71 987 records | yes |
| 4. Match | `match/exact.py`, `match/window.py`, `match/diff.py` | Byte-exact windows after canonical composition; per-occurrence verdicts; claimed-reference check against every position (B06) | yes |
| 5. State | `state.py` | The four-state machine. **Thresholds and transitions change only with an ADR.** | yes |
| 6. English gate | `english_gate.py`, `retrieve/translations.py` | Non-Arabic quote → BM25 over approved translations → candidates cross-referenced to byte-exact Arabic records; rule picker (top1 ≥ 0.90, gap ≥ 0.30) else optional constrained model picker `{"pick": k}` | rule part yes |
| 7. Validate | `verify.py` | V1 every string from `messages/*.json` · V2 link policy · V3 forbidden lexicon · V4 grade attribution · V5 structural · **V6 independent proof of every `found`** (quote tokens must be a contiguous window of the matched record in either rasm) · attribution-only rewrite (B05) | yes |
| 8. Hash | `pipeline._determinism_hash` | sha256(records_sha256 ‖ loose-normalised input ‖ ordered verdicts + refs) | yes |

Invariant: **the model can add spans, never remove or alter a rule span, never touch a verdict.** Tested:
`test_byok.py::test_check_headers_are_ignored_and_verdict_is_model_independent`.

## 3. Developer gate (`devgate.py`, `guard.py`, `mcp_server.py`)

One transport-agnostic core → three doors with byte-equal output:

* **REST** `/v1/check`, `/v1/guard`, `/v1/receipt`, `/v1/rules`, `/v1/sources`, `/v1/models`; header `X-Basira-Determinism-Hash`.
* **MCP** `verify_text`, `verify_quote`, `guard_answer`, `list_sources`, `grounding_rules`, `issue_receipt` — mounted as an exact `Route("/mcp")` so the SPA fallback keeps every other URL (E-051 fix).
* **Guard** verdict `clear` iff every quotation is `found`; summaries are fixed templates (counts only) in `guard_messages.py`.
* **Receipt** `token = base64url(zlib(json{v,t,l}))` — the input *is* the receipt; `GET /v/{token}?h=` replays and reports `verified_now` or `stale`. Inflate is bounded (`max_text_chars × 4 + 256`).

## 4. Model configuration (`byok.py`, E-051)

The operator enters a Genspark key once on `/settings`. The server verifies it (one 5-token call), stores it in
`backend/.runtime/model.json` (0600, git-ignored, path overridable by `BASIRA_MODEL_CONFIG`) and hot-swaps the live
LLM/vision/picker in-process. **No per-request key headers exist.** `/v1/models` returns the measured catalog
(`docs/MODELS.md`) and the current config with the key masked.

## 5. Frontend (`frontend/`)

React 19 + Vite + TypeScript, no router dependency (History API, `site/router.ts`), RTL-first, PWA shell (`sw.js`
never caches `/v1/*`). Pages: `/` (Lens hero on a *recorded* engine response), `/check` (text · image · English ·
Guard, 1-second-pause or button rule), `/services`, `/developers`, `/trust` (numbers generated from `eval/` by
`scripts/gen_trust.py`), `/about`, `/settings`. All prose comes from `messages/*.json` + `site/strings.ts`;
`scripts/check_site_lexicon.py` scans every string for judgment vocabulary (656 strings, 0 hits).

## 6. Data (`corpus/`)

`manifest.json` pins every source file by sha256 and licence. `fetch.py` refuses mismatches. `build_index.py`
produces `records.jsonl` (+ `records_sha256`) and `translations.pkl`; `snapshot.py` serialises numpy arrays for
mmap boot (≈ 2 s). `build_fixture.py` cuts a small deterministic fixture used by tests and CI without network.

## 7. Security posture (see `SECURITY.md`)

CSP with hashed inline script only · `X-Frame-Options DENY` · COOP/CORP · HSTS when HTTPS · per-IP fixed-window rate
limit with **trusted-proxy** XFF handling (`BASIRA_TRUSTED_PROXIES`) · image magic-byte sniffing before any provider ·
5 000-char / size limits · error envelope `{code, message_ar, message_en}` · class-only logging (never user text).

## 8. Quality gates (what "green" means)

`make lint` (ruff + mypy strict, 37 files) · `pytest` 304 · `make smoke` 8 canonical cases on the real corpus ·
`make eval-full` 150/150 · 0 unsafe · 0/500 false alarms · variance 0 over 3 repeats · frontend tsc/oxlint/vitest/build ·
`check_site_lexicon.py` 0 · pip-audit 0 · npm audit 0.
