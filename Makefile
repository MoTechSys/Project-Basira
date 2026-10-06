# Basira — developer entry points. `make help` lists every target.
# Backend targets use the venv created by `make bootstrap` (backend/.venv).

PY  := backend/.venv/bin/python
BIN := backend/.venv/bin
URL ?= http://localhost:8000

.DEFAULT_GOAL := help
.PHONY: help bootstrap fetch fetch-translations index fixture \
        lint fmt test gates smoke web-install web-lint web-test web-build web-gates \
        serve serve-mcp mcp-demo eval eval-full eval-english eval-english-picker \
        islamiceval islamiceval-1a scholar docker clean bot-install bot-test

help: ## list targets
	@awk 'BEGIN{FS=":.*## "} /^[a-z0-9-]+:.*## /{printf "  \033[1m%-20s\033[0m %s\n",$$1,$$2}' $(MAKEFILE_LIST)

# ---- setup -----------------------------------------------------------------------------------------
bootstrap: ## one command: corpora, venv, index, fixture, gates (idempotent)
	bash scripts/bootstrap.sh
fetch: ## download + sha256-verify the Quran/Hadith corpora (corpus/manifest.json)
	python3 corpus/fetch.py
fetch-translations: ## download + verify the approved translations (English gate)
	python3 corpus/fetch_translations.py
index: ## build corpus/index (records + translations)
	$(PY) corpus/build_index.py
fixture: ## cut the small deterministic test fixture from the full index
	$(PY) corpus/build_fixture.py

# ---- backend quality gates -------------------------------------------------------------------------
lint: ## ruff (check + format) + mypy strict
	cd backend && .venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests && .venv/bin/mypy
	$(BIN)/ruff check --config backend/pyproject.toml corpus eval scripts/smoke.py
fmt: ## apply ruff formatting
	cd backend && .venv/bin/ruff format app tests
test: ## pytest (corpus-backed tests need `make fixture`)
	cd backend && .venv/bin/pytest -q -rs
gates: lint test ## lint + tests
smoke: ## 8 canonical checks against the full corpus, in-process
	$(PY) scripts/smoke.py

# ---- frontend --------------------------------------------------------------------------------------
web-install: ## npm ci
	cd frontend && npm ci
web-lint: ## oxlint + tsc
	cd frontend && npm run lint && npm run typecheck
web-test: ## vitest
	cd frontend && npm test
web-build: ## production bundle → frontend/dist (served by the backend)
	cd frontend && npm run build
web-gates: web-lint web-test web-build ## all frontend gates

# ---- run -------------------------------------------------------------------------------------------
serve: ## backend on :8000 (mock providers unless OPENAI_* are set)
	bash scripts/serve.sh
serve-mcp: ## backend with the MCP server mounted at /mcp
	cd backend && BASIRA_MCP=1 .venv/bin/uvicorn app.main:app --port 8000
mcp-demo: ## call every MCP tool against a running server
	$(PY) scripts/mcp_demo.py
docker: ## build the single production image
	docker build -t basira:local .

# ---- evaluation ------------------------------------------------------------------------------------
eval: ## 150 cases on the fixture, 3 repeats, fail on any unsafe verdict
	$(PY) eval/run_eval.py --repeats 3 --fail-on-unsafe
eval-full: ## 150 cases on the full index + 500 false-alarm segments
	$(PY) eval/run_eval.py --index corpus/index --repeats 3 --false-alarm 500 --fail-on-unsafe
eval-english: ## English gate recall@k
	$(PY) eval/run_english.py --fail-under 0.9
eval-english-picker: ## constrained model picker (needs LLM_* env)
	$(PY) eval/run_english_picker.py --fail-on-wrong $${PICKER_MODELS:+--models $$PICKER_MODELS}
islamiceval: ## IslamicEval 2025 subtask 1B (data cloned into .scratch/islamiceval/)
	$(PY) eval/islamiceval/run_1b.py
islamiceval-1a: ## IslamicEval 2025 subtask 1A (add --llm via ARGS=--llm)
	$(PY) eval/islamiceval/run_1a.py $(ARGS)
scholar: ## scholar-lens probe against a running server (URL=...)
	$(PY) eval/scholar_probe.py $(URL)

clean: ## remove caches and build output (keeps corpora and venv)
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache \) -prune -exec rm -rf {} +
	rm -rf frontend/dist eval/results

# ---- Telegram bot (integrations/telegram) ---------------------------------------------------------
bot-install: ## venv + deps for the Telegram bot
	cd integrations/telegram && python3 -m venv .venv && .venv/bin/pip install -q -e '.[dev]'
bot-test: ## bot gates: ruff + mypy strict + pytest
	cd integrations/telegram && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy --strict . && .venv/bin/pytest -q
