# Scheduler audit

Audit run 2026-11-02T08:56:29Z. Source: the scheduled-task record (get_trigger) and files on disk.

## Test categories

| Category | Status |
|---|---|
| Unit tests | **None exist.** Every test drives the real scripts end to end. |
| Sandbox integration tests | **Passed:** 10/10 + 3/3 passed (monitor suite + push suite) |
| Actual GitHub tests | **Passed:** 11-step recovery from GitHub, 81-file SHA-256 match with GitHub, secrets scan of GitHub history, real pushes to `monitor-state` |
| Unattended scheduler execution | **PENDING.** Not yet observed with the app/terminal closed. Prepared 2026-11-02T09:02:13Z; next scheduled run 09:43 UTC. |

## What the scheduler is

- **Type:** claude.ai cloud scheduled task (server-side cron that wakes this persistent Claude session); not OS cron, launchd, GitHub Actions or a daemon.
- **Trigger:** `trig_0159bajz89RVbmpSSciinzwJ`, enabled, schedule `CRON_TZ=Asia/Kolkata 13 8-23 2-7 11 *` (hourly at :13, 08:13-23:13 IST, 2-7 Nov 2026).
- **Next run:** 2026-11-02T09:43:00Z (15:13 IST). **Last run:** fired 2026-11-02T08:43:48Z, status SUCCEEDED.
- **Target:** fires into this persistent session (`session_014cBR3DER5ExACk3MkfFMkV`); no OS scheduler is involved (no crontab binary, no cron.d entry, no launchd, no GitHub workflow).

## Execution identity (recorded 2026-11-02T09:02:13Z)

- OS user `root` (uid 0), host `vm`, Python 3.13.18
- Git identity `Claude <noreply@anthropic.com>`
- Working directory: /home/user/three_way (per scheduled-task step C)
- Environment: HOME `/root`, shell `/bin/bash`, HTTPS proxy configured: True; credential variables are present by name only and never written to logs or commits
- Session: `session_014cBR3DER5ExACk3MkfFMkV` (started from the desktop app), environment `env_01U8jvhbwM7pbR1ah6ah8XCb`
- GitHub at preparation: monitor-state `612e442`, main `70c175c`

Change made for this test (approved): every scheduled run now pushes `monitor-state` after its tick and reports clone, restore, tick and push outcomes in one line.

## Evidence it runs on its own

| Scheduled run (UTC) | Logged tick (UTC) | Outcome |
|---|---|---|
| 2026-11-02T07:44:59Z | 2026-11-02T07:45:37.765035+00:00 | ok (pre-audit log format) |
| 2026-11-02T08:43:48Z | 2026-11-02T08:44:07.021837+00:00 | ok (pre-audit log format) |

Both runs were started by the server at the scheduled minute with no message from you. Whether your terminal or app was closed at those moments cannot be verified from inside the session; the trigger runs server-side either way.

## Answers

| Question | Answer | How established |
|---|---|---|
| Survives terminal closure? | Yes | Inspected (server-side trigger) + observed scheduled runs |
| Survives container restart? | Yes, via `monitor-state` | Simulated recovery test passed 11/11 |
| Where are logs? | `three_way/monitor/ticks.jsonl` (every run, UTC start/finish, outcome), `events.json` (T0 and checkpoints), `snapshot_index.jsonl` (manifest SHA-256), session transcript | Tested (every run type logs) |
| Duplicate snapshots prevented? | Yes | Tested: exclusive lock, adoption of existing snapshots, atomic state writes |
| What happens on 429? | All collection stops; scheduled task deletes itself | Tested (stop); deletion is in the task's instructions (inspected) |

## Scheduled-task instructions (summary)

A. re-attach and clone the persistence repo, switch to `monitor-state` with an explicit refspec; B. restore if local state is missing; C. run one tick under the lock; D. stop and delete itself on 429; E. start a 5-minute loop on a new T0; F. at each checkpoint record Tapetide and ARTHSCAN-cached MCP data, rebuild reports and push; G. on completion write the findings in chat and delete itself; H. otherwise reply in one line.
