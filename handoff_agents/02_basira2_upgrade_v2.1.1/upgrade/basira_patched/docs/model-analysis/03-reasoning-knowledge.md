# 03 — Reasoning & knowledge work

## Artificial Analysis Intelligence Index v4.3.x (10 evals) — S3, S4 [indep]
| Model | Index |
|---|---|
| **GPT-6 Astra (max)** | **53** |
| **Claude Fable 5.1 (max, with fallback)** | **53** |
| GPT-6 Sol | 48 |
| GPT-5.6 Terra | 42 |
| GPT-6 Luna | 38 |
| GPT-6.1 Sol | *index not yet published (released 2026-09-29)* |
| Claude Opus 5.5 | *not yet indexed (released 2026-09-22)* |

Cost per Index task: Astra max $3.26 vs Fable 5.1 $7.63; Astra 27k output tokens/task vs Fable 78k.

## Humanity's Last Exam (with tools) — S1, S13 [vendor]
Opus 5.5 **67.7%** · Fable 5.1 65.6% (65.0% in Sept-1 table) · Opus 5 63.6% · GPT-6 Astra 57.2%.

## GDPval-AA (real work across 44 occupations, Elo)
| Model | v2.1 (S1) | v2 (S13, Sept-1) |
|---|---|---|
| Opus 5.5 | **1846** | — |
| Fable 5.1 | 1735 | 1853 |
| Opus 5 | 1708 | 1824 |
| GPT-5.6 Sol | 1588 | 1711 |
| GPT-6 Astra | 1542 | ~45 Elo below GPT-5.6 Sol (S3) |
Version drift between v2 and v2.1 is visible; relative order Opus 5.5 > Fable 5.1 > Opus 5 > GPT holds in both.

## ARC-AGI (abstract reasoning) — S9 [indep]
ARC-AGI-2: GPT-6 Astra **71.8%** vs Fable 5.1 65.0%. ARC-AGI-1 and -3: Astra leads (ARC-AGI-3 reported 99.9% by MindStudio, vendor-sourced).

## Terminal-Bench-Science 0.1 (agentic research)
GPT-6 Astra **64.6%** · Opus 5.5 58.7% · Fable 5.1 52.6% · Opus 5 29.0% (S1).

## Verdict
- **Pure reasoning / puzzle-class:** GPT-6 Astra.
- **Knowledge work with grounding:** Opus 5.5.
- **Long unattended research/agent runs:** Fable 5.1 (1M ctx, 128k out, 38-h run evidence).
