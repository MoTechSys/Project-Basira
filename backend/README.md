# backend — Basira API (FastAPI, Python 3.13)

Read `../AGENTS.md` and `../docs/STATE.md` first.

## Setup
```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
python3 ../corpus/fetch.py && .venv/bin/python ../corpus/build_index.py
.venv/bin/ruff check app tests && .venv/bin/mypy && .venv/bin/pytest
```

## Layout (implemented ✅ / planned ⏳)
| Module | Role |
|---|---|
| `app/normalize.py` ✅ | loose + strict Arabic tiers with original spans (ADR-002) |
| `app/store.py` ✅ | in-memory corpus, global token stream, CSR postings |
| `app/match/exact.py` ✅ | full-index phrase matching + strict gate |
| `app/retrieve/index.py` ✅ | BM25 words + char-3grams, RRF fusion |
| `app/match/window.py` ✅ | windowed token-Levenshtein |
| `app/match/diff.py` ✅ | word diff → char ranges |
| `app/extract/rules.py`, `surahs.py` ✅ | deterministic extractor, claimed-source parser, detectors |
| `app/messages.py` ✅ | templates loader + forbidden-lexicon scanner |
| `app/config.py`, `app/schemas.py` ✅ | settings, API models |
| `app/state.py` ⏳ | four-state machine (ADR-003) |
| `app/verify.py` ⏳ | post-validator |
| `app/providers/` ⏳ | `LLMClient`/`VisionClient` + `MockProvider` (ADR-005) |
| `app/pipeline.py`, `app/main.py` ⏳ | orchestration + FastAPI routes |
