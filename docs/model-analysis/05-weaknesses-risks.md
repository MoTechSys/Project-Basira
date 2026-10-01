# 05 — Documented weaknesses per model → Basira risk mapping

| Model | Documented weakness | Source | Basira mitigation |
|---|---|---|---|
| **Claude Opus 5.5** | Safeguards may re-route cyber/bio tasks to Opus 4.8 / Opus 5 transparently (lowers reported scores) | S1 | Basira has no cyber/bio content; irrelevant. Monitor `model` field in responses anyway. |
| | «Often suspects it is being evaluated» — Anthropic flags this limits their alignment assessment | S1 | Our gates are deterministic (tests, byte-equality); model self-awareness cannot pass them. |
| | Thinking cannot be disabled → slower, higher output tokens | S1 | Acceptable (owner: cost not a criterion). Budget thinking 16k. |
| | Not yet on Vectara HHEM / AA Arabic index (8 days old) | S10, S12 | Treat vendor grounding claims (16/18) as strong but single-source; keep second-family review. |
| **Claude Fable 5.1** | **Accuracy-driven honesty: hallucinates more than Opus 4.8; «verify its output rather than trust its calibration»** | S10 | Author role only; every artefact reviewed by Astra + tests; never final arbiter of facts. |
| | 0/18 on Anthropic's grounded-report test | S1 | Not used for docs/research facts. |
| | Slowest latency in the Claude family; $10/$50 | S13 | Irrelevant per owner. |
| | Safeguard «zeros» in vendor tables (tasks blocked counted as fail) | S13 | None needed; no blocked domains in Basira. |
| | Audit has «less visibility into very long-context and multi-agent settings» | S13 | Our WPs are bounded (one file set, ≤2 review rounds); orchestrator holds the long context. |
| **GPT-6 Astra** | Hallucination rate 51% at max effort on AA-Omniscience | S3 | Reviewer of code/tests only (ground truth = test suite). |
| | GDPval-AA −45 Elo vs GPT-5.6 Sol; uses 24 turns/task vs 60 for Claude → may under-explore | S3 | Reviewer briefs list explicit checklists so under-exploration cannot skip items. |
| | Presentation-quality Elo dropped vs GPT-5.6 Sol | S3 | Not used for user-facing prose. |
| | **Observed in our probe: argued against a fixed safety constraint** | CAPABILITIES/TEAM | Constraints injected as non-negotiable system text; constraint-related findings discarded, technical findings kept (R-02). |
| **GPT-6.1 Sol** | Released 2026-09-29 — **no independent benchmark yet**; OpenAI rates it «Critical» capability in cybersecurity | S4, S6, S15 | Use only as second GPT-family reviewer / fast test generator; never sole authority. Re-evaluate when AA publishes. |
| **Removed models** | DeepSeek V4 Pro: good Vectara (8.6%) but trails all capability axes; Kimi K2.6 Omniscience 6.4; Grok refused benign brief; flash/mini/nano/low variants by definition not «strongest» | S10, probe | Removed per D-009. |

## Cross-cutting risks (feed `docs/RISKS.md`)
| ID | Risk | Mitigation |
|---|---|---|
| R-10 | Vendor benchmarks flatter the vendor (Anthropic vs AA disagree on Terminal-Bench order) | Both numbers recorded; roster choices rest on *multiple* axes, never one table |
| R-11 | Newest models lack independent hallucination data | Second-family review mandatory; research claims fetched and verified |
| R-12 | Benchmark CIs overlap at the top (BenchLM) | Treat ±3 pts as a tie; decide by *task fit* (grounding, Arabic, safety) |
| R-13 | A single family (Claude) holds 3 of 5 roles → correlated blind spots | Astra + 6.1 Sol review every artefact; test suite is family-agnostic ground truth |
