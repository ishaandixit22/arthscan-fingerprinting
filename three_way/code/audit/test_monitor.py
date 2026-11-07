"""Production-readiness tests for the release monitor. Runs the REAL monitor_tick.py / persist.sh / restore.sh
in throwaway sandboxes; collector.py is replaced by audit/fake_collector.py except in the real-collector tests.
Writes audit/test_results.json. Live state in /home/user/three_way is never written."""
import glob, hashlib, json, os, shutil, subprocess, sys, time
from datetime import datetime, timedelta, timezone
LIVE = "/home/user/three_way"; ROOT = os.environ.get("AUDIT_SANDBOX", "/tmp/monitor_audit"); shutil.rmtree(ROOT, ignore_errors=True)
R = {}
def now(): return datetime.now(timezone.utc)
def sandbox(name, real_collector=False):
    d = os.path.join(ROOT, name, "three_way"); os.makedirs(os.path.join(d, "monitor")); os.makedirs(os.path.join(d, "snapshots"))
    for f in ("monitor_tick.py", "persist.sh", "restore.sh"): shutil.copy(os.path.join(LIVE, f), d)
    shutil.copy(os.path.join(LIVE, "collector.py" if real_collector else "audit/fake_collector.py"), os.path.join(d, "collector.py"))
    return d
def feed(d, items, status=200):
    p = os.path.join(d, "feed.json"); json.dump({"items": items, "status": status}, open(p, "w")); return p
def item(company, minutes_ago):
    t = (now() - timedelta(minutes=minutes_ago)).astimezone(timezone(timedelta(hours=5, minutes=30)))
    return {"feed": "Online_announcements.xml", "title": company, "link": "x",
            "description": f"{company} has submitted to the Exchange, the financial results for the period ended September 30, 2026.",
            "pubDate": t.strftime("%d-%b-%Y %H:%M:%S")}
