# بصيرة · Basira

**Deterministic verification of Quran and Hadith quotations — before you publish.**

Paste a post, an article, a chatbot answer, or an image. Basira finds every quotation presented as Quran or Hadith,
matches it **byte-exactly** against licensed source corpora, and returns one of four states with the verbatim source
text and a letter-level diff — including vowel marks (حركات). It never grades a hadith, never rewrites your text,
never generates religious text, and stores nothing.

**Live:** https://basirapp.site — deployed automatically from `main` ([`deploy/vps/`](deploy/vps/README.md)).

> Track 4 entry · *AI in Service of Islamic Content Challenge 2026* · Arabic-first, bilingual (AR/EN), RTL.

<div dir="rtl">

**بالعربية:** بصيرة أداة تتحقق من نقل الآيات والأحاديث **قبل النشر**. الصق منشورًا أو مقالًا أو جواب روبوت محادثة أو صورة،
فتستخرج كل ما قُدِّم على أنه قرآن أو حديث، وتطابقه حرفيًا مع مصادر مرخّصة، وتعرض النص الأصلي من المصدر مع الفرق
حرفًا بحرف (بما فيه الحركات). لا تحكم على حديث، ولا تعيد كتابة نصك، ولا تولّد نصًا دينيًا، ولا تخزّن شيئًا.
**الرابط المباشر:** https://basirapp.site · **لا يلزم أي مفتاح للتجربة.**

</div>

