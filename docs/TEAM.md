# TEAM.md — Basira engineering team charter (multi-model, max-reasoning)

> **Document ID:** BASIRA-DOC-003 · **Date:** 2026-10-01 · **Owner decision:** D-008 (see DECISIONS.md)
> Every model named here was **called successfully from this sandbox today** (see `CAPABILITIES.md` §1 and probe log §6). No role is assigned to a model that was not tested.

## 1. Principles
1. **One role → one model → one reasoning level.** Chosen for the *task*, not for availability. No random pooling.
2. **Maximum depth everywhere.** Claude roles run with `thinking.enabled` (budget 8k–16k tokens); GPT roles run with `reasoning_effort: "xhigh"`. Cost is not a selection criterion (owner).
3. **Family diversity on every verdict.** Nothing merges unless the author's output was reviewed by a model from a *different* family. Same-family review is not review.
4. **Constraints are injected, not debated.** Every brief carries the three red lines (no generated religious text · no judgment · confidentiality) as *non-negotiable system constraints*. A model that argues against them is overruled; its technical findings are still used.
5. **The orchestrator owns the merge.** Agents produce artefacts; only the orchestrator runs gates (`ruff · mypy --strict · pytest · smoke`) and commits. Agent transcripts never enter git.
6. **Everything measured, nothing claimed.** Every number in any deliverable has `n` and a CI, or is labelled «قيمة مبدئية».

## 2. Roster

| # | Role | Model | Mode | Why this model | Owns |
|---|---|---|---|---|---|
| 0 | **Orchestrator / Lead engineer** | Claude (this session) | — | Holds the whole context, the owner's decisions, and the repo. Decomposes, briefs, merges, verifies. | `STATE.md`, `DECISIONS.md`, all commits |
| 1 | **Chief Architect & Code Author** | `claude-opus-5-5` | thinking 16k | Strongest reasoning + understood the sharia-safety domain unprompted. Writes the core: `providers/`, `pipeline.py`, `main.py`. | backend core |
| 2 | **Second Code Author (parallel track)** | `claude-fable-5-1` | thinking 16k | Same-tier Claude, independent weights → parallel work packages without serial dependency; also domain-aware. | `eval/`, frontend |
| 3 | **Adversarial Code Reviewer** | `gpt-6-astra` | xhigh | Different family; pushed back hard in probe → ideal for finding what Claude missed. Briefed with constraints as fixed. | review every PR-equivalent |
| 4 | **Test Engineer / Breaker** | `gpt-6.1-sol` | xhigh | Different family; generates adversarial inputs, boundary cases (±0.002 thresholds), property tests, fixture index. | `backend/tests/`, `test_api.py` |
| 5 | **Sharia-Safety & Messages Auditor** | `claude-opus-5-5` (separate context) | thinking 16k | Must grasp mawḍūʿ/ḍaʿīf nuance to catch *implied* judgment in prose. Audits `messages/*.json`, `SAFETY.md`, every user-facing string. | lexicon, templates, SAFETY |
| 6 | **Research & Sources Analyst** | `deep-seek-v4-pro` | native reasoning | Fast, reasoning-on, strong at structured extraction. Verifies licences, source provenance, competitor tools, OCR limits; every claim with URL. | `docs/research/` |
| 7 | **Risk Officer** | `kimi-k3` | native reasoning | Different family again; long-context; builds and maintains the risk register with likelihood/impact/mitigation/owner. | `docs/RISKS.md` |
| 8 | **Documentation & Delivery Writer** | `gpt-5.6-luna-max` | plain (fast) | Fastest high-quality writer in probe (2.4 s). Drafts `README`, `API.md`, `ARCHITECTURE.md`, `AI_USAGE.md` (D-006 wording), `CHANGELOG`. All drafts pass role 5. | delivery docs |
| 9 | **Eval Case Generator** (batch) | `claude-sonnet-5-5` | thinking 4k | Cheap-enough Claude for 150 cases + 500 false-alarm segments; domain-aware so cases are realistic. Output validated against corpus by code, not by a model. | `eval/cases.yaml` |

