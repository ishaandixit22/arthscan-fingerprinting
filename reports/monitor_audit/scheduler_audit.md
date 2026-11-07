# Scheduler audit

Updated 2026-11-02T15:17:14Z.

## Configuration

- Type: claude.ai cloud scheduled task (server-side cron that wakes this persistent Claude session); not OS cron, launchd, GitHub Actions or a daemon.
- Trigger `trig_0159bajz89RVbmpSSciinzwJ`, enabled, `CRON_TZ=Asia/Kolkata 13 8-23 2-7 11 *` (hourly at :13, 08:13-23:13 IST, 2-7 Nov 2026).
- Fires into session `session_014cBR3DER5ExACk3MkfFMkV` (desktop app), environment `env_01U8jvhbwM7pbR1ah6ah8XCb`.

## Execution identity

- OS user `root` (uid 0), host `vm`, Python 3.13.18.
- Git identity `Claude <noreply@anthropic.com>`.
- Working directory `/home/user/three_way`; persistence clone `/home/user/arthscan-fingerprinting` on branch `monitor-state`.
- Environment: HOME `/root`, shell `/bin/bash`, HTTPS proxy configured; credentials present as environment variables by name only, never logged or committed.

## Test categories

| Category | Status | Notes |
|---|---|---|
| Unit tests | **None exist** | Every test drives the real scripts end to end. |
| Sandbox integration tests | **Passed: 10/10 monitor, 3/3 push** | Throwaway folders and local git remotes; NSE feed and collector replaced by test doubles. |
| Actual GitHub tests | **Passed: recovery 12/12, 81-file SHA-256 match, secrets scan, real pushes** | Fresh clones of ishaandixit22/arthscan-fingerprinting, branch monitor-state. |
| Unattended scheduler execution | **PASSED (attempt 2, 14:55 UTC)** | Attempt 1 (09:43 UTC) failed at the restore step; fixed and re-run. |

## Unattended execution evidence

| Scheduled (UTC) | Fired (UTC) | Clone | Restore | Tick | Push |
|---|---|---|---|---|---|
| 09:43 | 09:43:34 | re-cloned | **failed** (attempt 1) | ok | ok (fd5e3db) |
| 10:43 | 10:43:36 | kept | not needed | ok | ok (642fa62) |
| 11:43 | 11:44:00 | kept | not needed | ok | ok (12159bd) |
| 12:43 | 13:00:19 | kept | not needed | ok | ok (9f6e064) |
| 13:43 | 13:46:49 | kept | not needed | ok | ok (1760a45) |
| 14:43 | 14:55:13 | re-cloned | **ok** (attempt 2) | ok | ok (7685c69) |

The session transcript shows no message from you between 14:03:39 and 15:15:39 UTC, so the 14:55 run was unattended.

## Answers

| Question | Answer | How established |
|---|---|---|
| Runs without an open terminal? | Yes | Observed: the 14:55 run with no user input |
| Restores from GitHub? | Yes | Observed in the 14:55 run and in the fresh-environment recovery test (12/12) |
| Logs? | `monitor/ticks.jsonl` (every run, UTC), `events.json`, `snapshot_index.jsonl`, session transcript | Tested and observed |
| Duplicate prevention? | Lock + snapshot adoption + atomic state | Sandbox-tested; no duplicates after the acceptance run |
| Push failures? | Retried with backoff; commit kept for the next push | Sandbox-tested |