[![CI](https://github.com/MoTechSys/Project-Basira/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/MoTechSys/Project-Basira/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-6150EA)](LICENSE)
[![Determinism](https://img.shields.io/badge/false%20alarms-0%2F500-2EF2C2?labelColor=12183F)](eval/REPORT.md)

---

## Why it exists

Islamic text is quoted millions of times a day — often with a dropped word, a wrong vowel, a verse attributed to the
wrong surah, or a hadith that is not in the canonical books. Retrieval tools answer *"give me ayah 2:255"*.
**None answer *"here is a text someone wrote — tell me exactly where it departs from the Mushaf or the matn, without
rewriting it."*** Basira fills that gap, and exposes it as a product, an API, and an MCP server so AI assistants can
check their own quotations before showing them to a user.

## The four states — and the three red lines

| State | Meaning |
|---|---|
| `found` | Verbatim in the source (after canonical Unicode composition). Every `found` is independently re-proven by the validator (V6). |
| `partial_match` | A contiguous fragment of a longer passage |
| `needs_review` | A difference exists — letters, vowel marks, a foreign token inside the quote, a non-Arabic quote, an attribution with no text… The diff shows exactly where. |
| `not_found` | Not in **our** sources. *This is not a verdict on the text.* |

1. **No generated religious text.** Everything shown comes from the corpus by record ID.
2. **No judgment.** Basira never says صحيح / ضعيف / موضوع / محرّف. A grade line is shown only when it is HadeethEnc's own, quoted and attributed.
3. **No storage.** No database, no logs of user text, no cookies. The verification receipt is the input itself, compressed into the URL.

Full invariants I1–I17 and validator passes V1–V6: [`SAFETY.md`](SAFETY.md).

## What ships

| Surface | Where | Status |
|---|---|---|
| Arabic text check | `/check` · `POST /v1/check` | live |
| Image (OCR → same engine) | `/check?mode=image` · `POST /v1/check/image` | live |
| English quotation → approved translations + Arabic original | `/check?mode=english` · same endpoint | live |
| **Guard** — one verdict for a whole chatbot answer | `/check?mode=guard` · `POST /v1/guard` | live |
| **Verification receipt** — stateless, replayable | `POST /v1/receipt` · `GET /v/{token}?h=` | live |
| **MCP server** — 6 tools for AI assistants | `/mcp` (`BASIRA_MCP=1`) | live |
| Developer gate: sources, grounding rules, measured model catalog | `/v1/sources` · `/v1/rules` · `/v1/models` | live |
| **Telegram bot** — forward a text or image, get the source verbatim; «open in Basira» pre-fills the workspace | [@BasiraCheckBot](https://t.me/BasiraCheckBot) · `integrations/telegram/` · runs on the VPS (DEPLOYMENT §3.1) | live |
| Model settings — Genspark key saved once on the server | `/settings` · `PUT /v1/models/config` | live |

## For judges — try it in 60 seconds

| | |
|---|---|
| **Live solution** | https://basirapp.site — no sign-up, no key needed |
| **Try** | open `/check`, paste `قال تعالى: ﴿إن الله مع الصابرين﴾` → `found` with the verbatim ayah; change one letter → `needs_review` with a letter-level diff |
| **Telegram** | [@BasiraCheckBot](https://t.me/BasiraCheckBot) — forward any post |
| **API docs** | https://basirapp.site/docs (OpenAPI) · contract: [`docs/API.md`](docs/API.md) |
| **Source** | this public repository, Apache-2.0 |

## Measured, not claimed

| Gate | Result (re-run 2026-10-06 on `main`, full corpus) |
|---|---|
| Evaluation cases | **150/150**, 3 repeats, variance 0 · unsafe verdicts 0 · forbidden vocabulary 0 |
| False alarms on 500 verbatim corpus segments | **0/500** |
| IslamicEval 2025 subtask 1B (public dev) | **78.54 %**, false confirmations **2** of 100 wrong spans ([report](eval/islamiceval/REPORT_1B.md)) |
| Backend tests | **345** passed · ruff + mypy strict clean |
| Telegram bot tests | **110** passed |
| Frontend | tsc · oxlint 0 errors · vitest **32/32** · e2e **4/4** (2026-10-05, two phone viewports, axe) · **87.4 kB** gzip main JS |
| Dependency audit | pip-audit 0 · npm audit 0 (2026-10-05) |
| Boot (snapshot) | **0.78 s** · 71 987 records |

Every response carries a `determinism_hash` = sha256(corpus fingerprint + normalized input + ordered verdicts).
Same input on the same corpus build ⇒ same hash. A judge can re-run and compare. See [`eval/REPORT.md`](eval/REPORT.md)
and [`docs/MODELS.md`](docs/MODELS.md) for the model benchmark (20 models on the real extraction prompt).

## Quick start

### One command

```bash
git clone https://github.com/MoTechSys/Project-Basira.git && cd Project-Basira
bash run.sh            # → http://localhost:8000   (UI · REST /v1 · OpenAPI /docs · MCP /mcp)
```

`run.sh` checks prerequisites, fetches and **sha256-verifies** the corpora, creates the venv, builds the index, runs the
backend gates, builds the UI, runs the 8-case smoke test on the real corpus, then starts the server. It is idempotent:
the first run takes a few minutes (≈ 230 MB of corpus download + index build), later runs skip setup and start in seconds (`--check` re-runs every gate).

| Variant | Command | Needs |
|---|---|---|
| Native (default) | `bash run.sh` | Python ≥ 3.12, Node ≥ 20, internet on first run, ~2 GB disk |
| Docker only | `bash run.sh --docker` | Docker |
| Verify without serving | `bash run.sh --check` | as native |
| Compose (prod-like, read-only, non-root) | `docker compose up` | Docker |

### Step by step (what `run.sh` does)

```bash
bash scripts/bootstrap.sh      # corpora → venv → index → fixture → ruff + mypy + pytest
make web-install web-build     # UI → frontend/dist (served by the backend at /)
make smoke                     # 8 canonical cases on the real corpus → SMOKE OK
make eval-full                 # 150 cases ×3 + 500 false-alarm segments → 150/150 · 0/500
make serve-mcp                 # API + UI + MCP on http://localhost:8000
```

```bash
curl -s localhost:8000/v1/check -H 'Content-Type: application/json' \
  -d '{"text":"قال تعالى: ﴿إن الله مع الصابرين﴾","ui_lang":"ar"}' | jq '.quotes[0].status'
# "found"
```

MCP client config: `{"mcpServers":{"basira":{"type":"http","url":"https://basirapp.site/mcp"}}}`
Deployment details and the reverse-proxy variables you **must** set: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## API keys and environment variables

**No key is required.** Without one, Basira runs fully offline with deterministic rules + corpus anchors, and every
response says so (`extraction_degraded`). A key only adds an optional model that *proposes* quote positions and reads
images (OCR); it never decides a state and never writes text the user sees (ADR-005).

No secret is committed. `.env` is git-ignored; [`.env.example`](.env.example) documents every variable.

| Variable | Where to get it | Used for |
|---|---|---|
| `LLM_API_KEY` | **Genspark** API key from your Genspark account, with `LLM_BASE_URL=https://www.genspark.ai/api/llm_proxy/v1` — or an OpenAI key from https://platform.openai.com/api-keys with `LLM_BASE_URL=https://api.openai.com/v1` (any OpenAI-compatible endpoint works) | optional span proposals + OCR |
| `LLM_MODEL` | model id; measured default `gpt-5.4-mini` ([`docs/MODELS.md`](docs/MODELS.md)) | — |
| `BASIRA_EVAL_KEY` | any random string: `openssl rand -hex 24` | `X-Eval-Key` header bypasses the 30 req/min limit (your own eval runs, the bot) |
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) → `/newbot` | bot only, in `integrations/telegram/.env` ([`.env.example`](integrations/telegram/.env.example)) |

Two ways to set the model key:

```bash
# 1) environment (local / docker)
cp .env.example .env            # then fill: LLM_PROVIDER=openai-compatible, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
                                #            VISION_PROVIDER=openai-compatible
set -a; . ./.env; set +a; make serve-mcp      # docker compose reads .env automatically

# 2) once from the UI: open /settings, paste the Genspark key, pick a model.
#    The server verifies it with one 5-token call, stores it in backend/.runtime/model.json (0600, git-ignored),
#    and never echoes it back (E-051).
```

## Built with AI

Development used frontier coding models through **Genspark** — **Claude Opus 5.5**, **Claude Fable 5.1** and
**GPT-6 Astra** — as pair programmers under the rules in [`AGENTS.md`](AGENTS.md): every safety invariant has a named
test, every number is measured and dated, every decision is recorded in [`docs/DECISIONS.md`](docs/DECISIONS.md),
and no religious text was ever typed by a model (tests derive every case from corpus record IDs).
The runtime model is a separate, optional component, chosen by benchmark ([`docs/MODELS.md`](docs/MODELS.md)).
Full disclosure: [`AI_USAGE.md`](AI_USAGE.md).

## Development timeline

A prototype existed before the challenge window; the product was built and finished during **4–6 October 2026**.
The last commit before the window is tagged [`baseline-pre-oct4`](https://github.com/MoTechSys/Project-Basira/tree/baseline-pre-oct4)
(`30e23a5`, 4 Oct 08:45 Riyadh). Compare exactly what was added in the window:
[`baseline-pre-oct4...main`](https://github.com/MoTechSys/Project-Basira/compare/baseline-pre-oct4...main).
Before the window (111 files): the backend core — normalisation, exact/fuzzy matching, harakat gate, state machine,
validator V1–V6, first corpus anchor, snapshot — corpus fetchers, ADRs, CI; the UI folder was empty.
In the window: rasm-uniqueness proof + V7, whole-ayah and phrase-rarity anchors, the entire web UI, image (OCR) mode,
English gate, Guard, verification receipt, MCP server, Telegram bot, model benchmark + `/settings`, the 150-case and
IslamicEval evaluations (backend tests 9 → 21 files), production deployment.

## How it works — the engine

```
 text / image / chatbot answer
            │
            ▼
 ┌──────────────────────────────┐   optional model PROPOSES spans (start,end) — re-located verbatim or dropped
 │ 1 EXTRACT  rules + corpus    │◄──────────────────────────────────────────────┐
 │   anchors (always run)       │                                               │
 └──────────────┬───────────────┘                                  ┌────────────┴─────────────┐
                ▼                                                  │ model (optional)         │
 ┌──────────────────────────────┐                                  │ span proposal · OCR ·    │
 │ 2 NORMALISE  strict / loose  │                                  │ English pick-or-refuse   │
 │   / bare tiers, offsets kept │                                  │ never decides, never     │
 └──────────────┬───────────────┘                                  │ writes user-visible text │
                ▼                                                  └──────────────────────────┘
 ┌──────────────────────────────┐
 │ 3 MATCH  exact positional →  │  numpy posting-list intersection over 4.5 M tokens (<5 ms/quote)
 │   BM25 + char-3-gram → RRF → │  sparse retrieval, reciprocal-rank fusion (k = 60)
 │   windowed token-Levenshtein │  windows {0.8n, n, 1.2n}
 └──────────────┬───────────────┘
                ▼
 ┌──────────────────────────────┐
 │ 4 GATES  strict · harakat ·  │  hamza/ة/ى kept · vowel conflicts · rasm-uniqueness proof · foreign tokens
 │   rasm · foreign material    │
 └──────────────┬───────────────┘
                ▼
 ┌──────────────────────────────┐
 │ 5 DECIDE  state.py — the ONLY│  pure function of evidence + thresholds; invariants I1–I19
 │   place a status is assigned │
 └──────────────┬───────────────┘
                ▼
 ┌──────────────────────────────┐
 │ 6 VALIDATE  V1–V7            │  re-derives every `found` from the store alone; can only downgrade
 └──────────────┬───────────────┘
                ▼
   CheckResponse + letter-level diff + determinism_hash ──► Web · REST · MCP · Guard · Receipt · Telegram
```

**Who decides.** The language model is an optional *extraction assistant*. It proposes where a quotation might be,
reads text from images, and — for English quotes — may pick one of the engine's own candidates or refuse. It never
assigns a state and never writes a word the user reads. Matching, gating, the decision and the validation are
deterministic code. Turn the model off (`LLM_PROVIDER=mock`) and every verdict on a marked quote is byte-identical
(same `determinism_hash`, tested in `backend/tests/test_byok.py`).

### Algorithms

| Stage | Technique | Where |
|---|---|---|
| Quote extraction (rules) | Bracket pairs ﴿﴾ «» "" () · introducer lexicon («قال تعالى», «قال رسول الله ﷺ», «وفي الحديث»…) to sentence end · trailer lexicon («رواه البخاري», «صدق الله العظيم») back to the previous boundary · claimed-source parser («[البقرة: 255]», «رواه مسلم») by dictionary | `extract/rules.py` |
| Unmarked quotes | **Corpus-anchored seed-and-extend** (BLAST-style): every n-token run of the input that exists verbatim in the corpus is a seed; extended while the corpus agrees; stop-word seeds rejected; whole-ayah acceptance; **phrase-rarity** acceptance (≥ 3 tokens occurring ≤ 60× in 71 987 records); isnad guard | `extract/anchor.py` |
| Normalisation | Three orthographic tiers with character offsets into the original: **strict** (keeps hamza forms, ة/ه, ى/ي — required for `found`), **loose** (retrieval), **bare** (rasm proof); Uthmani marks, tatweel, bidi marks stripped; ٱ→ا | `normalize.py` |
| Exact match | Positional inverted index; rarest-token-first posting-list intersection (numpy) inside one surah/record stream; strict gate on the hit window | `match/exact.py` |
| Retrieval | **BM25** over loose words + **TF over character 3-grams**, both CSR inverted indexes in numpy, fused with **Reciprocal Rank Fusion** (k = 60). Dense vectors deliberately off | `retrieve/index.py` |
| Fuzzy match | Windowed **token-level Levenshtein** (`rapidfuzz`), windows {0.8n, n, 1.2n}; Quran windows mapped back to real ayah boundaries (cross-ayah quotes supported) | `match/window.py` |
| Diff | `SequenceMatcher` on strict tokens, projected to **character ranges** on both the user's text and the verbatim source, so the UI highlights without re-rendering religious text | `match/diff.py` |
| Harakat gate (Quran) | A vowel mark the user **wrote** that contradicts the Mushaf on the same letter → difference (e.g. subject/object flip in 35:28); an unwritten mark is never a contradiction | `match/harakat.py` |
| Rasm-uniqueness proof | Bare-typed text («قل هو الله احد») is `found` **iff** the corpus spells that span exactly one way across every position; otherwise `needs_review/rasm_ambiguous` with the competing spellings and counts (إنّ/أنّ, على/علي) | `match/rasm.py` |
| Decision | Pure state machine over evidence + thresholds (hadith partial ≥ 0.75, hadith review ≥ 0.70, Quran review ≥ 0.60, short-quote rules). Quran is never `partial_match` | `state.py` |
| Post-validator | **V1** shown text = corpus bytes · **V2** every ref exists · **V3** grade = HadeethEnc's own · **V4** forbidden-lexicon scan of everything we generate · **V5** disclaimer present · **V6** independent re-proof of every `found` from the token store (never from matcher output) · **V7** independent re-proof of every rasm-completed `found` | `verify.py` |
| Determinism | `determinism_hash = sha256(corpus fingerprint + normalised input + ordered verdicts)`, also in header `X-Basira-Determinism-Hash` | `pipeline.py` |
| English gate | BM25 over QuranEnc Saheeh/Rwwad + HadeethEnc EN → cross-referenced to the Arabic record → rule pick (top-1 ≥ 0.9, gap ≥ 0.3) or constrained model pick `{"pick": k}` / refuse | `english_gate.py` |
| Guard | Whole chatbot answer → `clear` / `flagged` / `no_quotes` + fixed bilingual summaries | `guard.py` |
| Receipt | Stateless: `token = base64url(zlib(json{text, lang}))`; `GET /v/{token}?h=` re-runs the pipeline and answers `verified_now` / `stale` — nothing is stored | `main.py` |
| Boot | Corpus snapshot memory-mapped (numpy) → **0.78 s** boot, 71 987 records | `snapshot.py` |

### Safety invariants (each one has a named test)

| | Invariant |
|---|---|
| I1 | Quran is never `partial_match`; any difference from the Mushaf → `needs_review` |
| I2 | `found` requires a strict-tier match (hamza, ة, ى as written) |
| I3 | Quran `not_found` shows no candidate ayah (a wrong ayah next to a false claim is harmful) |
| I5 | Short quotes: only exact → `found`; never `partial_match` |
| I6 | A hadith grade line appears only when it is HadeethEnc's own field, verbatim and attributed |
| I7 | Non-Arabic quotes → `needs_review` (English gate offers approved translations + the Arabic original) |
| I8, I10–I13 | Wrong surah/ayah claimed, Quran introduced as hadith (or the reverse) → a descriptive notice; the status never changes |
| I14 | Contradicting vowel marks are a difference anywhere in the word |
| I15 | Foreign material inside a quote (Latin letters, digits, symbols) → `needs_review` |
| I16 | Every occurrence gets its own verdict; repeats merge only if byte-identical |
| I17 | Every `found` has an independent proof (V6) |
| I18–I19 | Rasm completion only with a corpus-proven unique spelling; otherwise the alternatives are shown |

Full list with test names: [`SAFETY.md`](SAFETY.md) · decisions D-001…D-015, E-001…E-065: [`docs/DECISIONS.md`](docs/DECISIONS.md).

### Evaluation methodology

- **150 cases, 13 categories** (`eval/cases.yaml`, generated by `eval/gen_cases.py`, seed 20261004). Cases reference
  corpus records **by ID + token window** and apply mechanical mutations, so the eval contains no hand-typed religious
  text: Quran verbatim / cross-ayah (20), orthographic fold (12), near-miss (16), Quran-attributed prose (8), hadith
  verbatim (18), 1-token variant (14), heavy edits (10), hadith-attributed prose (8), claimed-source mismatch (10),
  **prompt injection** (8), non-Arabic / short (8), out-of-scope requests (8), offset robustness (10).
  Result: **150/150**, 3 repeats, variance 0, unsafe 0, recall@found = precision@found = 1.000 (89/89).
- **False alarms:** 500 verbatim corpus segments in neutral wrappers → **0/500** (95 % CI 0–0.76 %).
- **External:** IslamicEval 2025 subtask 1B public dev set, official metric → **78.54 %** (CI 73.0–83.2), and the
  number that matters for a checker: **2 of 100** wrong spans confirmed as correct. Published test-set scores
  (TCE 89.82 %, Burhan AI 88.60 %) are shown for context only — dev vs test, not head-to-head.
  Every miss is listed with its reason in [`eval/islamiceval/REPORT_1B.md`](eval/islamiceval/REPORT_1B.md).
- **Limits are written next to the numbers:** generated cases measure the engine, not real-world prevalence;
  per-category n < 30 is indicative only. See [`eval/REPORT.md`](eval/REPORT.md).

### Tech stack

| Layer | Tools |
|---|---|
| Backend | Python 3.12/3.13 · FastAPI · Pydantic v2 · NumPy · RapidFuzz · httpx · Uvicorn · MCP Python SDK (Streamable HTTP) |
| Frontend | React 19 · TypeScript 6 · Vite 8 · custom History router · PWA service worker · RTL-first, AR/EN, dark/light · Readex Pro + Amiri Quran |
| Quality | ruff · mypy `--strict` · pytest (345) · vitest (32) · Playwright e2e on two phone viewports + axe accessibility · oxlint · pip-audit · npm audit · forbidden-lexicon gate |
| Ops | Multi-stage Docker (non-root, read-only rootfs, snapshot built at image time) · Caddy (TLS) · GitHub Actions CI (gates + image build + `/health` build-sha check) · systemd auto-deploy from `main` |
| Bot | python-telegram-bot client of the public API (110 tests), Rich Messages, no model, no storage |
| Models (optional, runtime) | Any OpenAI-compatible endpoint; 20 models benchmarked on the real extraction prompt; default `gpt-5.4-mini` ([`docs/MODELS.md`](docs/MODELS.md)) |

## Sources and licences

Tanzil (Uthmani, simple-clean, simple — CC BY 3.0, verbatim only) · Open-Hadith-Data, 9 books (ODbL/DbCL) ·
HadeethEnc (link-only by default) · QuranEnc translations (Saheeh International, Rwwad) · HadeethEnc EN.
Every file is sha256-pinned in [`corpus/manifest.json`](corpus/manifest.json); `/health` exposes the index fingerprint.
Full register: [`SOURCES.md`](SOURCES.md) · [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) · [`AI_USAGE.md`](AI_USAGE.md).

## Repository layout

```
run.sh          one-command setup + run (native or --docker)
backend/        FastAPI service (Python ≥ 3.12) — app/{extract,match,retrieve,providers}, verify.py, devgate.py, mcp_server.py
frontend/       React 19 · Vite · TypeScript — multi-page PWA, RTL-first
corpus/         manifest.json (sha256 pins), fetch + index + fixture builders   (data/ and index/ are git-ignored)
eval/           150 cases, false-alarm generator, English gate eval, IslamicEval 2026 runners, REPORT.md
messages/       ar.json / en.json — the ONLY source of user-facing prose
scripts/        bootstrap · smoke · mcp_demo · bench_models · lexicon gate · generators
docs/           ARCHITECTURE · API · SAFETY-adjacent docs · DECISIONS (E-001…E-065) · STATE · adr/ · KNOWLEDGE
integrations/   telegram/ — @BasiraCheckBot, a thin client of the public API (no model, no storage)
deploy/vps/     Caddy + compose overlay + auto-deploy timer that publishes `main` to basirapp.site
.github/        GitHub Actions workflow (ci.yml: gates + docker build + /health build_sha check)
```

## Documentation map

| Need | Read |
|---|---|
| Run it locally in one command | [`run.sh`](run.sh) · [Quick start](#quick-start) |
| Rules for contributors (human or AI-assisted) | [`AGENTS.md`](AGENTS.md) |
| Why things are the way they are | [`docs/DECISIONS.md`](docs/DECISIONS.md) (product + engineering decisions, dated) · [`docs/adr/`](docs/adr/) |
| API / MCP / Guard contracts | [`docs/API.md`](docs/API.md) · [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md) · [`docs/GUARD.md`](docs/GUARD.md) |
| Safety invariants, security model | [`SAFETY.md`](SAFETY.md) · [`SECURITY.md`](SECURITY.md) · [`docs/RISKS.md`](docs/RISKS.md) |
| Release history | [`CHANGELOG.md`](CHANGELOG.md) |
| Sources, licences, AI disclosure | [`SOURCES.md`](SOURCES.md) · [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) · [`AI_USAGE.md`](AI_USAGE.md) |

## Contributing

Conventional Commits · every change passes `make lint && make test && make smoke` · product decisions are never
re-litigated (see `docs/DECISIONS.md`) · see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

Apache-2.0 — see [`LICENSE`](LICENSE). Corpus data carry their own licences (above).
