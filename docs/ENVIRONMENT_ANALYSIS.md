# Project Basira — Environment & Capabilities Analysis

> **Document ID:** BASIRA-DOC-001
> **Version:** 1.0.0
> **Date:** 2026-09-30
> **Status:** Baseline (pre-development)
> **Author:** AI Development Engineer (Genspark Sandbox)
> **Audience:** Software Architects, Reviewers, Project Stakeholders

---

## 1. Purpose

This document is the authoritative baseline of the development environment, tooling, constraints, and AI-assisted capabilities available for **Project Basira**. It was produced by direct, reproducible inspection of the sandbox (every claim below was verified by command execution on 2026-09-30) and is intended to:

1. Give reviewers full transparency on *where* and *how* the software will be built.
2. Drive technology-stack decisions grounded in what is actually available.
3. Record known limitations and the mitigation plan for each.
4. Serve as an onboarding artifact for any engineer joining the project.

---

## 2. Executive Summary

| Area | Verdict |
|---|---|
| Compute (4 vCPU / 7.8 GiB RAM / 20 GB free disk) | ✅ Sufficient for full-stack development, testing, and CI-like workflows |
| Runtimes (Node 22 LTS, Python 3.13, Java 21 JRE, GCC 14) | ✅ Modern, production-grade versions |
| Package registries (npm, PyPI, Debian apt) | ✅ Reachable, fast (<2 s typical installs) |
| Source control (git 2.47 + GitHub CLI authenticated as `MoTechSys`) | ✅ Full PR workflow possible |
| Deployment (Cloudflare Wrangler 4.x + Genspark Hosted Deploy) | ✅ Edge deployment path available |
| Public preview of running services | ✅ Verified HTTP 200 via sandbox tunnel |
| Local database servers (PostgreSQL/MySQL/Redis/Mongo) | ⚠️ Not pre-installed — installable via `apt` (passwordless sudo) or replaceable by SQLite / Cloudflare D1 |
| Containers (Docker/Kubernetes) | ❌ Not available — use PM2 / systemd-style process management instead |
| Sandbox persistence | ⚠️ Ephemeral filesystem — **all work must be committed and pushed frequently** |

**Conclusion:** The environment is fully capable of delivering an enterprise-grade application. The primary risk is sandbox ephemerality, mitigated by a strict commit-and-push discipline (see §9).

---

## 3. Host & Operating System

| Property | Value |
|---|---|
| Distribution | Debian GNU/Linux 13 (trixie) |
| Kernel | Linux 6.1.155 x86_64 (SMP, PREEMPT_DYNAMIC) |
| Hostname | `sandbox.local` |
| Init system | systemd 257 |
| Shell | `/bin/bash` |
| User | `user` (uid 1000, gid 1000) |
| Privilege escalation | Passwordless `sudo` ✅ |
| Locale/Time | UTC |

### 3.1 Compute Resources

| Resource | Value | Notes |
|---|---|---|
| CPU | 4 × Intel Xeon @ 2.50 GHz (2 threads/core) | Adequate for parallel test runs and bundling |
| RAM | 7.8 GiB total, ~7.5 GiB available | Swap: 127 MiB only — avoid memory-heavy processes (e.g. large in-memory DBs) |
| Root disk | 29 GB total, **20 GB free** (30 % used) | Sufficient for `node_modules` + build artifacts |
| `/tmp` | tmpfs 3.9 GB | RAM-backed, fast, volatile |
| Open-file limit | 1024 (soft) | Raise with `ulimit -n 65536` for file-watchers (Vite/Nodemon) |
| Max user processes | 31 837 | — |

### 3.2 Filesystem Layout & Constraints

| Path | Purpose | Persistence |
|---|---|---|
| `/home/user/webapp` | **Sole permitted write location for project code** | Persisted only via `git push` |
| `/home/user/node_modules` | Pre-seeded global-ish Node modules (`docx`, `jszip`, `nanoid`, `xml-js`, …) via `NODE_PATH` | Sandbox lifetime |
| `/mnt/aidrive` | ⚠️ **Corrected 2026-10-01:** in this sandbox it is an *empty root-owned local directory, not a mount* — files copied here are lost with the sandbox. The real AI Drive is reached via `gsk aidrive upload --local_file` (see `scripts/backup_to_aidrive.sh`) | Persistent **only via gsk** |
| `$HOME/sb-git-refs/` | Sanctioned clone location for SB-Git reference repos | Sandbox lifetime |
| `/tmp` | Scratch space | Volatile |

