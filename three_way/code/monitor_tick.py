"""Results-release monitor. One tick = poll NSE's official RSS feeds once, record T0, take due checkpoint snapshots.

T0 = the exchange's own pubDate (IST) of the first results filing for the company (not our detection time).
Checkpoints: T0 snapshot at detection, then T+30m, T+2h, T+24h, T+48h (each taken at the first tick at/after due;
the actual delay is recorded). Feeds: nsearchives.nseindia.com/content/RSS/{Financial_Results,Online_announcements}.xml
(NSE robots.txt: Allow /; feed TTL 5 min, so polling is never faster than every 5 minutes). Stops on HTTP 429.

usage: python monitor_tick.py                 one tick
       python monitor_tick.py --loop MINUTES  tick every 5 minutes for MINUTES (max 115)
"""
import fcntl, glob, hashlib, json, os, re, subprocess, sys, time
from datetime import datetime, timedelta, timezone
from scrapling.fetchers import Fetcher

HERE = os.path.dirname(os.path.abspath(__file__))
MON = os.path.join(HERE, "monitor"); os.makedirs(MON, exist_ok=True)
EVENTS = os.path.join(MON, "events.json"); LOG = os.path.join(MON, "ticks.jsonl")
IST = timezone(timedelta(hours=5, minutes=30))
WATCH = {"MOTHERSON": {"name": r"samvardhana motherson", "new_quarter": "Sep 2026"},
         "PIIND": {"name": r"\bpi industries", "new_quarter": "Sep 2026"}}
FEEDS = ["https://nsearchives.nseindia.com/content/RSS/Financial_Results.xml",
         "https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml"]
SINCE = datetime(2026, 11, 2, tzinfo=IST).astimezone(timezone.utc)   # ignore older filings (feeds keep stale items)
CHECKPOINTS = [("T+30m", timedelta(minutes=30)), ("T+2h", timedelta(hours=2)), ("T+24h", timedelta(hours=24)), ("T+48h", timedelta(hours=48))]
RESULT_RX = re.compile(r"financial result|outcome of board meeting|unaudited|audited results|results? for the (quarter|period)", re.I)
INTIMATION_RX = re.compile(r"board meeting to be held|to consider and approve|intimation|will be held", re.I)

INDEX = os.path.join(MON, "snapshot_index.jsonl")
LOCK = os.path.join(MON, ".lock")

def now(): return datetime.now(timezone.utc)

def acquire_lock():
    """Exclusive, non-blocking: a second tick (hourly + loop overlap) exits instead of duplicating work."""
    fh = open(LOCK, "w")
    try: fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError: return None
    return fh

def index_snapshot(sid, label):
    mp = os.path.join(HERE, "snapshots", sid, "manifest.json")
    if not (sid and os.path.exists(mp)): return
    with open(INDEX, "a") as f:
        f.write(json.dumps({"snapshot_id": sid, "label": label, "indexed_at_utc": now().isoformat(),
                            "manifest_sha256": hashlib.sha256(open(mp, "rb").read()).hexdigest()}) + "\n")

def incomplete_snapshots():
    """Directories without a manifest were interrupted mid-write; they are kept (immutable) and reported, never reused."""
    return sorted(os.path.basename(d) for d in glob.glob(os.path.join(HERE, "snapshots", "*")) if not os.path.exists(os.path.join(d, "manifest.json")))

def persist(note):
    """Optional: push state + snapshots to a git remote if PERSIST_REPO_DIR is set (credentials from the environment's git config; never printed)."""
    repo = os.environ.get("PERSIST_REPO_DIR")
    if not repo or not os.path.isdir(os.path.join(repo, ".git")): return "persist: not configured"
    r = subprocess.run(["bash", os.path.join(HERE, "persist.sh"), note], capture_output=True, text=True, timeout=300)
    return "persist: ok" if r.returncode == 0 else f"persist: failed ({r.returncode})"
def load(p, d): return json.load(open(p)) if os.path.exists(p) else d
def save(p, o):
    tmp = p + ".tmp"; json.dump(o, open(tmp, "w"), indent=1); os.replace(tmp, p)

def poll():
    items, statuses = [], {}
    for url in FEEDS:
        try:
            r = Fetcher.get(url, timeout=30)
            statuses[url] = r.status
            if r.status == 429: return None, statuses
            if r.status != 200: continue
            for it in re.findall(r"<item>(.*?)</item>", r.body.decode("utf-8", "replace"), re.S):
                g = lambda tag: re.sub(r"\s+", " ", "".join(re.findall(rf"<{tag}>(.*?)</{tag}>", it, re.S))).strip()
                items.append({"feed": url.rsplit("/", 1)[1], "title": g("title"), "description": g("description"), "link": g("link"), "pubDate": g("pubDate")})
        except Exception as e:
            statuses[url] = f"error: {str(e)[:80]}"
        time.sleep(2)
    return items, statuses

