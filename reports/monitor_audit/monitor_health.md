# Release monitor: health and acceptance

Updated 2026-11-02T15:17:14Z.

## Verdict

**Production-ready for the 4-5 Nov release window.** The unattended scheduler acceptance test passed on its second attempt; the first attempt exposed a restore bug, which was fixed with your approval.

## Test categories

| Category | Status | Notes |
|---|---|---|
| Unit tests | **None exist** | Every test drives the real scripts end to end. |
| Sandbox integration tests | **Passed: 10/10 monitor, 3/3 push** | Throwaway folders and local git remotes; NSE feed and collector replaced by test doubles. |
| Actual GitHub tests | **Passed: recovery 12/12, 81-file SHA-256 match, secrets scan, real pushes** | Fresh clones of ishaandixit22/arthscan-fingerprinting, branch monitor-state. |
| Unattended scheduler execution | **PASSED (attempt 2, 14:55 UTC)** | Attempt 1 (09:43 UTC) failed at the restore step; fixed and re-run. |

## Unattended acceptance run (attempt 2)

| Step | Result | Evidence |
|---|---|---|
| Fired by the server, no user input | PASS | trigger fired 14:55:13 UTC (scheduled 14:43, 12 min late); user messages at 14:03:39 and 15:15:39 UTC only |
| Re-cloned the repo from GitHub | PASS | clone: re-cloned @de06bf2, explicit refspec |
| Restored monitor-state | PASS | RESTORE: ok (1 snapshots, events: none), exit 0 |
| Acquired the lock | PASS | tick ran (not BUSY), pid 227 |
| Executed the monitor | PASS | TICK 2026-11-02T14:56:17Z, both NSE feeds HTTP 200 |
| Wrote the audit log | PASS | line 11, UTC start 2026-11-02T14:56:17Z and finish 2026-11-02T14:56:22Z, outcome ok |
| Preserved snapshot hashes | PASS | 81/81 files identical to the pre-test record |
| Pushed the resulting state | PASS | commit 7685c69 on monitor-state |
| Fresh environment restore afterwards | PASS | 12/12 recovery steps; restored commit 7685c69 = GitHub 7685c69 |
| No duplicate T0s or checkpoints | PASS | 1 snapshot folder (baseline), no events.json, empty snapshot index |
| main untouched | PASS | main still 70c175c |

Method: before the run, the live monitor folder and the repo clone were moved aside so the scheduled run had to re-clone and restore from GitHub. The container itself was not reclaimed, so this demonstrates restore from GitHub, not survival of a real container reset.

## Attempt 1 (09:43 UTC): failed

- FAILED: restore.sh line 8 `cp -n "$D/three_way/code/"* "$U/three_way/"` exits non-zero on the code/audit directory (added after the 11-step recovery test); set -e aborted before snapshots and monitor state were copied
- Live state was reinstated from the local backup; lock, tick, audit log and push still succeeded.
- Fix: `restore.sh` line 8 now copies the code folder recursively (commit 3f8211d).

## Limitations that remain

- 429 resume is manual: remove `_stopped_429` from `monitor/events.json` and re-create the scheduled task.
- The monitor runs as root, so file permissions do not stop edits; integrity rests on the write-once code, SHA-256 manifests and git history.
- Scheduled runs started up to 17 minutes late today; T+30m and T+2h depend on the 5-minute loop started at T0.
- Checkpoint MCP captures (Tapetide, ARTHSCAN-cached Indian Stock API) are not yet exercised; no company has filed.
- A harmless `cp -n` warning remains on another line of `restore.sh`.

## Current state

- Waiting for MOTHERSON and PIIND results; no events; Phase 4 monitoring is not complete.
- `monitor-state` at 7685c69 after the acceptance run; `main` untouched at 70c175c.
