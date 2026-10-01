# 06 — Roster decision (supersedes TEAM.md §2 of 2026-10-01 morning; D-009)

**Rule:** strongest model per task, maximum reasoning, no cost criterion, family diversity on every verdict, weak models removed.

| # | Role | Model ID (verified live) | Reasoning setting | Evidence for choice |
|---|---|---|---|---|
| 0 | Orchestrator / lead engineer | Claude (this session) | — | Holds repo, owner decisions, merges; only one who runs gates |
| 1 | **Chief architect & core author** (`providers/`, `pipeline.py`, `main.py`) | `claude-opus-5-5` | thinking, budget 16k | #1 Terminal-Bench 4.0 (66.4%), #1 SWE-bench Pro (89.9%), #1 FrontierCode, 72% bug catch in review, best alignment audit, 16/18 grounded reports — S1, S7 |
| 2 | **Second author, parallel track** (`eval/`, `frontend/`) | `claude-fable-5-1` | thinking, budget 16k | Tied #1 AA Intelligence Index; #3/144 BenchLM coding lane; strongest unattended-run record — S3, S9, S13 |
| 3 | **Adversarial reviewer** (every diff) | `gpt-6-astra` | `reasoning_effort: xhigh` | Different family; #1 ARC-AGI-2; leads AA's independent Terminal-Bench run; lowest tokens/task — S3, S9. Constraints injected as fixed (R-02) |
| 4 | **Test engineer / breaker** (`backend/tests/`, fixture index, property tests) | `gpt-6.1-sol` | `reasoning_effort: xhigh` | GPT family (diversity); OpenAI: «comparable to Astra, unmatched speed» — S6, S15. ⚠ no independent data yet → paired with Astra on anything non-trivial |
| 5 | **Sharia-safety & messages auditor** (`messages/*.json`, `SAFETY.md`, all user-facing strings) | `claude-opus-5-5` (fresh context) | thinking 16k | Only model with evidence of near-zero invention under strict grading (16/18 vs 0/18); Claude Opus lineage #3 Arabic (92) — S1, S12 |
| 6 | **Research & sources analyst** (`docs/research/`) | `claude-opus-5-5` | thinking 16k | Grounded-report evidence; every claim must return URL+excerpt, orchestrator fetches to confirm |
| 7 | **Risk officer** (`docs/RISKS.md`) | `gpt-6-astra` (fresh context) | xhigh | Different family from authors; strongest pure reasoning for failure-mode enumeration |
| 8 | **Delivery-docs writer** (`README`, `API.md`, `ARCHITECTURE.md`, `AI_USAGE.md`, `CHANGELOG`) | `claude-opus-5-5` | thinking 8k | «Writes clearer, puts key info first, follows writing rules» — S1; passes role 5 before merge |
| 9 | **Eval-case generator** (150 cases + 500 false-alarm segments) | `claude-fable-5-1` | thinking 8k | Domain-aware Claude at top tier; outputs validated against corpus **by code**, never by a model |

**Removed (D-009):** `claude-sonnet-5-5`, `gpt-5.6-luna-max`, `deep-seek-v4-pro`, `kimi-k3`, `grok-4.7`, all flash/mini/nano/low variants.

## Concurrency lanes (cap 20/user; soft 18)
| Lane | Slots |
|---|---|
| Authors (1, 2) | 4 |
| Reviewers (3, 4, 7) | 6 |
| Auditor + research + docs (5, 6, 8) | 4 |
| Eval batch (9) | 4 |
| **Total** | **18** |

## Protocol (unchanged from TEAM.md §4)
brief → author → self-check → **reviewer of other family** → test engineer → safety auditor (if user-facing) → orchestrator gates (`ruff · mypy --strict · pytest · smoke`) → commit → merge `main` → verify. Max 2 debate rounds; orchestrator rules; decision cited in commit.
