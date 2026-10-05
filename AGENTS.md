# AGENTS.md — rules for anyone (human or AI-assisted) changing this repository

Read this before the first change. It is short on purpose; the reasons live in the linked documents.

## 1. What Basira is

A deterministic checker for Quran and Hadith quotations. It locates quotations in a text, compares them byte-exactly
with sha256-pinned corpora, and returns one of four states with the verbatim source text. It never grades a hadith,
never issues a ruling, never rewrites the user's text, never generates religious text, and stores nothing.
Overview: `README.md` · architecture: `docs/ARCHITECTURE.md` · contract: `docs/API.md`.

## 2. Red lines (a change that breaks one is rejected, whatever else it improves)

1. **No religious text written by hand or by a model.** Anything shown as Quran or Hadith comes from the corpus by
   record id (`verify.py` V1). Test cases reference records by id and token window (`eval/gen_cases.py`).
2. **No judgement vocabulary** («صحيح / ضعيف / موضوع / محرّف …») in anything Basira authors. All user-facing prose lives
   in `messages/*.json` and `frontend/src/site/strings.ts`; both are scanned (`scripts/check_site_lexicon.py`, V3).
3. **No storage of user input** (ADR-004). No database, no logs of user text.
4. **The state machine decides.** `backend/app/state.py` is the only place a status is assigned. Changing it, or any
   threshold in `config.Thresholds`, requires a new ADR and a re-run of `make eval-full`.
5. **Every number is measured.** A figure in a document cites the command or report that produced it.

## 3. Setup and gates

```bash
make bootstrap        # corpora (sha256-verified) → venv → index → fixture → gates
make gates            # ruff check + format, mypy strict, pytest
make web-install web-gates
make eval-full        # 150 cases + 500 false-alarm segments; must stay 150/150, unsafe 0, 0/500
```

Definition of done: `make gates`, `make web-gates` and `make eval-full` green; documentation updated in the same
change; a `DECISIONS.md` entry for any non-trivial choice.

## 4. Where things go

| Change | Update |
|---|---|
| Behaviour or policy | `docs/DECISIONS.md` (new `D-`/`E-` row; never edit an old decision, supersede it) |
| Architecture | `docs/adr/` |
| New risk or mitigation | `docs/RISKS.md` (name the test that guards it) |
| Release | `CHANGELOG.md` section + `vX.Y.Z` tag (the release workflow publishes it) |
| Status after a release | `docs/STATE.md` |

## 5. Commits

Conventional Commits (`feat(scope): …`, `fix: …`, `docs: …`, `ci: …`). One topic per commit; the body says why and
what was measured. Never commit secrets, `.env`, corpus data or built indexes (all git-ignored).