**Excluded:** `grok-4.7` (refused a benign instruction in probe — unreliable for briefed work), `nemotron`, `glm`, `minimax`, `mimo`, `trinity` (not evaluated; no role needs them).

## 3. Concurrency budget (hard platform cap: 20 in-flight per user)

| Lane | Reserved slots |
|---|---|
| Authors (roles 1, 2) | 2 |
| Reviewers / tests (3, 4) | 4 |
| Safety auditor (5) | 2 |
| Research + risk (6, 7) | 2 |
| Docs (8) | 1 |
| Eval batch (9) | 6 |
| Headroom | 3 |
| **Total** | **20** (soft limit used: 18) |

Enforced by one shared `asyncio.Semaphore(18)` + exponential backoff on 429 (verified 60/60, `CAPABILITIES.md` §2).

## 4. Protocol per work package (WP)

```
brief ──► author ──► self-check ──► reviewer (other family) ──► test engineer ──► safety auditor (if user-facing)
                                                                                        │
orchestrator: gates (ruff/mypy/pytest/smoke) ──► commit ──► merge main ──► verify ◄──────┘
```

- **Brief** = `docs/work-packages/WP-NN.md`: goal · files in scope · acceptance criteria · constraints · references (ADR/DECISIONS ids).
- **Author output** = unified diff + rationale + list of assumptions. No prose outside the diff.
- **Reviewer output** = findings table (severity · file:line · issue · fix). Empty table = must say what was checked.
- **Disagreement** between author and reviewer → both positions logged in `docs/reviews/WP-NN.md`; orchestrator decides; decision cited in commit message.
- **Discussion rounds** are capped at 2 per WP; after that the orchestrator rules.

## 5. Risk register — initial (owned by role 7, maintained in `docs/RISKS.md`)

| ID | Risk | L | I | Mitigation |
|---|---|---|---|---|
| R-01 | A model generates or "corrects" religious text | M | **Critical** | Red line 1 in every brief; `verify.py` byte-equality to corpus; lexicon scan; safety auditor on all prose |
| R-02 | Reviewer family (GPT-6) argues to relax safety constraints | **H** (observed) | H | Constraints marked non-negotiable; findings on constraints discarded, technical findings kept |
| R-03 | Rate-limit 429 corrupts a batch | M | M | Shared semaphore 18 + backoff; idempotent batch with resume |
| R-04 | Sandbox dies mid-day | M | H | Commit after every WP; `STATE.md` updated per WP, not per session |
| R-05 | Annex phrases leak into public tree on Oct 4 | L | **Critical** | grep gate (`scripts/leak_gate.sh`) with the forbidden-phrase list from `docs/internal/`; orphan branch |
| R-06 | Model output hallucinated a source/URL | M | H | Role 6 must return URL + quoted excerpt; orchestrator fetches and verifies each |
| R-07 | Upstream data outage (tanzil cert expired today) | **observed** | M | E-013 fallback; corpus cached in `corpus/data/`; sha256 pinned |
| R-08 | Memory > 7.8 GB during index + tests + agents | M | H | Retriever peak ~1 GB; agents are remote (no local RAM); monitor `free -h` |
| R-09 | Oct-4 "fresh repo" loses authorship evidence | L | H | Keep this repo private as rehearsal; new repo gets logically-ordered commits + `AI_USAGE.md` |

## 6. Probe evidence (2026-10-01)

```
claude-opus-5-5   plain/think  200  7.7s / 7.9s  — domain-aware (mawḍūʿ)
claude-fable-5-1  plain/think  200  9.4s / 9.6s  — domain-aware
gpt-6-astra       plain/high/xhigh 200 7.2/8.1/16.7s — argued against the constraint
gpt-6.1-sol       plain/high   200  7.8s / 7.5s  — argued against the constraint
gpt-5.6-luna-max  plain        200  2.4s         — fastest
deep-seek-v4-pro  reasoning    200  3.5s  (250 reasoning tokens)
kimi-k3           reasoning    200  8.5s  (275 reasoning tokens)
grok-4.7          —            200  refused instruction → excluded
```
