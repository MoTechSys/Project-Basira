# RISKS.md — Risk register (living; owner role 7 = GPT-6 Astra, maintained by orchestrator)

> Sources of entries: (a) GPT-6 Astra risk officer run 2026-10-01 (reasoning_effort=high, two halves — lesson F12), (b) orchestrator's own observations (`docs/agent/discoveries/`), (c) model-analysis R-10..R-13, TEAM.md R-01..R-09. Every entry needs a detection signal; "no signal" is itself a risk.
> Review cadence: at the end of every session, and before any deploy or public push.

## Part A — AI-team operational risks (Astra, half 1)
**Assumptions:** Supplied model names and `xhigh` support are unverified planning inputs. The 20-request cap spans all agents per user. “Sandbox loss” means reset/expiry. Ratings are one-day planning estimates, not measured frequencies.

| id | risk | likelihood (L/M/H) | impact (L/M/H/Critical) | mitigation | owner role | detection signal |
|---|---|---|---|---|---|---|
| R1 | Context rot [1] | H | H | Pin constraints and corpus contract; require checkpointed handoffs and constraint tests. | Orchestrator lead | Agent contradicts pinned contract. |
| R2 | Conformity: identical bad choices [2] | H | H | Obtain blind proposals before sharing plans; assign independent adversarial review. | Review lead | Agents repeat assumptions without independent evidence. |
| R3 | Hallucinated sources [3] | H | Critical | Resolve allowlisted corpus IDs; display stored bytes only. No religious-text generation or grading; unresolved: “Not found in our sources.” | Corpus steward | Unknown ID or byte mismatch. |
| R4 | Fetched-page prompt injection [4] | H | Critical | Treat pages as untrusted data; never promote instructions; deny page-driven tool calls. | Security lead | Page content changes tool use or policy. |
| R5 | Benchmark overfitting [5] | H | H | Freeze hidden, corpus-backed holdouts; prohibit tuning against them; reserve final evaluation time. | QA lead | Visible-suite gains, holdout regression. |
| R6 | Sandbox loss [6] | M | H | Checkpoint patches and artifacts outside sandbox; rehearse fresh-environment restore. | Platform lead | Missing checkpoint or failed restore. |
| R7 | Rate limits [7] | H | H | Shared per-user semaphore ≤20; bounded queue; jittered retries within deadline; honor provider limits. | Backend lead | In-flight >20, HTTP 429, queue growth. |
| R8 | Origin timeout: HTTP 524 during long `xhigh` calls [8] | H | H | Return job ID promptly; use worker plus polling; enforce deadlines and idempotent retries. | Backend lead | 524 responses; latency approaches proxy timeout. |

### Sources
Exact quotations **UNVERIFIED**: no live retrieval performed.

1. https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents — “Context, therefore, must be treated as a finite resource with diminishing marginal returns.”
2. https://arxiv.org/abs/2310.13548 — “We find that five state-of-the-art AI assistants consistently exhibit sycophancy across four varied free-form text-generation tasks.”
3. https://openai.com/index/introducing-chatgpt/ — “ChatGPT sometimes writes plausible-sounding but incorrect or nonsensical answers.”
4. https://genai.owasp.org/llmrisk/llm01-prompt-injection/ — “A Prompt Injection Vulnerability occurs when user prompts alter the LLM’s behavior or output in unintended ways.”
5. https://scikit-learn.org/stable/common_pitfalls.html — “Test data should never be used to make choices about the model.”
6. https://docs.docker.com/engine/storage/volumes/ — “A volume's contents exist outside the lifecycle of a given container.”
7. https://www.rfc-editor.org/rfc/rfc6585#section-4 — “The 429 status code indicates that the user has sent too many requests in a given amount of time ("rate limiting").”
8. https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-524/ — “Error 524 indicates that Cloudflare successfully connected to the origin web server, but the origin did not provide an HTTP response before the default 120-second Proxy Read Timeout.”

## Part B — Product, confidentiality & delivery risks (Astra, half 2)
**Assumptions:** Oct-4’s year, timezone, and migration rules require confirmation. Named models are supplied tool labels. Ratings are planning estimates, not findings. Controls apply across all agents sharing the 20-concurrent-request/user cap.

