# 02 — Hallucination & honesty (the decisive axis for Basira)

Basira's whole value is **not inventing**. Two independent measures exist and they disagree by design (S10):
- **Vectara HHEM** — does the model stick to the source when summarizing? (lower % = better; <5% excellent, >10% concerning)
- **AA-Omniscience** — does the model admit ignorance instead of fabricating? (higher index = better; >25 excellent)

## AA-Omniscience (June-2026 snapshot via S10; AA primary)
| Model | Index | Accuracy | Hallucination rate |
|---|---|---|---|
| Claude Fable 5 (max) | **40.0** | **61%** | higher than Opus 4.8 (exact not published) — «accuracy-driven, not low-hallucination-driven» |
| Gemini 3.1 Pro | 32.9 | 55.3% | 50% |
| Claude Opus 4.8 (max) | 27.4 | 46.6% | **35.9%** (best calibration) |
| Claude Opus 4.7 | 26.2 | ~47% | 36% |
| GPT-5.5 (xhigh) | 20.1 | 57% | 86% |
| Kimi K2.6 | 6.4 | — | — |

## GPT-6 Astra on AA-Omniscience (S3 [indep])
Hallucination rate **92% → 51%** at max effort vs GPT-5.6 Sol, *with* +4 pts accuracy. Still 51% — far from calibrated.

## Vectara HHEM (S11 via S10; new dataset, answer-rate ≥95%)
| Model | Rate |
|---|---|
| GPT-5.4 Mini | 5.5% |
| DeepSeek V4 Pro | 8.6% |
| GPT-5.5 | 9.3% |
| Claude Haiku 4.5 | 9.8% |
| Claude Sonnet 4.6 | 10.6% |
| Claude Opus 4.7 | 12.0% |
**Not yet listed:** Opus 5.5, Fable 5.1, GPT-6 Astra, GPT-6.1 Sol (all < 6 weeks old).

## Anthropic grounded-report test (S1 [vendor]) — closest proxy to Basira's job
Task: write a quarterly report using only a web copy where the release was hard to find; automated grader checks **every figure and quote**; any invented one = fail.
- **Opus 5.5: 16/18 passed**
- Fable 5.1: **0/18**
- Opus 5: **0/18**

## «Reasoning tax» (S10)
Reasoning modes raise hallucination 2–3× on *summarization*. Does not apply to code generation; **does** apply to research/docs roles → we verify every URL and quote a research agent returns by fetching it.

## Implications for Basira (binding)
1. **No model ever produces religious text.** Display is byte-exact from the corpus (`verify.py`). This axis is about *our own* prose, code comments, docs and research — not about Quran/Hadith.
2. **Opus 5.5 is the only model with evidence of near-zero invention under a strict grader.** It is therefore the **Sharia-safety & messages auditor** and the **final arbiter** when authors disagree.
3. **Fable 5.1 output is always verified, never trusted on calibration** (S10's explicit guidance). Fine as author; never sole reviewer of facts.
4. **GPT-6 Astra** (51% hallucination on knowledge questions) is used for **adversarial review of code and tests**, where the ground truth is the test suite, not the model.
5. **Research agent claims** must carry URL + quoted excerpt; the orchestrator fetches and confirms before anything enters `docs/`.
