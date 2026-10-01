#!/usr/bin/env bash
# scripts/backup_to_aidrive.sh — SK-12: one compressed archive of the repo → the owner's real AI Drive.
#
# WHY: Genspark Code guide — sandbox idle-stops after 1h and is deleted within hours (docs/agent/research/09 §1).
# HOW: `gsk aidrive upload --local_file` (verified 2026-10-01). NOT `cp` to /mnt/aidrive — that path is an
#      empty root-owned local directory in this sandbox, not a mount; files copied there die with the sandbox
#      (discovery D3, 2026-10-01).
# Excludes rebuildable/large content (venv, node_modules, corpus data+index, scratch, .git — GitHub holds history).
set -euo pipefail
cd "$(dirname "$0")/.."
STAMP=$(date -u +%F_%H%M)
NAME="basira_backup_${STAMP}.tar.gz"
TMP="/tmp/${NAME}"
tar czf "$TMP" \
  --exclude=.venv --exclude='backend/.venv' --exclude=node_modules --exclude='corpus/data' \
  --exclude='corpus/index' --exclude=.scratch --exclude=.git --exclude='*.egg-info' .
SIZE=$(du -h "$TMP" | cut -f1)
gsk aidrive mkdir --path /basira_backups --workspace my_drive --output json >/dev/null 2>&1 || true
gsk aidrive upload --local_file "$TMP" --upload_path "/basira_backups/${NAME}" --workspace my_drive --output json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); i=d.get("item") or d.get("data",{}).get("item") or d; print("uploaded:", i.get("path", i))'
echo "BACKUP OK — ${NAME} (${SIZE}) → AI Drive:/basira_backups/"
gsk aidrive ls --path /basira_backups --workspace my_drive --output text 2>/dev/null | tail -n +4 | tail -5