> ⚠️ **Rule:** Never perform recursive operations (`find`, `cp -r`) on `/mnt/aidrive`. Package to a `.tar.gz` first.

---

## 4. Language Runtimes & Toolchains

### 4.1 Installed (verified)

| Tool | Version | Assessment |
|---|---|---|
| **Node.js** | v22.23.2 (Active LTS) | Primary backend/frontend runtime |
| npm | 10.9.8 | Default package manager |
| npx | 10.9.8 | — |
| corepack | 0.34.6 | Enables `pnpm` / `yarn` on demand (`corepack enable`) |
| **Python** | 3.13.14 (CPython) | Scripting, data processing, tests, alt. backend |
| pip | 26.1.2 | 239 packages pre-installed |
| **Java** | OpenJDK 21.0.12.1 (JRE only — no `javac`) | Runtime only; not a build target without installing JDK |
| **GCC / G++** | 14.2.0 | Native addons / compiled dependencies |
| GNU Make | 4.4.1 | Task automation |
| Perl | present | System scripting |

### 4.2 Not installed (installable if the architecture requires)

| Tool | Install path | Est. time |
|---|---|---|
| TypeScript (`tsc`) | `npm i -D typescript` per project | seconds |
| pnpm / yarn | `corepack enable && corepack prepare pnpm@latest --activate` | seconds |
| Bun / Deno | official install scripts | ~30 s |
| Go | `sudo apt-get install golang` or official tarball | ~1 min |
| Rust | `rustup` | ~2 min |
| PHP / Ruby / .NET | `apt` | ~1 min |
| JDK (`javac`) / Maven / Gradle | `sudo apt-get install openjdk-21-jdk maven` | ~2 min |
| CMake / Clang | `apt` | ~1 min |

### 4.3 Notable Pre-installed Python Packages

`aiohttp 3.14`, `beautifulsoup4 4.15`, `httpx 0.28`, `Jinja2 3.1`, `numpy 2.3`, `pandas 2.2`, `pillow 12.3`, `pydantic 2.13`, `pypdf 6.19`, `pytest 9.0`, `requests 2.33`, `rich 15`, `typer 0.27`, `markitdown 0.1.7`.

Not present (install on demand): `fastapi`, `uvicorn`, `flask`, `django`, `sqlalchemy`, `playwright`, `black`, `ruff`, `mypy`, `supervisor`.

### 4.4 Global npm Packages

| Package | Version | Role |
|---|---|---|
| `wrangler` | 4.134.0 | Cloudflare Workers/Pages/D1/R2 CLI |
| `pm2` | 7.0.4 | Node process manager (daemonization, logs, restarts) |
| `@genspark/cli` (`gsk`) | 1.13.0 | Genspark platform CLI (hosted deploy, search, crawl, upload) |
| `@anthropic-ai/claude-code` | 2.1.274 | Agentic coding CLI |

---

## 5. Data & Storage Options

| Option | Status | Recommended use |
|---|---|---|
| **SQLite** (via `better-sqlite3` / Python `sqlite3` module) | ✅ Python stdlib has it; Node needs npm package | Local dev, tests, embedded data |
| **Cloudflare D1** (SQLite at the edge) | ✅ via Wrangler / `gsk hosted_*` | Production relational DB for edge deployments |
| **Cloudflare R2** | ✅ via Wrangler / `gsk hosted_*` | Object/file storage |
| **Cloudflare KV** | ✅ via Wrangler | Config/cache/sessions |
| PostgreSQL / MySQL / Redis / MongoDB servers | ❌ Not installed | Installable via `apt` for local dev; production should use managed/cloud DBs |
| `sqlite3` CLI | ❌ Not installed | `sudo apt-get install sqlite3` (seconds) |

---

## 6. Networking, Connectivity & Deployment

### 6.1 Outbound Connectivity (verified)

| Endpoint | HTTP | Latency |
|---|---|---|
| registry.npmjs.org | 200 | 0.15 s |
| pypi.org | 301→200 | 0.07 s |
| github.com / api.github.com | 200 | 0.2–0.4 s |
| deb.debian.org | 200 | 0.06 s |
| api.cloudflare.com | 301→200 | 0.06 s |

