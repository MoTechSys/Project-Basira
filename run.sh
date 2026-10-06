#!/usr/bin/env bash
# Basira — one command from a fresh clone to a running site on http://localhost:8000
#
#   bash run.sh            native: Python ≥ 3.12 + Node ≥ 20 (first run ~5 min: corpora + index; then seconds)
#   bash run.sh --docker   only Docker needed (builds the production image)
#   bash run.sh --check    install + build + quality gates + smoke, then exit (no server)
#
# No API key is needed: without one Basira runs rules-only and says so (`extraction_degraded`).
# Optional model: copy .env.example to .env and fill LLM_* (README → "API keys and environment variables").
# Idempotent: re-running skips everything that is already up to date.
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8000}"
say() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

if [[ "${1:-}" == "--docker" ]]; then
  command -v docker >/dev/null || die "Docker not found."
  say "building the production image (corpora fetched + verified inside the build)"
  docker build -t basira:local --build-arg BUILD_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo local)" .
  say "Basira on http://localhost:${PORT}  (Ctrl+C to stop)"
  envfile=(); [[ -f .env ]] && envfile=(--env-file .env)
  exec docker run --rm -p "${PORT}:8000" "${envfile[@]}" -e BASIRA_CORS_ORIGINS="http://localhost:${PORT}" basira:local
fi

say "1/5 prerequisites"
command -v python3 >/dev/null || die "python3 not found (need ≥ 3.12)."
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' || die "Python ≥ 3.12 required, found $(python3 -V)."
command -v node >/dev/null || die "node not found (need ≥ 20) — or use: bash run.sh --docker"
command -v npm >/dev/null || die "npm not found."
echo "python $(python3 -V | cut -d' ' -f2) · node $(node -v)"

STAMP=backend/.venv/.basira-ready
if [[ "${1:-}" == "--check" || ! -f "$STAMP" || corpus/manifest.json -nt "$STAMP" || backend/pyproject.toml -nt "$STAMP" ]]; then
  say "2/5 corpora (sha256-verified) + venv + index + backend gates"
  bash scripts/bootstrap.sh
  FIRST=1
else
  say "2/5 already set up (corpora, venv, index) — skipping; \`bash run.sh --check\` re-runs every gate"
  FIRST=0
fi

say "3/5 frontend build"
if [[ ! -f frontend/dist/index.html ]] || [[ -n "$(find frontend/src frontend/index.html frontend/package.json -newer frontend/dist/index.html -print -quit)" ]]; then
  (cd frontend && npm ci --no-audit --no-fund && npm run build)
else
  echo "frontend/dist is up to date"
fi

if [[ "$FIRST" == 1 ]]; then
  say "4/5 smoke test — 8 canonical cases on the real corpus"
  backend/.venv/bin/python scripts/smoke.py
  touch "$STAMP"
fi

if [[ "${1:-}" == "--check" ]]; then say "CHECK OK"; exit 0; fi

say "5/5 Basira on http://localhost:${PORT}  (UI · API /v1 · docs /docs · MCP /mcp — Ctrl+C to stop)"
if [[ -f .env ]]; then set -a; . ./.env; set +a; echo "loaded .env"; fi
cd backend
BASIRA_MCP="${BASIRA_MCP:-1}" BASIRA_CORS_ORIGINS="${BASIRA_CORS_ORIGINS:-http://localhost:${PORT}}" \
  exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --log-level warning
