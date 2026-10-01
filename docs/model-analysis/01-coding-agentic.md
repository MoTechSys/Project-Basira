# 01 — Coding & agentic engineering

Sources: S1, S2, S3, S7, S8, S9, S13, S16 (see README §3). **[vendor]** = run by the model's maker; **[indep]** = third party.

## Terminal-Bench 4.0 (multi-step CLI engineering)
| Model | Score | Source |
|---|---|---|
| Claude Opus 5.5 (xhigh) | **66.4%** (SE 2.6) | S1 [vendor] |
| GPT-6 Astra (high) | 57.9% (as reported by OpenAI) / **59%** | S1 / S3 [indep] |
| Claude Fable 5.1 | 55.8% / 52% | S1,S13 [vendor] / S3 [indep] |
| Claude Mythos 5.1 (restricted twin) | 60.9% | S13 |
| Claude Opus 5 | 52.3% / 49% | S1 / S3 |
| GPT-5.6 Sol | 37.3% / 40% | S1 / S3 |

> Note: on AA's independent harness **Astra > Fable 5.1**; on Anthropic's table Opus 5.5 leads both. Opus 5.5 is not yet on AA's public Terminal-Bench run (released 8 days before this doc).

## SWE-bench Pro (1,865 long-horizon repo tasks) — 2026-09-30
| Model | Score |
|---|---|
| **Claude Opus 5.5** | **89.9%** |
| Claude Sonnet 5.5 | 81.3% |
| Claude Fable 5.1 | 81.2% |
| Claude Fable 5 / Mythos 5 | 80.3% |
| Claude Opus 5 | 79.2% |
S7 [indep]. ⚠ S16: OpenAI's July-2026 audit estimates ~30% of the 731-task public split is broken; treat as directional.

## SWE-bench Verified (500 human-validated)
Claude Opus 5 **96%** · Mythos 5 95.5% · Fable 5 95% (S8 [indep]). Saturated at the top; no longer discriminative.

## FrontierCode v1.1 (Main) / CursorBench
| Model | FrontierCode | CursorBench 4.0 | CursorBench 3.2 |
|---|---|---|---|
| Opus 5.5 | **54.4%** | **57.8%** | — |
| GPT-6 Astra | 53.3% | — | — |
| Fable 5.1 | 50.3% | 51.8% | 73.4% |
| Opus 5 | 48.0% | 46.6% | 70.0% |
S1, S13 [vendor].

## BenchLM BenchAlign v5.8 coding lane (aggregated, 144 models)
Fable 5.1 **79.8 (#3)** vs GPT-6 Astra 74.0 (#4) — «intervals overlap» (S9 [indep]). Opus 5.5 not yet placed in this lane at crawl time.

## Artificial Analysis Coding Agent Index
GPT-6 Astra (Codex) **62 = Fable 5.1 (Claude Code) 62** > Opus 5 60 > GPT-5.6 Sol 55 (S3 [indep]). Astra uses ~1/3 of the tokens.

## Real-world anecdotes (vendor, for colour only)
- Opus 5.5: 680k-line migration in <1 day; 200k-line audit in <3 h (Opus 5: >20 h, 2.5× tokens); HAProxy C→Rust 9.5 h vs Fable 5.1 12 h. Deloitte: caught **72% of known bugs in code review at lowest effort** vs Opus 5 56% at high. (S1)
- Fable 5.1: 38-hour unattended ML run (Ramp); 3-day prototype with verification loops (MongoDB). (S13)

## Verdict for Basira
| Need | Pick | Why |
|---|---|---|
| Core backend author (pipeline, API, providers) | **Opus 5.5** | Leads every agentic-coding row it appears in; best bug-catch rate in review; cleanest communication (easier for orchestrator to verify) |
| Parallel independent author (eval, frontend) | **Fable 5.1** | Same tier, independent weights, strongest «stay on plan for hours» record |
| Adversarial reviewer / breaker | **GPT-6 Astra** | Different family; leads ARC-AGI-2 and AA's Terminal-Bench run; finds what Claude misses |