Install benchmarks: `npm install hono` ≈ **1.5 s**; `pip install fastapi uvicorn` ≈ **3.2 s**; `apt-get update` ✅ works.

### 6.2 Inbound / Preview

- Any HTTP service bound to `0.0.0.0:<port>` can be exposed publicly through the sandbox tunnel.
- **Verified:** probe server on port 8787 → `https://8787-<sandbox-id>.sandbox.novita.ai` returned **HTTP 200**.
- Currently listening: SSH (22) and one sandbox-internal port (49983). All common app ports (3000, 5173, 8000, 8080, 8787) are free.

### 6.3 Deployment Paths

| Path | Mechanism | When to use |
|---|---|---|
| **Genspark Hosted Deploy** | `gsk hosted_*` → Workers for Platforms, D1, R2, custom domains, route-level access rules | Default for production; no user Cloudflare token needed |
| **Cloudflare BYOK** | `wrangler pages deploy` with user's API token | When the client owns the Cloudflare account |
| **Static/Pages** | `wrangler pages` | Pure static frontends |
| **GitHub** | `gh` CLI, authenticated as **`MoTechSys`** | Source of truth, PRs, CI (GitHub Actions) |

### 6.4 Source Control State

| Property | Value |
|---|---|
| Remote | `https://github.com/MoTechSys/Project-Basira.git` |
| Visibility | Public |
| Created | 2026-09-30 05:04 UTC |
| Local state at analysis time | Branch `main`, **0 commits**, empty working tree |
| Working branch (policy) | `genspark_ai_developer` → PR → `main` |

---

## 7. Process & Service Management

| Tool | Status | Notes |
|---|---|---|
| PM2 7.0.4 | ✅ | Recommended for Node services: `pm2 start ecosystem.config.cjs`, `pm2 logs --nostream` |
| systemd 257 | ✅ present | User-level units possible, but PM2 is simpler in-sandbox |
| Supervisor | ❌ | `pip install supervisor` if a Python daemon manager is needed |
| Background execution | ✅ | Tool-level `run_in_background` for dev servers |
| Docker / Compose / kubectl | ❌ | **Not available.** Containerization deferred to CI/production; local dev uses native processes |
| tmux / screen | ❌ | Not needed given PM2 + background execution |

---

## 8. AI-Assisted Capability Inventory

Beyond the shell, the engineer has direct access to the following capability classes. These are used to accelerate research, quality assurance, and asset production.

### 8.1 Engineering & Files
- Structured file operations (read / write / precise multi-edit / glob / regex search).
- Persistent bash with background processes and output streaming.
- Jupyter notebook read/edit.
- Task tracking (todo lists) for auditable progress.
- Git credential setup for GitHub, PR creation via `gh`.

### 8.2 Quality Assurance
- **Playwright console capture**: load any URL (local or public) in a headless browser and collect console errors/warnings — used for frontend smoke tests.
- `pytest` (Python) available; Node test runners installable (Vitest/Jest).
- Public service URL generation for manual/E2E verification.

### 8.3 Research & Web
- Web search, page crawling (HTML/PDF/Office → Markdown), long-document Q&A.
- Access to project SB-Git knowledge repositories.

### 8.4 Media & Content (on request, credit-consuming)
- Image search (Creative-Commons filtered), image generation/editing, background removal, upscaling.
- Video generation, audio/TTS/music generation, transcription, media analysis.
- Local toolchain: **FFmpeg 7.1**, **ImageMagick 7.1**, `pdftotext 25.03`, `markitdown`.

### 8.5 Platform / Hosting
- Genspark Hosted Deploy (Workers, D1, R2, custom domains).
- Route-level access rules (public / authenticated / allow-list / org members) enforced at the platform dispatcher — never in application JS.
- Hosted identity helper (signed-in Genspark visitor headers).
- Cloudflare BYOK deploy skill.

### 8.6 Skills Registered
`cf-byok-deploy`, `designer-handoff`, `gsk-hosted-deploy`, `gsk-hosted-identity` (activated on demand; `/mnt/skills` is materialized at activation time).

---

## 9. Constraints, Risks & Mitigations