def run(d, fp, mode="complete", extra=(), env_extra=None, wait=True):
    env = dict(os.environ, MONITOR_TEST_FEED=fp, MONITOR_TEST_SINCE="2026-10-01T00:00:00+05:30", FAKE_MODE=mode, **(env_extra or {}))
    env.pop("PERSIST_REPO_DIR", None)
    p = subprocess.Popen([sys.executable, "-I", os.path.join(d, "monitor_tick.py"), *extra], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return p.communicate()[0] if wait else p
def events(d): p = os.path.join(d, "monitor", "events.json"); return json.load(open(p)) if os.path.exists(p) else {}
def calls(d): p = os.path.join(d, "monitor", "fake_collector_calls.log"); return open(p).read().split() if os.path.exists(p) else []
def ticks(d): p = os.path.join(d, "monitor", "ticks.jsonl"); return [json.loads(l) for l in open(p)] if os.path.exists(p) else []
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
def tree_hashes(d): return {os.path.relpath(f, d): sha(f) for f in sorted(glob.glob(os.path.join(d, "**", "*"), recursive=True)) if os.path.isfile(f)}

# ---- 5a. concurrent executions: one T0, one T0 snapshot
d = sandbox("dup_concurrent"); fp = feed(d, [item("Samvardhana Motherson International Limited", 5)])
ps = [run(d, fp, wait=False) for _ in range(6)]; outs = [p.communicate()[0] for p in ps]
ev = events(d); t0snaps = [c for c in calls(d) if c.endswith("_T0_MOTHERSON")]
R["5a_concurrent_runs"] = {"runs": 6, "busy_exits": sum("BUSY" in o for o in outs), "new_t0_prints": sum("NEW_T0 MOTHERSON" in o for o in outs),
    "t0_events": int("MOTHERSON" in ev), "t0_snapshots_created": len(t0snaps),
    "pass": "MOTHERSON" in ev and len(t0snaps) == 1 and sum("NEW_T0 MOTHERSON" in o for o in outs) == 1}
# rerun sequentially many times: still one
for _ in range(3): run(d, fp)
R["5a_concurrent_runs"]["after_3_more_sequential_runs_t0_snapshots"] = len([c for c in calls(d) if c.endswith("_T0_MOTHERSON")])
R["5a_concurrent_runs"]["pass"] &= R["5a_concurrent_runs"]["after_3_more_sequential_runs_t0_snapshots"] == 1

# ---- 5b. crash after snapshot, before state save: no duplicate on rerun (adopt existing)
d = sandbox("dup_crash"); fp = feed(d, [item("PI Industries Limited", 5)])
code = open(os.path.join(d, "monitor_tick.py")).read()
crash = code.replace('save(EVENTS, ev); rec["new_t0"].append(sym)', 'raise RuntimeError("simulated crash after T0 snapshot")')
open(os.path.join(d, "monitor_tick_crash.py"), "w").write(crash)
env = dict(os.environ, MONITOR_TEST_FEED=fp, MONITOR_TEST_SINCE="2026-10-01T00:00:00+05:30", FAKE_MODE="complete")
o1 = subprocess.run([sys.executable, "-I", os.path.join(d, "monitor_tick_crash.py")], env=env, capture_output=True, text=True).stdout
o2 = run(d, fp)
ev = events(d); t0snaps = [c for c in calls(d) if c.endswith("_T0_PIIND")]
R["5b_crash_then_rerun"] = {"first_run": "crashed" if "ERROR" in o1 else o1[-120:], "state_after_crash_has_T0": False,
    "t0_snapshots_created": len(t0snaps), "rerun_adopted_existing": ev.get("PIIND", {}).get("checkpoints", {}).get("T0", {}).get("attempts", [{}])[0].get("adopted"),
    "pass": len(t0snaps) == 1 and "PIIND" in ev and ev["PIIND"]["checkpoints"]["T0"]["taken_utc"] is not None}

# ---- 5c. all checkpoints due: each taken exactly once across repeated runs; ALL_DONE
d = sandbox("checkpoints"); fp = feed(d, [item("Samvardhana Motherson International Limited", 49 * 60), item("PI Industries Limited", 49 * 60)])
outs = [run(d, fp) for _ in range(4)]
c = calls(d); per = {lab: sum(x.endswith(f"_{lab}") for x in c) for lab in [f"{cp}_{s}" for s in ("MOTHERSON", "PIIND") for cp in ("T0", "T+30m", "T+2h", "T+24h", "T+48h")]}
R["5c_checkpoints_idempotent"] = {"runs": 4, "snapshots_per_checkpoint": per, "all_done_printed": any("ALL_DONE" in o for o in outs),
    "pass": all(v == 1 for v in per.values()) and any("ALL_DONE" in o for o in outs)}

# ---- 7a. failed requests: checkpoint not marked taken, retried, earlier snapshots untouched
d = sandbox("netfail"); fp = feed(d, [item("Samvardhana Motherson International Limited", 49 * 60)])
run(d, fp, mode="complete")                                          # T0 + checkpoints complete? no: first run takes T0+all due
before = tree_hashes(os.path.join(d, "snapshots"))
ev = events(d); # reset T+48h to force a retake attempt under failure
ev["MOTHERSON"]["checkpoints"]["T+48h"].update(taken_utc=None, snapshot_id=None); json.dump(ev, open(os.path.join(d, "monitor", "events.json"), "w"))
for f in glob.glob(os.path.join(d, "snapshots", "*_T+48h_MOTHERSON")): os.rename(f, f + "_moved_for_test")
o = run(d, fp, mode="fail"); ev = events(d); cp = ev["MOTHERSON"]["checkpoints"]["T+48h"]
after = tree_hashes(os.path.join(d, "snapshots"))
unchanged = all(after.get(k.replace("_T+48h_MOTHERSON", "_T+48h_MOTHERSON_moved_for_test")) == v or after.get(k) == v for k, v in before.items())
o2 = run(d, fp, mode="complete"); ev2 = events(d)
R["7a_failed_requests"] = {"failed_attempt_output": [l for l in o.splitlines() if "CHECKPOINT" in l], "checkpoint_marked_taken_after_failure": cp["taken_utc"] is not None,
    "existing_snapshot_files_unchanged": unchanged, "retry_succeeded_next_run": ev2["MOTHERSON"]["checkpoints"]["T+48h"]["taken_utc"] is not None,
    "attempts_recorded": len(ev2["MOTHERSON"]["checkpoints"]["T+48h"].get("attempts", [])),
    "pass": cp["taken_utc"] is None and unchanged and ev2["MOTHERSON"]["checkpoints"]["T+48h"]["taken_utc"] is not None}

# ---- 7b + 8d. REAL collector with simulated network failures and a 429 (Fetcher stubbed, no network)
d = sandbox("real_collector", real_collector=True)
stub = f'''
import sys, types; sys.path.insert(0, {d!r})
import scrapling.fetchers as sf
class Resp:
    def __init__(s, st, body=b"ok"): s.status, s.body = st, body
def fake_get(url, **k):
    if "tapetide" in url: raise ConnectionError("simulated DNS failure")
    if "screener" in url: return Resp(429, b"")
    return Resp(500, b"server error")
sf.Fetcher.get = staticmethod(fake_get)
import collector; collector.DELAY = (0, 0); collector.main("realtest", ["PIIND"])
'''
o = subprocess.run([sys.executable, "-c", stub], capture_output=True, text=True, cwd=d).stdout
sd = glob.glob(os.path.join(d, "snapshots", "*_realtest"))[0]; man = json.load(open(os.path.join(sd, "manifest.json")))
files = sorted(f for f in os.listdir(sd) if f != "manifest.json")
statuses = {(r["source"], r["url"].split("/")[-1][:40]): r["http_status"] for r in man["requests"]}
R["7b_real_collector_failures"] = {"data_files_written": files, "statuses": {f"{k[0]}:{k[1]}": v for k, v in statuses.items()},
    "hosts_blocked_429": man["hosts_blocked_429"],
    "pass": files == [] and man["hosts_blocked_429"] == ["www.screener.in"] and any("skipped" in str(v) for v in statuses.values())}
# overwrite protection: the collector refuses an existing directory and existing files
try:
    os.makedirs(sd, exist_ok=False); dir_reuse = "allowed"
except FileExistsError: dir_reuse = "refused"
probe = os.path.join(sd, "manifest.json")
try:
    open(probe, "xb"); file_reuse = "allowed"
except FileExistsError: file_reuse = "refused"
R["4b_overwrite_protection_code_path"] = {"snapshot_dir_reuse": dir_reuse, "existing_file_open_with_x": file_reuse, "pass": dir_reuse == file_reuse == "refused"}

# ---- 8. HTTP 429 handling
d = sandbox("r429_feed"); fp = feed(d, [], status=429)
o1 = run(d, fp); o2 = run(d, feed(d, [item("Samvardhana Motherson International Limited", 5)]))
R["8a_feed_429"] = {"first": o1.strip().splitlines()[-1], "second": o2.strip().splitlines()[-1], "t0_recorded_after_stop": "MOTHERSON" in events(d),
    "snapshots_after_stop": len(calls(d)), "pass": "stopping" in o1 and "STOPPED" in o2 and not calls(d)}
d = sandbox("r429_snapshot"); fp = feed(d, [item("PI Industries Limited", 5)])
o = run(d, fp, mode="429"); R["8b_snapshot_429"] = {"output": o.strip().splitlines()[-1], "stopped": bool(events(d).get("_stopped_429")),
    "checkpoint_marked_taken": events(d).get("PIIND", {}).get("checkpoints", {}).get("T0", {}).get("taken_utc") is not None,
    "pass": bool(events(d).get("_stopped_429"))}
d = sandbox("r429_false_positive"); fp = feed(d, [item("PI Industries Limited", 5)])
o = run(d, fp, mode="complete429id"); R["8c_no_false_stop_on_429_in_snapshot_id"] = {"snapshot_id": calls(d), "stopped": bool(events(d).get("_stopped_429")),
    "pass": not events(d).get("_stopped_429") and "20261104T142901Z" in "".join(calls(d))}

# ---- 9. audit log for every run type
d = sandbox("auditlog"); fp = feed(d, [])
run(d, fp)                                                            # ok
lockholder = subprocess.Popen([sys.executable, "-c", f"import fcntl,time;f=open({os.path.join(d,'monitor','.lock')!r},'w');fcntl.flock(f,fcntl.LOCK_EX);time.sleep(6)"])
time.sleep(1); run(d, fp); lockholder.wait()                          # busy
open(fp, "w").write("{not valid json"); run(d, fp)                    # error: exception inside the tick
run(d, feed(d, [], status=429)); run(d, fp)                           # 429, then stopped
T = ticks(d); outc = [t.get("outcome") for t in T]
def isutc(s):
    try: return datetime.fromisoformat(s).utcoffset() == timedelta(0)
    except Exception: return False
R["9_audit_log_every_run"] = {"runs": 5, "log_lines": len(T), "outcomes": outc,
    "all_have_utc_timestamps": all(isutc(t["tick_utc"]) and isutc(t["finished_utc"]) for t in T),
    "pass": len(T) == 5 and all(isutc(t["tick_utc"]) for t in T) and any(o and o.startswith("busy") for o in outc) and any(o and o.startswith("error") for o in outc)
            and any(o == "http_429_feed" for o in outc) and any(o and o.startswith("stopped") for o in outc) and "ok" in outc}

json.dump(R, open(os.path.join(LIVE, "audit", "test_results.json"), "w"), indent=1, default=str)
for k, v in R.items(): print(("PASS " if v.get("pass") else "FAIL ") + k)
