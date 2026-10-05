# Contributing

Basira is maintained by one person. AI-assisted development is disclosed in `AI_USAGE.md`.
These rules apply to every change, however it was produced.

## Ground rules

1. **Three red lines** (`SAFETY.md` §1): no generated religious text · no judgment vocabulary · no storage.
   Anything that touches them needs an ADR in `docs/adr/` **before** code.
2. **Decisions are not re-litigated.** `docs/DECISIONS.md` is the log of product (D-) and engineering (E-) decisions.
   If you disagree, add a dated note proposing a change; do not silently diverge.
3. **Every user-facing string lives in `messages/{ar,en}.json` or `frontend/src/site/strings.ts`** and passes
   `scripts/check_site_lexicon.py`. Never hard-code prose in components. AR and EN key sets must be identical (tested).
4. **No religious text in tests, examples or fixtures that is not drawn verbatim from the corpus/fixture.**
5. **Numbers are measured.** A number in docs or UI must cite the command/file that produced it.

## Workflow

```bash
bash scripts/bootstrap.sh          # once per machine
make gates && make smoke           # before you start, and before every commit
# …work…
make lint && make test && make smoke && make eval-full && git checkout eval/REPORT.md
cd frontend && npm run typecheck && npm run lint && npm test -- --run && npm run build
```

* Branch from `main`; Conventional Commits (`feat(scope): …`, `fix: …`, `docs: …`, `test: …`, `chore: …`).
* A pull request includes the **pasted terminal output** of every gate; the maintainer **re-runs** them
  then merges `--no-ff` with the measured numbers in the merge message (D-001).
* Stacked branches are rebased with `git rebase --onto origin/main origin/<base> <branch>`.

## Definition of Done

lint ✓ · mypy ✓ · pytest ✓ · smoke ✓ · eval 150/150 · FA 0/500 · frontend tsc/oxlint/vitest/build ✓ ·
lexicon 0 · docs updated (STATE, DECISIONS, and API/ARCHITECTURE where relevant) · merged to `main` ·
post-merge verification run on `main`.

## Code style

* Python 3.12+: ruff (all rules enabled in `backend/pyproject.toml`), mypy strict, dataclasses with `slots`,
  no `Any` leaking from public functions, every module has a docstring explaining *why* it exists.
* TypeScript: strict, no `any`, no router/framework dependencies beyond React, components are small and
  tested with Testing Library.
* Comments explain intent and cite the decision id (`# B12`, `# E-051`). Code that enforces a safety invariant
  cites it (`# I7`).

## Reporting a safety or security issue

See `SECURITY.md`. For a wrong verdict on a specific quotation, open an issue with the `determinism_hash` from the
response — it lets us reproduce the exact run.
