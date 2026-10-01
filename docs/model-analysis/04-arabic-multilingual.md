# 04 — Arabic & multilingual capability

## Artificial Analysis Multilingual Index — Arabic (S12 [indep], crawled 2026-10-01)
| Rank | Model | Arabic score |
|---|---|---|
| 1 | Gemini 3.1 Pro Preview | 93 |
| 2 | Gemini 3 Pro Preview (high) | 93 |
| 3 | **Claude Opus 4.6 (max)** | **92** |
| 4 | Gemini 3 Flash | 92 |
| 5 | Claude Opus 4.5 | 91 |

- **Gemini is not available on our proxy** (`/models` lists no Gemini ID) → irrelevant to roster.
- Opus 5.5 / Fable 5.1 / GPT-6 Astra / 6.1 Sol are **not yet in the Arabic index**. Best proxy: Claude Opus lineage scores 91–92, within 1 pt of the leader.
- SWE-bench Multilingual (300 problems, 9 programming languages): Fable 5.1 reported in its system card (S2) — programming languages, not natural languages.

## What Arabic capability means for Basira (and what it does **not**)
- Religious text is **never** produced by a model; it is displayed from Tanzil / OHD / HadeethEnc by ID. Arabic *generation* quality therefore matters only for:
  1. our own UI prose in `messages/ar.json` (audited by role 5, Opus 5.5);
  2. the LLM **extraction** provider on competition day (locating quote spans inside Arabic posts — a recognition task, re-anchored by the server to the original text per ADR-005);
  3. research agents reading Arabic sources (dorar.net, hadeethenc.com).
- For (2) the risk is *missing* a span, not inventing text; the deterministic `rules.py` extractor runs in parallel and the union is taken (ADR-005). Eval category for Arabic dialect/orthography variants is in `eval/cases.yaml` (STATE §2 item 7).

## Verdict
Claude Opus family is the strongest available Arabic performer on independent data (92/93). Use **Opus 5.5** for all Arabic-facing roles (messages audit, extraction provider default on competition day). No model is allowed to *write* religious text regardless of Arabic score.
