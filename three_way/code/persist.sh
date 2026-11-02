#!/usr/bin/env bash
# Push monitor state, evidence, code and immutable snapshots to $PERSIST_REPO_DIR (dedicated non-production repo).
# Snapshots already in the repo are never rewritten (--ignore-existing). Credentials come from the environment's
# git configuration; nothing is printed.
set -euo pipefail
: "${PERSIST_REPO_DIR:?}"; HERE="$(cd "$(dirname "$0")" && pwd)"; U="$(dirname "$HERE")"; D="$PERSIST_REPO_DIR"
mkdir -p "$D/three_way/snapshots" "$D/three_way/state/monitor" "$D/three_way/state/evidence" "$D/three_way/code" "$D/deps" "$D/reports"
cp -a --update=none "$HERE/snapshots/." "$D/three_way/snapshots/"
cp -a "$HERE/monitor/." "$D/three_way/state/monitor/"; rm -f "$D/three_way/state/monitor/.lock" "$D/three_way/state/monitor/.persist.lock"
cp -a "$HERE/evidence/." "$D/three_way/state/evidence/"
cp -a "$HERE"/*.py "$HERE"/*.sh "$D/three_way/code/"; mkdir -p "$D/three_way/code/audit"; cp -a "$HERE/audit/." "$D/three_way/code/audit/"
cp -a "$U/fingerprint/compare_engine.py" "$D/deps/"
cp -a "$U/reports/." "$D/reports/"
exec 9>"$HERE/monitor/.persist.lock"; flock -w 120 9 || { echo "persist: lock timeout"; exit 3; }   # one persist at a time
cd "$D"
BR=monitor-state
if [ "$(git rev-parse --abbrev-ref HEAD)" != "$BR" ]; then
  git fetch -q --depth 1 origin "+refs/heads/$BR:refs/remotes/origin/$BR" 2>/dev/null && git checkout -q -B "$BR" "origin/$BR" || git checkout -q -B "$BR"
fi
git add -A
git diff --cached --quiet || git commit -q -m "${1:-monitor checkpoint} ($(date -u +%FT%TZ))" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cBR3DER5ExACk3MkfFMkV"
for i in 1 2 3 4; do git push -q -u origin "$BR" && exit 0; sleep $((2**i)); done; exit 1
