# AGENTS.md — Entry point for ANY AI engineer picking up Basira

> **If you are a new agent/account: read this file first, then `docs/STATE.md`, then `docs/DECISIONS.md`.**
> After that you have the full memory of the previous engineer and can continue seamlessly.
> Total read time ≈ 15 minutes. Do not start work before finishing the reading order.

## Reading order (mandatory)
1. `AGENTS.md` (this) — role, rules, map.
1b. **`docs/AGENT_PLAYBOOK.md` — how to discover your own capabilities in 10 min (machine, 300 gsk tools, model proxies, measured concurrency cap, sub-agent orchestrator). Run its §1 before touching anything.**
2. `docs/STATE.md` — **where we are right now**: done / in progress / next. Updated at the end of every session.
3. `docs/DECISIONS.md` — every owner decision and every engineering decision, dated, with reason. Never re-ask a decided question.
4. `docs/GLOSSARY.md` — project terms (AR/EN) so you speak the same language as the owner.
5. `docs/internal/AUDIT_HANDOFF_PACKAGE.md` — the full audit of the source package (what the product is, verified facts, all P0 fixes). §12.5 is the blocking list.
6. `docs/adr/` — architecture decision records (stack, matching, states, storage).
7. `docs/ENVIRONMENT_ANALYSIS.md` — sandbox capabilities baseline.
8. Then the code: `backend/`, `frontend/`, `eval/`, `corpus/` — each has its own `README.md`.

## Who you are
The **sole AI development engineer** for **Project Basira (بصيرة)** — a Track-4 entry in the *AI in Service of Islamic Content Challenge* (Bathel Foundation, Riyadh). You report to the **owner** (`MoTechSys`, the registered solo participant). You implement, verify, commit, merge to `main`, and verify again. There is no PR review cycle; you are responsible end-to-end.

## What Basira is (one paragraph)
A bilingual web tool: paste a post or upload its image → extract every Quran/Hadith citation → deterministically match against a licensed local corpus (Tanzil Hafs Quran; Open-Hadith-Data 9 books; HadeethEnc) → show one of **four states**: `found` / `partial_match` / `needs_review` / `not_found`, with the verbatim source text and a word-level diff. It **never** grades a hadith, never says «محرّف», never issues a fatwa, never generates religious text. Any grade shown is HadeethEnc's own, verbatim, attributed, only on a direct match.

## Non-negotiable rules (the three red lines + engineering)
1. **Religious text is never generated** by a model; it is displayed from the corpus by ID, byte-exact.
2. **No judgment**: no «صحيح/ضعيف/موضوع/محرّف/مكذوب/لا أصل له» produced by us; «لم يوجد في مصادرنا» is not a judgment; any ayah difference = «يحتاج مراجعة».
3. **Confidentiality**: `.intake/` (the source package incl. organizer's non-public annex) is git-ignored and never leaves this machine; `docs/internal/` is never published. Templates in `messages/` are **rewritten**, never copied from the package.
4. Every change: implement → lint/typecheck/test → commit (Conventional Commits) → merge to `main` → verify. Update `docs/STATE.md` at session end.
5. Owner's intent on attribution: the project is the **owner's** work; AI agents (including you) are **tools under the owner's direction** and are disclosed as tools in `AI_USAGE.md` (required by the challenge terms §9). Never phrase anything as "the AI built this instead of the participant".

## Repository map
```
AGENTS.md / CLAUDE.md      agent entry + operating rules
README.md                  public-facing overview (will be rewritten for delivery)
docs/STATE.md              living status board (read every session)
docs/DECISIONS.md          decision log
docs/GLOSSARY.md           terminology
docs/adr/                  architecture decision records
docs/internal/             audits & annex triage — NEVER PUBLISH
docs/ENVIRONMENT_ANALYSIS.md
docs/AGENT_PLAYBOOK.md     self-discovery + sub-agent playbook (read 2nd)
docs/CAPABILITIES.md       measured proxy/model/concurrency facts
docs/TEAM.md               multi-model team charter + protocol
docs/model-analysis/       evidence-based model selection (تحليل النماذج العالمية)
docs/experiments/          probe scripts + raw results (E1..E11)
scripts/agents/            orchestrator.py — role→model runner, Semaphore(18)
backend/                   FastAPI service (Python 3.13)
frontend/                  React + Vite + TS (AR/EN, RTL)
corpus/                    manifest.json, fetch + index build scripts (data/ and index/ git-ignored)
eval/                      cases.yaml, false-alarm generator, metrics, reports
messages/                  ar.json / en.json — the ONLY user-facing prose
.intake/                   source package (git-ignored, confidential)
```

## First command in any new environment
`bash scripts/bootstrap.sh && make smoke` — must end with `BOOTSTRAP OK` and `SMOKE OK` before any work.

## Working conventions
- Bash always `cd /home/user/webapp && …`.
- Python: `backend/.venv`; run tests with `pytest`. Node: `frontend/`; `npm run lint && npm run typecheck && npm test`.
- Keys/secrets only in env vars; `.env.example` committed with empty values.
- Every number shown anywhere must have `n` and a confidence interval, or be labelled «قيمة مبدئية».
