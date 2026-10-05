#!/usr/bin/env bash
# Start the Basira backend for local development.
# If OPENAI_API_KEY and OPENAI_BASE_URL are set (any OpenAI-compatible endpoint), the real LLM and
# vision providers are used; otherwise the deterministic offline mocks are used (ADR-005).
set -euo pipefail
cd "$(dirname "$0")/../backend"
if [[ -n "${OPENAI_API_KEY:-}" && -n "${OPENAI_BASE_URL:-}" ]]; then
  export LLM_PROVIDER="${LLM_PROVIDER:-openai-compatible}" LLM_BASE_URL="${LLM_BASE_URL:-$OPENAI_BASE_URL}" LLM_API_KEY="${LLM_API_KEY:-$OPENAI_API_KEY}"
  export LLM_MODEL="${LLM_MODEL:-gpt-5.4}" VISION_PROVIDER="${VISION_PROVIDER:-openai-compatible}" VISION_MODEL="${VISION_MODEL:-gpt-5.4}"
  # span location is copy-work: "none" cuts gpt-5.4 extraction from ~9-15 s to ~2-3 s with identical spans (E-035)
  export LLM_REASONING_EFFORT="${LLM_REASONING_EFFORT:-none}"
  echo "providers: openai-compatible ($LLM_MODEL, reasoning_effort=$LLM_REASONING_EFFORT) via $LLM_BASE_URL"
else
  echo "providers: mock (no OPENAI_API_KEY/OPENAI_BASE_URL in env)"
fi
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --log-level warning
