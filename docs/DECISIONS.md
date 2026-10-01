# DECISIONS.md — Decision log (owner + engineering)

> Append-only. Format: `D-###` · date · who · decision · reason · affects. Never re-open a decision without a new entry that supersedes it.

## Owner decisions (from the owner, verbatim intent)

| ID | Date | Decision | Reason / intent | Affects |
|---|---|---|---|---|
| D-001 | 2026-09-30 | **Merge directly to `main`; no PR review cycle.** Engineer is fully responsible for verify→merge. | Owner does not review PRs. | CLAUDE.md, workflow |
| D-002 | 2026-09-30 | **Start coding NOW** in this repo. On **Oct 4** a **fresh repository** will be created and the work migrated «as if new». | Owner's plan for the challenge window (terms §8: only Oct 4–6 work is evaluated; this repo is the private rehearsal). | Everything: this repo = *rehearsal*; `docs/STATE.md` must always allow a clean re-creation. |
| D-003 | 2026-09-30 | **Repository must be self-explanatory to a new AI agent/account** — full memory, structure, state, so it continues seamlessly. | Owner may switch accounts/agents. | AGENTS.md, STATE.md, DECISIONS.md, GLOSSARY.md, ADRs |
| D-004 | 2026-09-30 | **Providers/hosting accounts (Render, Cloudflare, LLM APIs) are NOT to be set up now.** Engineer tests locally in the sandbox. Accounts are handled on competition day. | Owner: «مش وقتها». | Local-first architecture; provider layer behind an interface with a **mock/offline** implementation. |
| D-005 | 2026-09-30 | **Data sources**: use what the organizer's documents approve. Build to the highest standard. | Owner defers to the official annex. | Corpus = Tanzil (Quran, Hafs, Uthmani display) + Open-Hadith-Data (9 books) + HadeethEnc grades; referral links to dorar.net/hadith, shamela.ws, quranpedia.net. |
| D-006 | 2026-09-30 | **Attribution intent**: all work is the **owner's** work. Research team and AI agents are the owner's tools. Nothing may be phrased as «this was made by AI instead of the participant». Disclosure of AI **tools** in `AI_USAGE.md` is done because the terms (§9) require it — worded as *tools used by the participant*. | Owner's explicit intent. | AI_USAGE.md wording, README, deck, video. |
| D-007 | 2026-09-30 | Owner asked for plain-language explanation of: extension (Guard API), OHD, HadeethEnc, Apache-2.0 before deciding. → **Pending** (see «Open owner questions»). | — | LICENSE, HADEETHENC_MODE, P2 scope |
| D-008 | 2026-10-01 | **Multi-model professional team, maximum reasoning, cost is not a criterion.** Each role is bound to one specific frontier model chosen for the task (Opus 5.5 / Fable 5.1 / GPT-6 Astra / GPT-6.1 Sol / Sonnet 5.5 / DeepSeek V4 Pro / Kimi K3 / Luna-max), run at deepest reasoning (thinking / xhigh). Agents research, analyse, review each other across families, and debate under the orchestrator. Risks studied up-front. | Owner: «فريق محترف وليس عشوائية… الأقوى… الوضع العميق… الأرصدة لا تهمني… العمل الجاد والدقيق». | `docs/TEAM.md`, `docs/RISKS.md`, `docs/work-packages/`, `docs/reviews/` |
| D-009 | 2026-10-01 | **Strongest models only; weak ones removed; selection by sourced research, not availability.** Roster rebuilt on `claude-opus-5-5`, `claude-fable-5-1`, `gpt-6-astra`, `gpt-6.1-sol` exclusively, all at max reasoning. Research with primary/independent sources archived in `docs/model-analysis/` (تحليل النماذج العالمية). Supersedes the roster part of D-008. | Owner: «ليش بتسوي موديلات ضعيفة… الأقوى… سوي بحث ووثق… شغل مؤسسات». | `docs/model-analysis/`, `docs/TEAM.md` |

## Engineering decisions (by the engineer, within owner intent)

