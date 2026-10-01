#!/usr/bin/env bash
# One-command restore for a NEW agent / NEW machine. Idempotent. Exits non-zero on any failure.
# Usage: bash scripts/bootstrap.sh
set -euo pipefail
cd "$(dirname "$0")/.."
echo "== 1/5 fetch + verify corpora (sha256, counts)"
python3 corpus/fetch.py
echo "== 2/5 python venv + deps"
[ -d backend/.venv ] || python3 -m venv backend/.venv
backend/.venv/bin/pip install -q --upgrade pip
backend/.venv/bin/pip install -q -e "backend[dev]"
echo "== 3/5 build index (skipped if up to date)"
if [ ! -f corpus/index/meta.json ] || [ corpus/manifest.json -nt corpus/index/meta.json ] || [ corpus/build_index.py -nt corpus/index/meta.json ]; then
  backend/.venv/bin/python corpus/build_index.py >/dev/null
fi
grep -q '"records_sha256"' corpus/index/meta.json
echo "== 4/5 quality gates"
( cd backend && .venv/bin/ruff check app tests && .venv/bin/mypy && .venv/bin/pytest -q )
echo "== 5/5 message templates lexicon self-check"
( cd backend && .venv/bin/python -c "
from pathlib import Path; from app.messages import self_check_templates
p=self_check_templates(Path('../messages')); assert not p, p; print('templates clean')" )
echo
echo "BOOTSTRAP OK — now read docs/STATE.md §2 for the next task."
