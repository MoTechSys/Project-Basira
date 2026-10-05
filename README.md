<div align="center">

# 🕌 بصيرة · Basira

### **Deterministic verification of Quran & Hadith quotations — before you publish.**

<p align="center">
  <em>Paste any text, image, or AI answer. Basira finds every Quran/Hadith quote,<br/>
  matches it <strong>byte-exactly</strong> against licensed sources, and shows you<br/>
  the diff — vowel marks and all. No judgment. No generation. No storage.</em>
</p>

<p align="center">
  <a href="https://basirapp.site"><img src="https://img.shields.io/badge/🌐_Try_Live-basirapp.site-2EF2C2?style=for-the-badge&labelColor=12183F" alt="Live Demo"/></a>
  <a href="https://github.com/MoTechSys/Project-Basira/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/MoTechSys/Project-Basira/ci.yml?branch=main&style=for-the-badge&logo=github&label=CI&labelColor=12183F" alt="CI"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-6150EA?style=for-the-badge&labelColor=12183F" alt="License"/></a>
</p>

<p align="center">
  <img src="https://img.shields.io/github/stars/MoTechSys/Project-Basira?style=flat-square&logo=github&color=FFD700&labelColor=12183F" alt="Stars"/>
  <img src="https://img.shields.io/github/forks/MoTechSys/Project-Basira?style=flat-square&logo=github&color=6150EA&labelColor=12183F" alt="Forks"/>
  <img src="https://img.shields.io/github/last-commit/MoTechSys/Project-Basira?style=flat-square&logo=git&color=2EF2C2&labelColor=12183F" alt="Last Commit"/>
  <img src="https://img.shields.io/github/commit-activity/w/MoTechSys/Project-Basira?style=flat-square&color=FF6B9D&labelColor=12183F" alt="Commit Activity"/>
  <img src="https://img.shields.io/github/languages/top/MoTechSys/Project-Basira?style=flat-square&color=3178C6&labelColor=12183F" alt="Top Language"/>
  <img src="https://img.shields.io/badge/false_alarms-0%2F500-2EF2C2?style=flat-square&labelColor=12183F" alt="Zero false alarms"/>
  <img src="https://img.shields.io/badge/eval-150%2F150-2EF2C2?style=flat-square&labelColor=12183F" alt="150/150 eval"/>
  <img src="https://img.shields.io/badge/variance-0-2EF2C2?style=flat-square&labelColor=12183F" alt="Zero variance"/>
</p>

<p align="center">
  <strong>Track 4 entry · <em>AI in Service of Islamic Content Challenge 2026 (IslamicAIch)</em></strong><br/>
  <sub>Arabic-first · bilingual AR / EN · RTL · PWA · MCP server for AI assistants</sub>
</p>

<p align="center">
  <a href="https://basirapp.site"><kbd>&nbsp;&nbsp;🚀&nbsp;Try&nbsp;it&nbsp;now&nbsp;&nbsp;</kbd></a>&nbsp;·&nbsp;
  <a href="#quick-start"><kbd>&nbsp;&nbsp;⚡&nbsp;Quick&nbsp;Start&nbsp;&nbsp;</kbd></a>&nbsp;·&nbsp;
  <a href="docs/API.md"><kbd>&nbsp;&nbsp;📘&nbsp;API&nbsp;Docs&nbsp;&nbsp;</kbd></a>&nbsp;·&nbsp;
  <a href="SAFETY.md"><kbd>&nbsp;&nbsp;🛡️&nbsp;Safety&nbsp;Model&nbsp;&nbsp;</kbd></a>&nbsp;·&nbsp;
  <a href="eval/REPORT.md"><kbd>&nbsp;&nbsp;📊&nbsp;Evaluation&nbsp;&nbsp;</kbd></a>
</p>

</div>

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
| Model settings — Genspark key saved once on the server | `/settings` · `PUT /v1/models/config` | live |

## Measured, not claimed

