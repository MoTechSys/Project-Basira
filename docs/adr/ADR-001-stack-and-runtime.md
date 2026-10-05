# ADR-001 — Stack & runtime

**Status:** Accepted · 2026-09-30

## Context
The product needs a fast, auditable stack for Arabic text processing and a bilingual RTL web UI, with an in-memory corpus index built at deploy time, no database, no accounts and no storage of user input. Everything must also run fully offline for development and evaluation (D-004).

## Decision
- **Backend:** Python 3.13, FastAPI, uvicorn. Index held in process memory, built by `corpus/build_index.py` and loaded at startup. `/health` → 503 until loaded (E-011).
- **Frontend:** React 19 + Vite + TypeScript, RTL/LTR, imports `messages/*.json` at build.
- **Providers:** `LLMClient` / `VisionClient` interfaces; `MockProvider` default (E-008). Real providers are config only.
- **Hosting target (later):** static frontend on Cloudflare Pages, backend on a long-running host (Render). Not part of this repo's dev loop.
- **Quality gates:** ruff + mypy + pytest (backend); eslint + tsc + vitest (frontend); gitleaks.

## Consequences
- No Docker needed locally; `make dev` runs both.
- Memory budget 1.5 GB: postings as numpy int32; char-3gram index for Quran only.
