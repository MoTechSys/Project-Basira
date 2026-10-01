# تحليل النماذج العالمية — Global Frontier Model Analysis

> **Document ID:** BASIRA-MA-000 · **Date:** 2026-10-01 · **Owner directive:** D-009 («الأقوى فقط؛ الضعيف يُحذف؛ الأرصدة لا تهم؛ بحث موثّق بالمصادر»)
> **Method:** every figure below is quoted from a named primary or independent source with URL; vendor-reported numbers are marked **[vendor]**, independent ones **[indep]**. Where sources disagree, both are shown. Nothing is estimated by us.
> **Live availability** of every model ID was verified from this sandbox on 2026-10-01 (`CAPABILITIES.md`).

## Files
| File | Content |
|---|---|
| `README.md` (this) | Executive verdict, roster decision, sources index |
| `01-coding-agentic.md` | Coding / agentic-engineering benchmarks (Terminal-Bench 4.0, SWE-bench Pro/Verified, FrontierCode, CursorBench) |
| `02-hallucination-honesty.md` | Factuality / hallucination (AA-Omniscience, Vectara HHEM) — **the decisive axis for Basira** |
| `03-reasoning-knowledge.md` | HLE, GDPval-AA, ARC-AGI, Intelligence Index |
| `04-arabic-multilingual.md` | Arabic-language capability |
| `05-weaknesses-risks.md` | Documented weaknesses per model and how they map to Basira risks |
| `06-roster-decision.md` | Final role→model binding with evidence citations |

---

## 1. Executive verdict (2026-10-01)