| Gate | Result (2026-10-05, full corpus, clean clone) |
|---|---|
| Evaluation cases | **150/150**, 3 repeats, variance 0 |
| False alarms on 500 verbatim corpus segments | **0/500** |
| Unsafe verdicts / forbidden vocabulary | 0 / 0 |
| IslamicEval 2025 subtask 1B (public dev) | **78.54 %**, false confirmations **2** of 100 wrong spans ([report](eval/islamiceval/REPORT_1B.md)) |
| Backend tests | **304** passed, none skipped · ruff + mypy strict clean |
| Frontend | tsc · oxlint 0 errors · vitest **30/30** · e2e **4/4** (incl. two phone viewports, axe) · **86.7 kB** gzip JS |
| Dependency audit | pip-audit 0 · npm audit 0 |
| Boot (snapshot) | **0.78 s** · **314 MB** RSS · 71 987 records |

Every response carries a `determinism_hash` = sha256(corpus fingerprint + normalized input + ordered verdicts).
Same input on the same corpus build ⇒ same hash. A judge can re-run and compare. See [`eval/REPORT.md`](eval/REPORT.md)
and [`docs/MODELS.md`](docs/MODELS.md) for the model benchmark (20 models on the real extraction prompt).

## Quick start

```bash
git clone https://github.com/MoTechSys/Project-Basira.git && cd Project-Basira
bash scripts/bootstrap.sh      # fetch + sha256-verify corpora → venv → build index → lint/types/tests  (~3 min)
make smoke                     # 8 canonical cases on the real corpus → must print SMOKE OK
make serve-mcp                 # API + UI + MCP on http://localhost:8000
```

```bash
curl -s localhost:8000/v1/check -H 'Content-Type: application/json' \
  -d '{"text":"قال تعالى: ﴿إن الله مع الصابرين﴾","ui_lang":"ar"}' | jq '.quotes[0].status'
# "found"
```

MCP client config: `{"mcpServers":{"basira":{"type":"http","url":"https://<host>/mcp"}}}`

Docker: `docker compose up` (multi-stage image, snapshot built at image time, non-root). Deployment details and the
reverse-proxy variables you **must** set: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

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
docs/           ARCHITECTURE · API · SAFETY-adjacent docs · DECISIONS (E-001…E-054) · STATE · adr/ · KNOWLEDGE
.github/        GitHub Actions workflow (ci.yml, active — E-058)
```

## Documentation map

| Need | Read |
|---|---|
| Rules for contributors (human or AI-assisted) | [`AGENTS.md`](AGENTS.md) |
| Why things are the way they are | [`docs/DECISIONS.md`](docs/DECISIONS.md) (product + engineering decisions, dated) · [`docs/adr/`](docs/adr/) |
| API / MCP / Guard contracts | [`docs/API.md`](docs/API.md) · [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md) · [`docs/GUARD.md`](docs/GUARD.md) |
| Safety invariants, security model | [`SAFETY.md`](SAFETY.md) · [`SECURITY.md`](SECURITY.md) · [`docs/RISKS.md`](docs/RISKS.md) |
| Release history | [`CHANGELOG.md`](CHANGELOG.md) |

## Contributing

Conventional Commits · every change passes `make lint && make test && make smoke` · product decisions are never
re-litigated (see `docs/DECISIONS.md`) · see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

Apache-2.0 — see [`LICENSE`](LICENSE). Corpus data carry their own licences (above).

---

<div align="center">

### 🌙 Built for the Ummah, measured for the judges.

<sub>
  <strong>IslamicAIch 2026 · Track 4</strong> &nbsp;·&nbsp;
  <a href="https://basirapp.site">basirapp.site</a> &nbsp;·&nbsp;
  <a href="https://github.com/MoTechSys/Project-Basira/issues">Issues</a> &nbsp;·&nbsp;
  <a href="https://github.com/MoTechSys/Project-Basira/discussions">Discussions</a>
</sub>

<p align="center">
  <sub>If Basira helps you ship safer Islamic content, consider a ⭐ — it's the only metric we don't measure ourselves.</sub>
</p>

</div>
