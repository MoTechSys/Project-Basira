# Project Basira — AI Engineer Operating Rules

These rules are set by the project owner and override any default workflow.

## Ownership & Delivery
- The AI engineer is **fully responsible** for the change lifecycle: implement → verify → commit → push → **merge into `main` directly**.
- **Do NOT open pull requests for review.** The owner does not review PRs; the engineer merges and verifies.
- Every merge into `main` must be followed by a post-merge verification (checkout `main`, pull, run lint/typecheck/tests/build where they exist).

## Quality Bar
- **Confidentiality (challenge terms §15):** nothing derived from non-public organizer material (scientific annex, handbook internals, chat logs, HANDOFF/ANNEX_ALIGNMENT text) may enter the public repository. `.intake/` is git-ignored; `SAFETY.md` and templates are **rewritten**, never copied from the package.
- Target: world-class review by senior software engineers. Zero tolerance for sloppiness.
- When the owner supplies documents/files/explanations: **audit line by line**, record findings (bugs, gaps, risks, inconsistencies), then improve to the highest standard. Never skim.
- Every non-trivial technical decision gets an ADR in `docs/adr/`.
- Definition of Done: lint ✅ · typecheck ✅ · tests ✅ · docs updated ✅ · merged to `main` ✅ · verified ✅.

## Git
- Work on `genspark_ai_developer`, rebase on `origin/main`, squash to one meaningful commit, push, merge to `main` (fast-forward or merge commit), then sync local `main`.
- Conventional Commits. Never commit secrets (`.env`, tokens, keys).
- Commit after every logical change — the sandbox is ephemeral.

## Environment
- All writes inside `/home/user/webapp` only. Every bash command prefixed with `cd /home/user/webapp &&`.
- Baseline of the environment: `docs/ENVIRONMENT_ANALYSIS.md`.

## Repository visibility & publication gate
- Repo is **private during preparation** (terms §15 permits this). It must be **public at delivery** (participant guide).
- `docs/internal/` holds audits, annex triage, and anything derived from non-public organizer material. **It must never be published.**
- Before flipping to public: create the public tree from a clean orphan branch (or filter history) containing only `README`, `SOURCES`, `AI_USAGE`, `SAFETY` (rewritten), `CHANGELOG`, `LICENSE`, `messages/`, `eval/`, `docs/API.md`, `docs/ARCHITECTURE.md`, ADRs — and run a grep gate for annex phrases before the push.