| ID | Date | Decision | Reason | ADR |
|---|---|---|---|---|
| E-001 | 2026-09-30 | Stack = **FastAPI (Python 3.13) backend + React/Vite/TS frontend**, in-memory index built at deploy, no DB. | Mandated by BUILD_SPEC; index needs a long-running process (not Workers). | ADR-001 |
| E-002 | 2026-09-30 | **Dual-orthography matching**: loose normalization for retrieval, **strict** re-verification before `found`. | Audit T1: loose-only normalization returns `found` for misspelled ayat (verified on 11 verses). | ADR-002 |
| E-003 | 2026-09-30 | **Exact matching runs on the full inverted index**, RRF only for fuzzy fallback. | Audit T3: RRF top-100 can drop the exact hit. | ADR-002 |
| E-004 | 2026-09-30 | **Vector channel OFF in P0** (`RETRIEVAL_VECTORS=off`). | Audit T8: unmeasured recall, +RAM, +licence row. | ADR-002 |
| E-005 | 2026-09-30 | Quran states: `found` (strict 1.0) / `needs_review` (with diff + السورة:الآية + qirāʾa caveat, one render unit) / `not_found` (**no candidates shown**). `partial_match` never for Quran. | Audit B-A1/A2 + SAFETY §1. | ADR-003 |
| E-006 | 2026-09-30 | Hadith `partial_match` carries a transmission-variant caveat. Cross-corpus rule: a 1.0 Quran match wins regardless of attribution. | Audit B-A5/A8. | ADR-003 |
| E-007 | 2026-09-30 | **No storage** of user input, period. Report button → pre-filled GitHub Issue. No server-side report store. | Terms §9; audit C2. | ADR-004 |
| E-008 | 2026-09-30 | Provider layer = `LLMClient` interface with `MockProvider` (offline, deterministic) as default in dev/test; real providers plugged on competition day. | D-004. | ADR-005 |
| E-009 | 2026-09-30 | `messages/ar.json` & `en.json` are the single source of user-facing prose; frontend imports them at build. Forbidden-word scanner whitelists corpus book names and literal corpus fields. | Audit C1/C6. | ADR-003 |
| E-010 | 2026-09-30 | Display Quran in **Uthmani** rasm (Tanzil), index both rasms. | Annex approves King Fahd Complex (Uthmani). | ADR-002 |
| E-011 | 2026-09-30 | `/health` returns 503 until corpus loaded; reports doc counts, RSS, build sha. | Audit T6. | ADR-001 |
| E-012 | 2026-09-30 | Min quote length: 2 tokens Quran / 3 hadith unless quote-marked; ≤30 spans/request; positions shown ≤5 with total count. | Audit T13. | ADR-003 |
| E-013 | 2026-10-01 | **`corpus/fetch.py` TLS policy**: on a *certificate* failure (expired/untrusted/hostname) and **only** for files with a pinned sha256, retry once without certificate verification, print a loud warning, then enforce the sha256 as usual. `--strict-tls` forbids the fallback. Unpinned sources never fall back. | tanzil.net served an **expired Let's Encrypt cert** (notAfter 2026-09-30 11:47 UTC) on 2026-10-01, breaking `bootstrap.sh` step 1 on a fresh sandbox. The sha256 pin already makes content integrity independent of the channel; a hard failure would block all work for an upstream ops lapse. Downloaded bytes re-verified identical to the pinned hashes. | ADR-001 (corpus pinning) |

## Open owner questions (need an answer; defaults applied until then)

| Q | Question (plain language in `docs/GLOSSARY.md`) | Default applied now |
|---|---|---|
| Q1 | Code licence — **Apache-2.0** recommended | Apache-2.0 placeholder `LICENSE` (easy to swap) |
| Q2 | HadeethEnc: show full hadith text (`embed`) or only grade+link (`link`)? | `link` (safer) |
| Q3 | Guard API (public API for other apps) stays a *conditional extension*, not a promise? | Yes — P2, unannounced |
| Q4 | Open-Hadith-Data upstream copyright unresolved — keep with full documentation + kill-switch? | Keep, `OHD_MODE=display`, documented |
