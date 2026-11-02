# Release monitor: production-readiness audit

Audit run 2026-11-02T08:56:29Z. Scope: the Tapetide fingerprinting release monitor (`three_way/`), its scheduled task and its persistence branch. `main` and ARTHSCAN production were not modified.

## Test categories

| Category | Status |
|---|---|
| Unit tests | **None exist.** Every test drives the real scripts end to end. |
| Sandbox integration tests | **Passed:** 10/10 + 3/3 passed (monitor suite + push suite) |
| Actual GitHub tests | **Passed:** 11-step recovery from GitHub, 81-file SHA-256 match with GitHub, secrets scan of GitHub history, real pushes to `monitor-state` |
| Unattended scheduler execution | **PENDING.** Not yet observed with the app/terminal closed. Prepared 2026-11-02T09:02:13Z; next scheduled run 09:43 UTC. |

## Verdict

**Ready for the 4-5 Nov release window, with three open limitations** (manual 429 resume, root-writable snapshot files, MCP checkpoint captures not yet exercised). All ten requirements pass or are observed; five defects found during the audit were fixed first and are covered by the tests.

## Results

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 1 | Scheduler runs without an open terminal | **OBSERVED + INSPECTED** | Server-side scheduled task; two scheduled runs fired and logged (07:45, 08:44 UTC); last run status SUCCEEDED. I cannot close your terminal, so 'terminal closed' itself was not tested. |
| 2 | Restores state from monitor-state after a reset | **PASSED (simulated)** | Fresh shallow clone from GitHub into an empty root: 11/11 steps passed, restored monitor ran a real tick. Not an actual container reset. |
| 3 | Explicit refspec for shallow-clone restore | **PASSED** | Negative control: plain fetch leaves origin/monitor-state missing; explicit refspec creates it. Both scripts use it. |
| 4 | Snapshots immutable and SHA-256 verified | **PASSED, with a limitation** | 80 live files match manifests; 81 GitHub copies byte-identical; code refuses to reuse a folder or file. Limitation: runs as root, and root can write to 0444 files. |
| 5 | No duplicate T0 events or checkpoints | **PASSED (after fix D2)** | 6 concurrent runs: 1 T0, 1 snapshot, 3 BUSY exits; crash after snapshot then rerun: existing snapshot adopted, 1 snapshot; 4 runs with all checkpoints due: each taken once. |
| 6 | No credentials in GitHub commits | **PASSED** | 4 commits / 11,217,747 bytes scanned: 0 token/key patterns, none of 11 secret env values present, remote URL has no credential. |
| 7 | Failed requests never overwrite valid snapshots | **PASSED (after fix D5)** | Simulated network failure: checkpoint not marked taken, existing snapshot files unchanged, retried successfully next run. Real collector with DNS failure / HTTP 500 / 429: no data files written. |
| 8 | HTTP 429 pauses collection safely | **PASSED (after fix D3); resume is manual** | Feed 429 and snapshot 429 both stop all collection and later runs print STOPPED without polling. A '429' inside a snapshot ID no longer causes a false stop. Resuming requires a manual reset. |
| 9 | Every run writes a UTC audit log line | **PASSED (after fix D1)** | 5 run types logged with UTC start and finish: ok, busy (lock held by another run), error, http_429_feed, stopped (earlier HTTP 429). |
| 10 | Push failures retried safely | **PASSED (local remotes)** | Unreachable remote: 4 retries over 30.2 s, exit 1, commit kept; next push delivered both commits; 2 concurrent pushes serialised, no index.lock errors. Not tested against a real GitHub outage. |

Status key: **PASSED** = executed test with a pass result; **OBSERVED** = seen happening in real runs but not under controlled conditions; **INSPECTED** = read in code or configuration only.

## Defects found and fixed during the audit

| ID | Defect | Fix | Requirement |
|---|---|---|---|
| D1 | BUSY, STOPPED, 429 and exception paths wrote no audit line | tick() wrapped with a logging finally block; BUSY logged before exit | 9 |
| D2 | Crash between snapshot and state save led to a duplicate snapshot on rerun | existing complete snapshot with the same label is adopted instead of retaken | 5 |
| D3 | 429 detected by searching stdout for '429', so snapshot IDs like ...T142901Z could falsely stop the monitor | 429 read from the manifest's hosts_blocked_429 | 8 |
| D4 | persist.sh could run concurrently (scheduled step and loop) | flock serialises pushes (120 s wait) | 10 |
| D5 | A checkpoint was marked taken even if every request failed | checkpoint is taken only when all requests return 200; failed attempts are recorded and retried | 7 |

The fixes were pushed to `monitor-state` (commit 88fb5ac) and are the code the recovery test restored.

## Inspected only, or not yet exercised

- Scheduled-task steps F and G (Tapetide and ARTHSCAN-cached MCP captures at checkpoints, final write-up): not exercised yet, as no T0 has occurred. The trigger stores no connector list (mcp_connections: []); it fires into this session, which has both connectors, but that path is unproven until the first checkpoint.
- Behaviour across a real container reclaim: simulated only. A background --loop process dies with the container; missed T+30m/T+2h would then be taken late at the next hourly run (lateness is recorded).
- Coverage gaps: checks run 08:13-23:13 IST only. A late-night filing still gets its exact T0 from the feed timestamp (feed holds ~5 h of items), but T0, T+30m and T+2h snapshots would be taken late.
- Arth MCP quota (free plan, 50 calls/day): checkpoint captures use about 2 calls per checkpoint; not load-tested.
- main branch: you merged PR #1, so main holds a stale copy of state up to commit 1c92fb4. The monitor never reads or writes main.

## Limitations to accept or address

- **429 resume is manual.** Collection stops for good; to resume, remove `_stopped_429` from `monitor/events.json` and re-create the scheduled task (step D deletes it).
- **Root can write to snapshot files.** Protection comes from the write-once code paths, the manifest SHA-256s and git history, not from file permissions. Any edit would show up as a hash mismatch.
- **Secrets scan** covers known token formats and the exact values of this environment's secret variables; it is not a general-purpose secret scanner.

## Current state

- Monitor: waiting for T0 for MOTHERSON and PIIND; no events recorded; `monitoring.complete` remains false.
- Live audit log: 5 lines, last 2026-11-02T08:44:07.021837+00:00.
- Test code: `three_way/audit/` (test_monitor.py, test_persist.py, fake_collector.py) with raw results JSON.
