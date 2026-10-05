#!/usr/bin/env bash
# One-command setup for a fresh clone. Idempotent; exits non-zero on the first failure.
# Usage: bash scripts/bootstrap.sh   (or: make bootstrap)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== 1/6 fetch + verify corpora (sha256 pinned in corpus/manifest.json)"
python3 corpus/fetch.py
python3 corpus/fetch_translations.py

echo "== 2/6 python venv + dependencies"
[ -d backend/.venv ] || python3 -m venv backend/.venv
backend/.venv/bin/pip install -q --upgrade pip
backend/.venv/bin/pip install -q -e "backend[dev,mcp]"

echo "== 3/6 build index (skipped when up to date)"
if [ ! -f corpus/index/meta.json ] || [ corpus/manifest.json -nt corpus/index/meta.json ] \
   || [ corpus/build_index.py -nt corpus/index/meta.json ]; then
  backend/.venv/bin/python corpus/build_index.py >/dev/null
fi
grep -q '"records_sha256"' corpus/index/meta.json

echo "== 4/6 test fixture (cut from the full index)"
backend/.venv/bin/python corpus/build_fixture.py >/dev/null

echo "== 5/6 quality gates"
( cd backend && .venv/bin/ruff check app tests && .venv/bin/mypy && .venv/bin/pytest -q )

echo "== 6/6 message templates lexicon self-check"
( cd backend && .venv/bin/python -c "
from pathlib import Path; from app.messages import self_check_templates
p = self_check_templates(Path('../messages')); assert not p, p; print('templates clean')" )

echo
echo "BOOTSTRAP OK — run \`make serve\` and open http://localhost:8000 (see README, Quick start)."