| # | Constraint / Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | Sandbox filesystem is ephemeral; may reset | Loss of uncommitted work | Commit after every change; push; merge to `main` and verify |
| R2 | Writes restricted to `/home/user/webapp` | Tooling must be project-local | Use project-local `node_modules`, `.venv`, config files |
| R3 | No Docker | Cannot run containerized DBs locally | Use SQLite/D1 locally; document production DB via IaC/CI |
| R4 | Only 127 MiB swap | OOM risk for heavy builds | Limit parallelism; avoid in-memory DB servers; monitor `free -h` |
| R5 | Default `ulimit -n 1024` | File-watcher failures with large trees | `ulimit -n 65536` in dev scripts |
| R6 | Java is JRE-only | Cannot compile Java | Install JDK only if Java is chosen (not planned) |
| R7 | Each Bash call starts in `/home/user` | Wrong-directory mistakes | Prefix every command with `cd /home/user/webapp &&` |
| R8 | AI Drive is slow | Backups may stall | Single `.tar.gz` archive only, named `basira_backup_YYYY-MM-DD.tar.gz` |
| R9 | Public repository | Secrets exposure | Never commit `.env`/tokens; `.gitignore` from day one; use Wrangler secrets / GitHub secrets |

---

## 10. Recommended Baseline Stack (derived from this analysis)

> Final selection is subject to the product requirements in the next phase; this is the environment-optimal default.

| Layer | Recommendation | Rationale |
|---|---|---|
| Language | **TypeScript** (strict) on Node 22 | Type safety, single language across stack, LTS runtime present |
| Backend | **Hono** (edge-native) on Cloudflare Workers, or **Fastify/NestJS** if a long-running Node server is required | Deploys through the verified Wrangler/Hosted path; sub-2 s installs |
| Database | **Cloudflare D1** (prod) + **SQLite** (local/tests) via **Drizzle ORM** | Same SQL dialect in both environments; migrations versioned in git |
| Frontend | **Vite + React 19 + TypeScript**, TailwindCSS | Fast HMR, mature ecosystem, static output deployable to Pages |
| Validation | **Zod** | Shared schemas between client and server |
| Testing | **Vitest** (unit/integration) + **Playwright** (E2E) | Native TS, fast; Playwright console capture is available |
| Quality gates | ESLint (flat config) + Prettier + `tsc --noEmit` + Husky/lint-staged | Enforced pre-commit and in CI |
| CI/CD | **GitHub Actions** (lint → typecheck → test → build → deploy) | Repo already on GitHub, `gh` authenticated |
| Process mgmt (dev) | **PM2** ecosystem file | Pre-installed |
| Docs | ADRs in `docs/adr/`, OpenAPI spec for the API, C4 diagrams (Mermaid) | Reviewer-friendly, versioned |
| Security | OWASP ASVS-aligned checklist, secret scanning, dependency audit (`npm audit`, Dependabot) | Public repo hygiene |

---

## 11. Engineering Standards Committed To

1. **Conventional Commits** (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `ci:`).
2. **Branch model:** `genspark_ai_developer` → verified → merged directly into `main` by the AI engineer (owner policy: no PR review cycle); rebase on `origin/main` first; squash to one meaningful commit; conflicts resolved favouring remote.
3. **Definition of Done:** lint ✅, typecheck ✅, tests ✅, docs updated ✅, merged to `main` and post-merge verified ✅.
4. **12-Factor configuration:** environment variables only; `.env.example` committed, `.env` ignored.
5. **Architecture Decision Records** for every significant technical choice.
6. **Semantic Versioning** and a maintained `CHANGELOG.md`.
7. **Accessibility & i18n** first-class (Arabic RTL + English LTR) where a UI exists.

---

## 12. Reproducibility

Every fact in this document can be re-verified with:

```bash
cat /etc/os-release; uname -a; nproc; free -h; df -h /
node -v; npm -v; python3 --version; pip --version; java -version; gcc --version
npm ls -g --depth=0; pip list
git --version; gh auth status; wrangler --version; gsk --version
for u in https://registry.npmjs.org https://pypi.org https://github.com; do curl -s -o /dev/null -w "$u %{http_code}\n" $u; done
```

---

## 13. Next Steps

1. ✅ Environment baseline documented (this file).
2. ⏭ Capture **product requirements** for Basira (scope, users, domain, non-functional requirements).
3. ⏭ Produce **Architecture Overview + ADR-001 (stack selection)** based on §10 and the requirements.
4. ⏭ Scaffold repository skeleton: tooling, CI, quality gates, `README.md`, `CONTRIBUTING.md`, `.gitignore`, `.env.example`.
5. ⏭ Iterative feature delivery with PR-per-increment.

---

*End of document.*
