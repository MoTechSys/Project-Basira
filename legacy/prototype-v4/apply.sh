#!/usr/bin/env bash
# Apply Basira v4 onto Project-Basira00 main (base b801da5). Run from the Project-Basira00 repo root.
#   bash /path/to/basira-v4/apply.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
git fetch origin main
git checkout -B v4-ui origin/main
if git am --3way "$HERE"/patch/*.patch; then
  echo "patches applied cleanly"
else
  echo "git am failed — falling back to whole-file copy (base drifted from b801da5)"
  git am --abort || true
  cp -r "$HERE"/files/. .
  git add -A && git commit -m "feat(ui+api): Basira v4 (X-ray, two-phase, letter highlight, compact cards)"
fi
echo "now run the gates:"
echo "  (cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app && .venv/bin/pytest -q)"
echo "  make eval-full PY=backend/.venv/bin/python   # expect 150/150, unsafe 0, FA 0/500"
echo "  (cd frontend && npx tsc -b && npx oxlint && npx vitest run && npm run build)"
