"""Three-source, time-stamped statement collector (Tapetide, Screener.in, Indian Stock API via ARTHSCAN).

Each run writes ONE new immutable snapshot directory: snapshots/<UTC timestamp>_<label>/
  - raw responses exactly as received, plus manifest.json (url, fetch time UTC, HTTP status, bytes,
    sha256, source-reported timestamp where the source exposes one)
  - files are chmod 0444 and the directory 0555 after writing; an existing directory is never reused.

Sources (public interfaces only; robots.txt respected):
  tapetide  https://tapetide.com/stocks/{SYM}.md                    (robots: Allow /, /api/ disallowed and unused)
  screener  https://www.screener.in/company/{SYM}/consolidated/ and /company/{SYM}/   (robots: /company/ allowed)
  indianapi https://arthscan.me/stock/{SYM}/statements?stats=...    ARTHSCAN's statements endpoint, the same data
            ARTHSCAN serves as /v1/ext/statements with source "Indian Stock API (indianapi.in)"
            (robots: /api/ disallowed and unused; this path is outside it)
No credentials are used or read. Stops a host on HTTP 429.

usage: python collector.py LABEL SYM [SYM ...]
"""
import hashlib, json, os, random, re, stat, sys, time
from datetime import datetime, timezone
from scrapling.fetchers import Fetcher

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "snapshots")
DELAY = (4.0, 6.5)
ISAPI_STATS = ["quarter_results", "yoy_results", "balancesheet", "cashflow", "ratios"]
last, blocked = {}, set()

def utcnow(): return datetime.now(timezone.utc)

def fetch(host, url):
    if host in blocked: return None, "skipped: host returned 429 earlier", None
    wait = random.uniform(*DELAY) - (time.time() - last.get(host, 0))
    if wait > 0: time.sleep(wait)
    t = utcnow()
    try:
        r = Fetcher.get(url, stealthy_headers=True, timeout=40)
    except Exception as e:
        last[host] = time.time(); return t, f"error: {str(e)[:120]}", None
    last[host] = time.time()
    if r.status == 429: blocked.add(host)
    return t, r.status, r.body

def source_ts(source, body):
    """Timestamp the source itself reports, if any."""
    if not body: return None
    txt = body[:20000].decode("utf-8", "replace")
    if source == "tapetide":
        m = re.search(r'generated_at: "([^"]+)"', txt); a = re.search(r"as of ([^·\n]+IST)", body.decode("utf-8", "replace"))
        return {"page_generated_at": m.group(1) if m else None, "prices_as_of": a.group(1).strip() if a else None}
    return None   # Screener pages and ARTHSCAN's statements JSON carry no timestamp

def main(label, syms):
    ts = utcnow()
    sid = ts.strftime("%Y%m%dT%H%M%SZ") + "_" + re.sub(r"[^A-Za-z0-9+_-]", "", label)
    d = os.path.join(ROOT, sid)
    os.makedirs(d, exist_ok=False)                       # never reuse a snapshot directory
    manifest = {"snapshot_id": sid, "label": label, "started_at_utc": ts.isoformat(), "symbols": syms, "requests": []}
    for sym in syms:
        jobs = [("tapetide", f"https://tapetide.com/stocks/{sym}.md", f"tapetide_{sym}.md"),
                ("screener", f"https://www.screener.in/company/{sym}/consolidated/", f"screener_{sym}_consolidated.html")]
        jobs += [("indianapi", f"https://arthscan.me/stock/{sym}/statements?stats={s}", f"indianapi_{sym}_{s}.json") for s in ISAPI_STATS[:2]]
        jobs += [("screener", f"https://www.screener.in/company/{sym}/", f"screener_{sym}_standalone.html")]
        jobs += [("indianapi", f"https://arthscan.me/stock/{sym}/statements?stats={s}", f"indianapi_{sym}_{s}.json") for s in ISAPI_STATS[2:]]
        for source, url, fname in jobs:
            host = url.split("/")[2]
            t, st, body = fetch(host, url)
            rec = {"source": source, "symbol": sym, "url": url, "file": None, "fetched_at_utc": t.isoformat() if t else None,
                   "http_status": st, "bytes": len(body) if body else 0}
            if st == 200 and body:
                p = os.path.join(d, fname)
                with open(p, "xb") as f: f.write(body)  # 'x' = fail if the file already exists
                os.chmod(p, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
                rec.update(file=fname, sha256=hashlib.sha256(body).hexdigest(), source_reported_ts=source_ts(source, body))
            manifest["requests"].append(rec)
            print(f"{sym:11s} {source:9s} {st}", flush=True)
    manifest["finished_at_utc"] = utcnow().isoformat()
    manifest["hosts_blocked_429"] = sorted(blocked)
    mp = os.path.join(d, "manifest.json")
    with open(mp, "x") as f: json.dump(manifest, f, indent=1)
    os.chmod(mp, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    os.chmod(d, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    print("SNAPSHOT", sid)
    return sid

if __name__ == "__main__":
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2:])
