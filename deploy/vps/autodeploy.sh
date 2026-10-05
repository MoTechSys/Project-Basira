#!/bin/bash
# Basira auto-deploy (installed as /opt/basira/autodeploy.sh, run every minute by basira-autodeploy.timer).
# Compares the server's commit with $BRANCH of $REPO (autodeploy.conf).
# If GitHub has a new commit → fetch, rebuild, restart, health-check. If the build fails,
# the running site is NOT touched (compose replaces the container only after a successful build).
set -uo pipefail
cd /opt/basira
source /opt/basira/autodeploy.conf
LOG=/var/log/basira-deploy.log
exec 9>/run/basira-deploy.lock
flock -n 9 || exit 0                               # a deploy is already running

remote=$(git ls-remote "$REPO" "refs/heads/$BRANCH" 2>/dev/null | cut -f1)
[ -n "$remote" ] || { echo "$(date '+%F %T') ERROR branch '$BRANCH' not found on $REPO" >> $LOG; exit 1; }
local_sha=$(git rev-parse HEAD)
[ "$remote" = "$local_sha" ] && [ "${1:-}" != "--force" ] && exit 0   # nothing new

{
echo "================================================================"
echo "$(date '+%F %T') NEW COMMIT on $BRANCH: ${local_sha:0:7} → ${remote:0:7}"
git remote set-url origin "$REPO"
git fetch -q origin "$BRANCH"
git reset -q --hard "$remote"
git log -1 --format='  commit: %h %an — %s' | cut -c1-160
export BUILD_SHA=$(git rev-parse --short HEAD)
start=$(date +%s)
if docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build > /root/build.log 2>&1; then
  sleep 8
  code=$(curl -s -m 10 -o /dev/null -w '%{http_code}' "${HEALTH_URL:-https://basirapp.site/health}")
  live=$(curl -s -m 10 "${HEALTH_URL:-https://basirapp.site/health}" | grep -o '"build_sha":"[^"]*"')
  echo "  ✅ DEPLOYED $BUILD_SHA in $(( $(date +%s) - start ))s · health $code · $live"
  docker image prune -f >/dev/null
else
  echo "  ❌ BUILD FAILED — site still runs the previous version. Details: /root/build.log"
  grep -E "ERROR|error " /root/build.log | head -5 | sed 's/^/     /'
fi
} >> $LOG 2>&1
