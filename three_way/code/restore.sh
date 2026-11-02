#!/usr/bin/env bash
# Rebuild /home/user/three_way (and its dependencies) from the persistence repo on a fresh container.
set -euo pipefail
D="${PERSIST_REPO_DIR:-/home/user/arthscan-fingerprinting}"; U="${RESTORE_ROOT:-/home/user}"
git -C "$D" fetch -q --depth 1 origin +refs/heads/monitor-state:refs/remotes/origin/monitor-state 2>/dev/null && git -C "$D" checkout -q -B monitor-state origin/monitor-state || true
[ -d "$D/three_way/code" ] || { echo "RESTORE: nothing to restore"; exit 2; }
mkdir -p "$U/three_way/monitor" "$U/three_way/evidence" "$U/three_way/snapshots" "$U/fingerprint" "$U/reports"
cp -n "$D/three_way/code/"* "$U/three_way/"
cp -a --update=none "$D/three_way/snapshots/." "$U/three_way/snapshots/"
cp -a "$D/three_way/state/monitor/." "$U/three_way/monitor/"
cp -a "$D/three_way/state/evidence/." "$U/three_way/evidence/"
cp -n "$D/deps/compare_engine.py" "$U/fingerprint/"
cp -a --update=none "$D/reports/." "$U/reports/"
python -c "import scrapling" 2>/dev/null || pip install -q "scrapling[fetchers]" xlrd >/dev/null 2>&1
echo "RESTORE: ok ($(ls "$U/three_way/snapshots" | wc -l) snapshots, events: $(test -f "$U/three_way/monitor/events.json" && echo yes || echo none))"
