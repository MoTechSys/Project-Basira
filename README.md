# Project Basira (بصيرة)

> Enterprise-grade software project built to international engineering standards.

**Status:** 🟡 Phase 0 — Environment baseline complete, awaiting product requirements.

## Repository Layout

```
.
├── docs/
│   └── ENVIRONMENT_ANALYSIS.md   # Verified baseline of the dev environment, tooling & constraints
├── .gitignore
└── README.md
```

## Documentation

| Document | Description |
|---|---|
| [docs/ENVIRONMENT_ANALYSIS.md](docs/ENVIRONMENT_ANALYSIS.md) | Full audit of OS, compute, runtimes, package registries, deployment paths, AI-assisted capabilities, risks & mitigations, and the recommended baseline stack |

## Engineering Workflow

- **Branching:** `genspark_ai_developer` → Pull Request → `main`
- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `chore:`, …)
- **Definition of Done:** lint ✅ · typecheck ✅ · tests ✅ · docs ✅ · PR ✅
- **Configuration:** 12-Factor — environment variables only, `.env` never committed

## Roadmap

1. ✅ Environment & capabilities baseline
2. ⏭ Product requirements & scope definition
3. ⏭ Architecture overview + ADR-001 (stack selection)
4. ⏭ Repository scaffold (tooling, CI/CD, quality gates)
5. ⏭ Iterative feature delivery

## License

TBD
