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

**Requirements:** Python ≥ 3.12, Node 22, `make`, ~2 GB free disk (corpora). Or only Docker.

```bash
git clone https://github.com/MoTechSys/Project-Basira.git && cd Project-Basira
bash scripts/bootstrap.sh      # fetch + sha256-verify corpora → venv → build index → lint/types/tests  (~3 min)
make web-install web-build     # build the UI into frontend/dist (served by the backend at /)
make smoke                     # 8 canonical cases on the real corpus → must print SMOKE OK
make eval-full                 # 150 cases ×3 + 500 false-alarm segments → 150/150 · 0/500
make serve-mcp                 # API + UI + MCP on http://localhost:8000
```

```bash
curl -s localhost:8000/v1/check -H 'Content-Type: application/json' \
  -d '{"text":"قال تعالى: ﴿إن الله مع الصابرين﴾","ui_lang":"ar"}' | jq '.quotes[0].status'
# "found"
```

MCP client config: `{"mcpServers":{"basira":{"type":"http","url":"https://basirapp.site/mcp"}}}`

Docker: `docker compose up` (multi-stage image, snapshot built at image time, non-root, read-only). Deployment details
and the reverse-proxy variables you **must** set: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

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

Development used frontier coding models through Genspark — **Claude Opus 5.5**, **Claude Fable 5.1** and
**GPT-6 Astra** — under the rules in [`AGENTS.md`](AGENTS.md): every invariant has a named test, every number is
measured, every decision is dated in [`docs/DECISIONS.md`](docs/DECISIONS.md). The same models were benchmarked on
Basira's real extraction prompt before choosing the runtime default ([`docs/MODELS.md`](docs/MODELS.md)).
Full disclosure, including what AI is never allowed to do here: [`AI_USAGE.md`](AI_USAGE.md).

## Architecture in one picture

```
 text / image / English / answer
            │
            ▼
 ┌─────────────────────┐   proposes spans only; never shown      ┌──────────────────────────┐
 │ rules + corpus      │◄────────────────────────────────────────│ model (optional, BYOK)   │
 │ anchors (extract/)  │                                         │ extraction · OCR · picker│
 └─────────┬───────────┘                                         └──────────────────────────┘
           ▼
 ┌─────────────────────┐  two-tier normalisation (strict / loose), n-gram index, byte-exact windows
 │ deterministic match │  harakat policy (D-013), foreign-token gate, per-occurrence verdicts
 └─────────┬───────────┘
           ▼
 ┌─────────────────────┐  V1–V6: messages from messages/*.json only · forbidden lexicon · link policy
 │ post-validator      │  V6 re-proves every `found` independently of the matcher
 └─────────┬───────────┘
           ▼
   CheckResponse + determinism_hash  ──►  REST · MCP · Guard · Receipt · UI
```

Details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · ADRs in [`docs/adr/`](docs/adr/).

## Sources and licences

Tanzil (Uthmani, simple-clean, simple — CC BY 3.0, verbatim only) · Open-Hadith-Data, 9 books (ODbL/DbCL) ·
HadeethEnc (link-only by default) · QuranEnc translations (Saheeh International, Rwwad) · HadeethEnc EN.
Every file is sha256-pinned in [`corpus/manifest.json`](corpus/manifest.json); `/health` exposes the index fingerprint.
Full register: [`SOURCES.md`](SOURCES.md) · [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) · [`AI_USAGE.md`](AI_USAGE.md).

## Repository layout

```
backend/        FastAPI service (Python 3.13) — app/{extract,match,retrieve,providers}, verify.py, devgate.py, mcp_server.py
frontend/       React 19 · Vite · TypeScript — multi-page PWA, RTL-first
corpus/         manifest.json (sha256 pins), fetch + index + fixture builders   (data/ and index/ are git-ignored)
eval/           150 cases, false-alarm generator, English gate eval, IslamicEval 2026 runners, REPORT.md
messages/       ar.json / en.json — the ONLY source of user-facing prose
scripts/        bootstrap · smoke · mcp_demo · bench_models · lexicon gate · generators
docs/           ARCHITECTURE · API · SAFETY-adjacent docs · DECISIONS (E-001…E-064) · STATE · adr/ · KNOWLEDGE
integrations/   telegram/ — @BasiraCheckBot, a thin client of the public API (no model, no storage)
deploy/vps/     Caddy + compose overlay + auto-deploy timer that publishes `main` to basirapp.site
.github/        GitHub Actions workflow (ci.yml: gates + docker build + /health build_sha check)
```

## Documentation map

| Need | Read |
|---|---|
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
