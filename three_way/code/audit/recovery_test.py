"""Recovery test from GitHub: fresh shallow clone -> explicit refspec -> restore into an empty root -> verify -> run a real tick.
Writes audit/recovery_raw.json. Never writes to live state or GitHub."""
import glob, hashlib, json, os, shutil, subprocess, sys, time
from datetime import datetime, timezone
S = sys.argv[1]; shutil.rmtree(S, ignore_errors=True); os.makedirs(S)
URL = "https://github.com/ishaandixit22/arthscan-fingerprinting"; LIVE = "/home/user/three_way"
R = {"started_utc": datetime.now(timezone.utc).isoformat(), "steps": []}
def sh(*a, **k):
    t = time.time(); r = subprocess.run(list(a), capture_output=True, text=True, **k); return r, round(time.time() - t, 1)
def step(name, ok, **kw): R["steps"].append({"step": name, "pass": bool(ok), **kw}); print(("PASS " if ok else "FAIL ") + name, kw)
def hashes(root): return {os.path.relpath(f, root): hashlib.sha256(open(f, "rb").read()).hexdigest() for f in glob.glob(os.path.join(root, "**", "*"), recursive=True) if os.path.isfile(f)}
clone = os.path.join(S, "clone"); r, dt = sh("git", "clone", "-q", "--depth", "1", URL, clone)
step("fresh shallow clone from GitHub", r.returncode == 0, seconds=dt)
sh("git", "-C", clone, "fetch", "-q", "origin", "monitor-state")
step("negative control: plain fetch leaves origin/monitor-state missing", sh("git", "-C", clone, "rev-parse", "--verify", "-q", "origin/monitor-state")[0].returncode != 0)
sh("git", "-C", clone, "fetch", "-q", "--depth", "1", "origin", "+refs/heads/monitor-state:refs/remotes/origin/monitor-state")
pos = sh("git", "-C", clone, "rev-parse", "--verify", "-q", "origin/monitor-state")[0]
step("explicit refspec fetch creates origin/monitor-state", pos.returncode == 0, commit=pos.stdout.strip()[:7])
open(os.path.join(S, "restore.sh"), "w").write(sh("git", "-C", clone, "show", "origin/monitor-state:three_way/code/restore.sh")[0].stdout)
fresh = os.path.join(S, "fresh"); r, dt = sh("bash", os.path.join(S, "restore.sh"), env=dict(os.environ, RESTORE_ROOT=fresh, PERSIST_REPO_DIR=clone))
step("restore.sh rebuilds an empty root", "RESTORE: ok" in r.stdout and r.returncode == 0, seconds=dt, exit=r.returncode, output=(r.stdout + r.stderr).strip().splitlines()[-1:])
live_s, rest_s = hashes(os.path.join(LIVE, "snapshots")), hashes(os.path.join(fresh, "three_way", "snapshots"))
step("restored snapshots byte-identical to live (SHA-256)", live_s == rest_s and len(live_s) == 81, files=len(rest_s))
code_ok = all(open(os.path.join(LIVE, f)).read() == open(os.path.join(fresh, "three_way", f)).read() for f in ("monitor_tick.py", "collector.py", "persist.sh", "restore.sh", "analyze.py", "build_report.py"))
step("restored code identical to live", code_ok)
step("restored audit/ folder present", os.path.isdir(os.path.join(fresh, "three_way", "audit")))
lt = sum(1 for _ in open(os.path.join(LIVE, "monitor", "ticks.jsonl"))); rt = sum(1 for _ in open(os.path.join(fresh, "three_way", "monitor", "ticks.jsonl")))
step("restored audit log matches live line count", rt == lt, live=lt, restored=rt)
step("restored analysis dependencies present", os.path.exists(os.path.join(fresh, "fingerprint", "compare_engine.py")) and os.path.exists(os.path.join(fresh, "reports", "tapetide_screener_validation", "detailed_mismatches.csv")))
r, dt = sh("python", "-I", os.path.join(fresh, "three_way", "monitor_tick.py"))
line = [l for l in r.stdout.splitlines() if l.startswith(("TICK", "BUSY", "STOPPED", "ERROR"))]
step("restored monitor executes a real tick", bool(line) and line[0].startswith("TICK"), seconds=dt, output=line[:1])
last = json.loads(open(os.path.join(fresh, "three_way", "monitor", "ticks.jsonl")).read().splitlines()[-1])
step("restored tick wrote a UTC audit line", last.get("outcome") == "ok" and last["tick_utc"].endswith("+00:00"), outcome=last.get("outcome"))
before = hashes(os.path.join(fresh, "three_way", "snapshots"))
sh("bash", os.path.join(S, "restore.sh"), env=dict(os.environ, RESTORE_ROOT=fresh, PERSIST_REPO_DIR=clone))
step("second restore is a no-op for snapshots", hashes(os.path.join(fresh, "three_way", "snapshots")) == before)
R["finished_utc"] = datetime.now(timezone.utc).isoformat(); R["passed"] = sum(s["pass"] for s in R["steps"]); R["total"] = len(R["steps"])
json.dump(R, open(os.path.join(LIVE, "audit", "recovery_raw.json"), "w"), indent=1)
print(f"{R['passed']}/{R['total']} recovery steps passed")