def parse_pub(s):
    for fmt in ("%d-%b-%Y %H:%M:%S", "%a, %d %b %Y %H:%M:%S %z", "%d-%b-%Y %H:%M"):
        try:
            d = datetime.strptime(s, fmt)
            return (d if d.tzinfo else d.replace(tzinfo=IST)).astimezone(timezone.utc)
        except ValueError: pass
    return None

def snapshot(label, sym):
    out = subprocess.run([sys.executable, os.path.join(HERE, "collector.py"), label, sym], capture_output=True, text=True, timeout=900)
    m = re.search(r"SNAPSHOT (\S+)", out.stdout)
    blocked = "429" in out.stdout
    return (m.group(1) if m else None), blocked

def tick():
    ev = load(EVENTS, {}); t = now(); rec = {"tick_utc": t.isoformat(), "new_t0": [], "checkpoints": []}
    if ev.get("_stopped_429"):
        print("STOPPED: an earlier HTTP 429; not polling"); return ev
    items, st = poll(); rec["feed_status"] = st
    if items is None:
        ev["_stopped_429"] = t.isoformat(); save(EVENTS, ev); print("HTTP 429 from NSE feed: stopping monitor"); return ev
    for sym, w in WATCH.items():
        if sym in ev: continue
        hits = [i for i in items if re.search(w["name"], i["title"], re.I) and (parse_pub(i["pubDate"]) or t) >= SINCE and (i["feed"] == "Financial_Results.xml" or
                (RESULT_RX.search(i["description"]) and not INTIMATION_RX.search(i["description"])))]
        if not hits: continue
        hits.sort(key=lambda i: parse_pub(i["pubDate"]) or t)
        first = hits[0]; t0 = parse_pub(first["pubDate"]) or t
        ev[sym] = {"t0_exchange_raw": first["pubDate"], "t0_exchange_utc": t0.isoformat(), "t0_assumed_tz": "IST (+05:30), per NSE feed convention",
                   "detected_at_utc": t.isoformat(), "detection_lag_min": round((t - t0).total_seconds() / 60, 1), "item": first,
                   "new_quarter": w["new_quarter"], "checkpoints": {}}
        sid, blocked = snapshot(f"T0_{sym}", sym); index_snapshot(sid, f"T0_{sym}")
        ev[sym]["checkpoints"]["T0"] = {"due_utc": t0.isoformat(), "taken_utc": now().isoformat(), "snapshot_id": sid}
        for lab, dt in CHECKPOINTS: ev[sym]["checkpoints"][lab] = {"due_utc": (t0 + dt).isoformat(), "taken_utc": None, "snapshot_id": None}
        save(EVENTS, ev); rec["new_t0"].append(sym); print(f"NEW_T0 {sym} exchange {first['pubDate']} IST, snapshot {sid}")
        if blocked: ev["_stopped_429"] = now().isoformat(); save(EVENTS, ev); print("HTTP 429 during snapshot: stopping"); return ev
    for sym, e in ev.items():
        if sym.startswith("_"): continue
        for lab, cp in e["checkpoints"].items():
            if cp["taken_utc"] or datetime.fromisoformat(cp["due_utc"]) > now(): continue
            sid, blocked = snapshot(f"{lab}_{sym}", sym); index_snapshot(sid, f"{lab}_{sym}")
            cp.update(taken_utc=now().isoformat(), snapshot_id=sid,
                      late_by_min=round((now() - datetime.fromisoformat(cp["due_utc"])).total_seconds() / 60, 1))
            save(EVENTS, ev); rec["checkpoints"].append(f"{sym}:{lab}"); print(f"CHECKPOINT {sym} {lab} snapshot {sid} late_by {cp['late_by_min']} min")
            if blocked: ev["_stopped_429"] = now().isoformat(); save(EVENTS, ev); print("HTTP 429 during snapshot: stopping"); return ev
    rec["incomplete_snapshot_dirs"] = incomplete_snapshots()
    if rec["new_t0"] or rec["checkpoints"]: rec["persist"] = persist(f"monitor: {rec['new_t0'] + rec['checkpoints']}")
    with open(LOG, "a") as f: f.write(json.dumps(rec) + "\n")
    pend = [(s, l, c["due_utc"]) for s, e in ev.items() if not s.startswith("_") for l, c in e["checkpoints"].items() if not c["taken_utc"]]
    waiting = [s for s in WATCH if s not in ev]
    print(f"TICK {t.isoformat()} feeds={list(st.values())} waiting_for_T0={waiting} pending={pend}")
    if not waiting and not pend: print("ALL_DONE")
    return ev

if __name__ == "__main__":
    lock = acquire_lock()
    if lock is None: print("BUSY: another tick holds the lock; exiting without work"); sys.exit(0)
    if len(sys.argv) == 3 and sys.argv[1] == "--loop":
        end = time.time() + min(float(sys.argv[2]), 115) * 60
        while time.time() < end:
            ev = tick()
            if ev.get("_stopped_429"): break
            time.sleep(max(0, min(300, end - time.time())))
    else:
        tick()