| Axis | #1 | #2 | #3 | Decisive source |
|---|---|---|---|---|
| **Agentic coding (Terminal-Bench 4.0)** | **Claude Opus 5.5** 66.4% | GPT-6 Astra 57.9% | Claude Fable 5.1 55.8% | Anthropic launch table [vendor]; AA independent: Astra 59% > Fable 5.1 52% [indep] |
| **SWE-bench Pro** | **Claude Opus 5.5** 89.9% | Claude Sonnet 5.5 81.3% | Claude Fable 5.1 81.2% | BenchLM 2026-09-30 [indep] — ⚠ OpenAI audit: ~30% of public tasks broken |
| **SWE-bench Verified** | Claude Opus 5 96% | Claude Mythos 5 95.5% | Claude Fable 5 95% | BenchLM [indep] |
| **Coding (BenchLM BenchAlign lane)** | Claude Fable 5.1 79.8 (#3/144) | GPT-6 Astra 74.0 (#4/144) | — | BenchLM compare page [indep]; intervals overlap |
| **Knowledge work (GDPval-AA v2.1 Elo)** | **Claude Opus 5.5** 1846 | Fable 5.1 1735–1853* | Opus 5 1708–1824* | Anthropic [vendor]; *DataCamp quotes Anthropic's Sept-1 table (Fable 5.1 1853, Opus 5 1824) — version drift between v2 and v2.1 |
| **Intelligence Index (AA)** | GPT-6 Astra 53 **=** Claude Fable 5.1 53 | — | GPT-6 Sol 48 | Artificial Analysis [indep] |
| **Humanity's Last Exam (tools)** | Opus 5.5 67.7% | Fable 5.1 65.6% | Opus 5 63.6% | Anthropic [vendor] |
| **Reasoning (ARC-AGI-2)** | GPT-6 Astra 71.8% | Fable 5.1 65.0% | — | BenchLM [indep] |
| **Hallucination — admits ignorance (AA-Omniscience)** | Claude Fable 5 40.0 (accuracy-driven) | Gemini 3.1 Pro 32.9 | Claude Opus 4.8 27.4 (lowest halluc. 35.9%) | AA via CodingFleet [indep] |
| **Hallucination — source grounding (Vectara HHEM)** | GPT-5.4 Mini 5.5% | DeepSeek V4 Pro 8.6% | GPT-5.5 9.3% | Vectara [indep] — Opus 5.5 / Fable 5.1 / Astra **not yet listed** |
| **Hallucination — GPT-6 Astra** | 51% at max effort (was 92% for GPT-5.6 Sol) | — | — | Artificial Analysis [indep] |
| **Grounded reporting (no invented figures)** | **Opus 5.5: 16/18 reports passed**; Fable 5.1 **0/18**; Opus 5 **0/18** | | | Anthropic internal test [vendor] — highly relevant to Basira |
| **Prompt-injection resistance** | Opus 5.5 **=** Fable 5.1 (lowest success rate) | | | Gray Swan via Anthropic [vendor] |
| **Arabic (AA Multilingual Index)** | Gemini 3.1 Pro 93 | Gemini 3 Pro 93 | **Claude Opus 4.6 92**, Opus 4.5 91 | Artificial Analysis [indep] — newer Claude/GPT not yet indexed; Gemini **not available** on our proxy |
| **Token efficiency** | GPT-6 Astra 27k tokens/task vs Fable 5.1 78k | | | Artificial Analysis [indep] |

### Reading
1. **Claude Opus 5.5 (released 2026-09-22) is the strongest model available to us on the axes Basira needs most**: agentic coding, long codebase audits, *grounded* knowledge work (16/18 vs 0/18), and alignment/safety (best automated behavioral audit of any Claude; 85% fewer boundary-crossing attempts; thinking cannot be disabled). Anthropic itself says the real-world gap to Fable 5.1 is «narrower than the scores suggest» — but it is never *behind*.
2. **Claude Fable 5.1 (2026-09-01)** is the top-tier «unattended multi-hour agent» model; equal to Astra on AA Intelligence Index; leads BenchLM coding lane. Documented weakness (Fable 5 lineage): **accuracy-driven honesty — hallucinates more than Opus 4.8; «verify its output rather than trust its calibration»** (CodingFleet/AA). For Basira this means Fable is excellent as a **second independent author**, not as the final arbiter of facts.
3. **GPT-6 Astra (2026-09-03)** ties Fable 5.1 on intelligence at 1/3 the tokens, **leads reasoning (ARC-AGI-2) and Terminal-Bench on AA's independent run**, and halved OpenAI's hallucination rate (92→51%). Weakness: GDPval-AA dropped ~45 Elo vs GPT-5.6 Sol (uses far fewer turns — may under-explore); in our own probe it **argued against a fixed safety constraint**. Ideal **adversarial reviewer / test breaker**, with constraints injected as non-negotiable.
4. **GPT-6.1 Sol (2026-09-29, two days old)** — OpenAI: «comparable to GPT-6 Astra, unmatched speed»; AA release page exists but index not yet published. **Too new for independent evidence** → used only where speed matters and a reviewer from the GPT family is wanted; never as sole authority.
5. **Models removed from the team (D-009):** `deep-seek-v4-pro`, `kimi-k3`, `gpt-5.6-luna-max`, `claude-sonnet-5-5`, `grok-4.7`, and every flash/mini/nano/low variant. Reason: not top-3 on any axis above, or (Grok) refused a benign brief in probe. DeepSeek V4 Pro's good Vectara score (8.6%) is noted but it trails on every capability axis; the owner's directive is «strongest only».

## 2. Caveats we must carry (anti-hallucination discipline)
- Vendor launch tables are run by the vendor with their own harness; AA's independent Terminal-Bench run ranks Astra above Fable 5.1, the reverse of Anthropic's table for Opus 5.5 — **both are in the file**.
- SWE-bench Pro public split is ~30% broken per OpenAI's July-2026 audit; BenchLM itself says «do not decide a purchase on this alone».
- Benchmark intervals overlap at the top (BenchLM 90% CI). Differences of a few points are «directional».
- Newest models (Opus 5.5, Fable 5.1, Astra, 6.1 Sol) are **not yet on Vectara HHEM**; their grounding numbers come from vendor tests or AA-Omniscience only.
- Arabic index does not yet include the Sept-2026 models; Claude Opus 4.6 at 92 is our best proxy for Claude's Arabic strength.
- «Reasoning tax»: reasoning modes raise hallucination 2–3× on *summarization* tasks (CodingFleet). Basira never asks a model to summarize religious text, so this applies to our **docs/research** roles, not to code roles → research outputs are verified by fetching the cited URL.

## 3. Sources index
| # | Source | Type | URL |
|---|---|---|---|
| S1 | Anthropic — Introducing Claude Opus 5.5 (2026-09-22) | vendor | https://www.anthropic.com/claude-opus-5-5 |
| S2 | Anthropic — Fable 5.1 & Mythos 5.1 System Card (2026-09-01) | vendor | https://www-cdn.anthropic.com/0339e6a7c5c7b87f5c07798616dc32c215d14235/Claude%20Fable%205.1%20&%20Claude%20Mythos%205.1%20System%20Card.pdf |
| S3 | Artificial Analysis — Benchmarking GPT-6 Astra (2026-09-09) | indep | https://artificialanalysis.ai/articles/benchmarking-gpt-6-astra |
| S4 | Artificial Analysis — GPT-6.1 Sol release page | indep | https://artificialanalysis.ai/models/releases/gpt-6-1-sol |
| S5 | OpenAI — GPT-6 Astra announcement | vendor | https://openai.com/index/gpt-6-astra/ |
| S6 | OpenAI — GPT-6.1 Sol system-card addendum | vendor | https://deploymentsafety.openai.com/gpt-6-1-sol |
| S7 | BenchLM — SWE-bench Pro leaderboard (2026-09-30) | indep | https://benchlm.ai/benchmarks/swe-bench-pro |
| S8 | BenchLM — SWE-bench Verified leaderboard | indep | https://benchlm.ai/benchmarks/swe-bench-verified |
| S9 | BenchLM — Fable 5.1 vs GPT-6 Astra compare (2026-09-30) | indep | https://benchlm.ai/compare/claude-fable-5-1-vs-gpt-6-astra |
| S10 | CodingFleet — AI Model Hallucination Rates 2026 (Vectara + AA data) | indep (secondary) | https://codingfleet.com/blog/ai-model-hallucination-rates-2026/ |
| S11 | Vectara HHEM leaderboard | indep | https://github.com/vectara/hallucination-leaderboard |
| S12 | Artificial Analysis — Arabic multilingual index | indep | https://artificialanalysis.ai/models/multilingual/arabic |
| S13 | DataCamp — Claude Fable 5.1 features/benchmarks (2026-09-02) | secondary | https://www.datacamp.com/blog/claude-fable-5-1 |
| S14 | VentureBeat — Opus 5.5 release (2026-09-22) | press | https://venturebeat.com/technology/anthropic-releases-claude-opus-5-5-beating-fable-5-1-on-key-agentic-benchmarks-at-60-cheaper-api-price |
| S15 | TechCrunch — GPT-6.1 Sol launch (2026-09-29) | press | https://techcrunch.com/2026/09/29/openai-launches-gpt-6-1-sol-says-it-nearly-matches-gpt-6-astra-and-costs-less/ |
| S16 | OpenAI — coding-evals task-quality audit (July 2026) | vendor | https://openai.com/index/separating-signal-from-noise-coding-evaluations/ |