| id | risk | likelihood (L/M/H) | impact (L/M/H/Critical) | mitigation | owner role | detection signal |
|---|---|---|---|---|---|---|
| R1 | Confidential organizer material enters public repository [1] | H | Critical | Give agents only approved workspace access; export allowlisted files; require human pre-push review. | Release lead | Unexpected staged files; confidential-content scan hit. |
| R2 | Owner’s contributions and AI assistance misrepresented [2] | M | H | Owner attests actual contributions; disclose orchestrator/sub-agents as tools, not authors; retain third-party attribution. | Project owner | README/submission credits contradict contribution log. |
| R3 | Model generates or alters religious text [3] | H | Critical | Models return IDs only; retrieve corpus bytes deterministically; prohibit model-text streaming; gate release on byte-equality tests. | Backend lead | Displayed religious text differs from corpus entry by ID. |
| R4 | UI wording implies religious judgment [3] | M | Critical | Allowlist citation-status strings, including “Not found in our sources”; review localized, accessible, and exported labels. | UX lead | Unapproved string appears in API/UI/export snapshots. |
| R5 | Compromised dependency or install script [4] | M | Critical | Freeze dependencies today; use hashed Python requirements and npm lockfile installs; inspect lifecycle scripts; require human dependency approval. | Security lead | Hash/lockfile drift; unexpected script or package. |
| R6 | Credentials committed to git [1] | H | Critical | Use placeholder configuration; scan staged files and full history; immediately revoke/rotate exposed credentials. | Security lead | Secret scanner hit or provider exposure alert. |
| R7 | Oct-4 migration imports prohibited history or omits required assets [5] | H | H | Confirm permitted carryover; initialize fresh repository; preserve attribution; compare export manifest; run clean-clone backend/frontend tests. | Release lead | Unexpected commits; missing files; clean-clone checks fail. |
| R8 | Family-reviewer conflicts enable coordinated favoritism [2] | M | H | Require conflict declarations and relative recusal; independently reassign reviews; audit decisions without treating anomalies as proof. | Review coordinator | Undisclosed kinship; assignment conflict; unusual scoring convergence. |

### Sources
Sources support general risk mechanisms; mitigations above are proposed release controls.

1. **UNVERIFIED** — https://git-scm.com/docs/gitignore  
   “Files already tracked by Git are not affected; see the NOTES below for details.”
2. **UNVERIFIED** — https://www.acm.org/code-of-ethics  
   “Be honest and trustworthy.”
3. **UNVERIFIED** — https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf  
   “Confabulation: The production of confidently stated but erroneous or false content (known colloquially as ‘hallucinations’ or ‘fabrications’) by which users may be misled or deceived.”
4. **UNVERIFIED** — https://pip.pypa.io/en/stable/topics/secure-installs/  
   “By default, pip does not perform any checks to protect against remote tampering and involves running arbitrary code from distributions.”
5. **UNVERIFIED** — https://git-scm.com/docs/git-init  
   “An initial branch without any commits will be created (see the --initial-branch option below for its name).”

## Part C — Orchestrator-observed (verified by experiment)
| id | risk | L | I | detection | mitigation | owner |
|---|---|---|---|---|---|---|
| R-O1 | tanzil.net TLS expired → bootstrap fails | observed | M | `CERTIFICATE_VERIFY_FAILED` in step 1/5 | E-013 pinned-sha fallback; `--strict-tls` for CI | orchestrator |
| R-O2 | Astra `xhigh` on long brief → HTTP 524 (origin timeout ~120s) | observed ×2 | M | 524 in `AgentResult.error` | split briefs; use `high` for long reviews; treat 524 like 429 (retry) — STATE #13 | orchestrator |
| R-O3 | parallel same-role outputs overwrite | observed | M | fewer files than jobs in `.scratch/agents/<run>/` | `label=role-NN` (fixed 2026-10-01) | orchestrator |
| R-O4 | model self-misidentifies | observed (E11) | L | model names a different version | never ask; use `response.model` / platform UI | all |
| R-O5 | reviewer argues against red lines | observed (E6) | H | review text debates constraint | constraints non-negotiable; discard constraint-findings | orchestrator |
