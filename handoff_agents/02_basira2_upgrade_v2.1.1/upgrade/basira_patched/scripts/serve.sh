#!/usr/bin/env bash
# Start the Basira backend. In a Genspark sandbox the platform LLM proxy keys are present, so the
# REAL vision/LLM providers are used automatically; elsewhere it falls back to the offline mocks.
set -euo pipefail
cd "$(dirname "$0")/../backend"
if [[ -n "${OPENAI_API_KEY:-}" && -n "${OPENAI_BASE_URL:-}" ]]; then
  export LLM_PROVIDER="${LLM_PROVIDER:-openai-compatible}" LLM_BASE_URL="${LLM_BASE_URL:-$OPENAI_BASE_URL}" LLM_API_KEY="${LLM_API_KEY:-$OPENAI_API_KEY}"
  export LLM_MODEL="${LLM_MODEL:-gpt-5.4}" VISION_PROVIDER="${VISION_PROVIDER:-openai-compatible}" VISION_MODEL="${VISION_MODEL:-gpt-5.4}"
  echo "providers: openai-compatible ($LLM_MODEL) via $LLM_BASE_URL"
else
  echo "providers: mock (no OPENAI_API_KEY/OPENAI_BASE_URL in env)"
fi
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --log-level warning
