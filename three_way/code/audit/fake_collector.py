"""Test double for collector.py: writes a real snapshot dir + manifest whose outcome is set by FAKE_MODE.
FAKE_MODE: complete | fail | 429 | complete429id (complete, but the snapshot id contains '429')."""
import json, os, sys, time, hashlib
from datetime import datetime, timezone
HERE = os.path.dirname(os.path.abspath(__file__))
mode = os.environ.get("FAKE_MODE", "complete"); label, sym = sys.argv[1], sys.argv[2]
ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + f"{time.time_ns() % 1000000:06d}"
if mode == "complete429id": ts = "20261104T142901Z"
sid = f"{ts}_{label}"; d = os.path.join(HERE, "snapshots", sid); os.makedirs(d, exist_ok=False)
reqs = []
for src in ("tapetide", "screener", "indianapi"):
    if mode == "fail": reqs.append({"source": src, "symbol": sym, "http_status": "error: simulated network failure", "file": None})
    elif mode == "429" and src == "screener": reqs.append({"source": src, "symbol": sym, "http_status": 429, "file": None})
    else:
        body = f"{src} {sym} {label}".encode(); fn = f"{src}_{sym}.txt"
        open(os.path.join(d, fn), "xb").write(body); reqs.append({"source": src, "symbol": sym, "http_status": 200, "file": fn, "sha256": hashlib.sha256(body).hexdigest()})
json.dump({"snapshot_id": sid, "label": label, "symbols": [sym], "requests": reqs, "hosts_blocked_429": ["www.screener.in"] if mode == "429" else []},
          open(os.path.join(d, "manifest.json"), "x"))
with open(os.path.join(HERE, "monitor", "fake_collector_calls.log"), "a") as f: f.write(sid + "\n")
print("SNAPSHOT", sid)
