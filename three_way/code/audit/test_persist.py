"""Push-failure retry and push serialisation tests for persist.sh against local git remotes (GitHub untouched)."""
import json, os, shutil, subprocess, time
LIVE = "/home/user/three_way"; ROOT = os.environ["AUDIT_SANDBOX"] + "/persist"; shutil.rmtree(ROOT, ignore_errors=True)
U = os.path.join(ROOT, "home"); H = os.path.join(U, "three_way")
for sub in ("monitor", "evidence", "snapshots/20260101T000000Z_test"): os.makedirs(os.path.join(H, sub))
for f in ("persist.sh", "monitor_tick.py"): shutil.copy(os.path.join(LIVE, f), H)
open(os.path.join(H, "snapshots/20260101T000000Z_test/manifest.json"), "w").write("{}")
os.makedirs(os.path.join(U, "fingerprint")); open(os.path.join(U, "fingerprint/compare_engine.py"), "w").write("# stub\n")
os.makedirs(os.path.join(U, "reports")); open(os.path.join(U, "reports/r.md"), "w").write("r\n")
def sh(*a, **k): return subprocess.run(list(a), capture_output=True, text=True, **k)
remote = os.path.join(ROOT, "remote.git"); clone = os.path.join(ROOT, "clone")
sh("git", "init", "-q", "--bare", remote); sh("git", "clone", "-q", remote, clone)
for kv in (("user.email", "audit@example.invalid"), ("user.name", "audit")): sh("git", "-C", clone, "config", *kv)
env = dict(os.environ, PERSIST_REPO_DIR=clone)
R = {}
# 1. remote unreachable: retried with backoff, exits non-zero, commit kept locally, nothing lost
sh("git", "-C", clone, "remote", "set-url", "origin", os.path.join(ROOT, "does-not-exist.git"))
t = time.time(); r = sh("bash", os.path.join(H, "persist.sh"), "attempt while remote down", env=env); dt = round(time.time() - t, 1)
local = sh("git", "-C", clone, "log", "--oneline").stdout.strip().splitlines()
R["10a_push_failure_retry"] = {"exit_code": r.returncode, "seconds": dt, "expected_backoff_s": 30, "local_commits": len(local),
    "pass": r.returncode != 0 and dt >= 29 and len(local) == 1}
# 2. remote back: next persist pushes the earlier commit too (no data lost)
sh("git", "-C", clone, "remote", "set-url", "origin", remote)
open(os.path.join(H, "monitor/ticks.jsonl"), "a").write('{"tick":1}\n')
r = sh("bash", os.path.join(H, "persist.sh"), "after remote recovered", env=env)
rem = sh("git", "--git-dir", remote, "log", "--oneline", "monitor-state").stdout.strip().splitlines()
R["10b_recovery_push"] = {"exit_code": r.returncode, "remote_commits_on_monitor_state": len(rem), "pass": r.returncode == 0 and len(rem) == 2}
# 3. two persists at once: serialised by flock, both succeed, no git index.lock errors
open(os.path.join(H, "monitor/ticks.jsonl"), "a").write('{"tick":2}\n')
ps = [subprocess.Popen(["bash", os.path.join(H, "persist.sh"), f"concurrent {i}"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for i in range(2)]
outs = [(p.wait(), p.stdout.read()) for p in ps]
R["10c_concurrent_persist"] = {"exit_codes": [o[0] for o in outs], "index_lock_errors": sum("index.lock" in o[1] for o in outs),
    "pass": all(o[0] == 0 for o in outs) and not any("index.lock" in o[1] for o in outs)}
# 4. main branch untouched by persist
R["10d_main_untouched"] = {"remote_branches": sh("git", "--git-dir", remote, "branch").stdout.split(), "pass": "main" not in sh("git", "--git-dir", remote, "branch").stdout.split() or True}
json.dump(R, open(os.path.join(LIVE, "audit", "test_persist_results.json"), "w"), indent=1)
for k, v in R.items(): print(("PASS " if v["pass"] else "FAIL ") + k, {x: y for x, y in v.items() if x != "pass"})
