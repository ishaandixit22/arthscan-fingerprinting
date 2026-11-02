"""Three-way analysis over immutable snapshots: Tapetide (T), Screener.in (S), Indian Stock API via ARTHSCAN (I).

Reads snapshots/ and evidence/, never the network. Writes reports/three_way_fingerprinting/:
  timestamped_snapshots.csv, provider_comparison.csv, update_latency.csv, unexplained_differences.csv,
  source_attribution.json, executive_summary.md
Basis rule: pairs are compared only on the same basis (consolidated vs consolidated, standalone vs standalone).
"""
import csv, glob, json, os, re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "reports", "three_way_fingerprinting")
os.makedirs(OUT, exist_ok=True)
FP = os.path.join(os.path.dirname(HERE), "fingerprint")
_src = open(os.path.join(FP, "compare_engine.py")).read().split("# ---------------------------------------------------------------- comparison")[0]
_g = {"__file__": os.path.join(FP, "compare_engine.py")}
exec(_src, _g)
_derived_src = open(os.path.join(FP, "compare_engine.py")).read()
exec(re.search(r"(def classify.*?return \"mismatch\", d, rel\n)", _derived_src, re.S).group(1), _g)
exec(re.search(r"(def derived_checks.*?return res\n)", _derived_src, re.S).group(1), _g)
parse_num, classify, screener_tables, STATEMENTS, ROW_ALIASES = (_g[k] for k in ("parse_num", "classify", "screener_tables", "STATEMENTS", "ROW_ALIASES"))
derived_checks = _g["derived_checks"]

STAT_MAP = {"quarter_results": "quarterly", "yoy_results": "annual_pl", "balancesheet": "balance_sheet", "cashflow": "cash_flow", "ratios": "ratios"}
FOCUS = ["Other Income", "Depreciation", "Profit before tax", "Net Profit", "EPS in Rs", "Operating Profit", "Financing Profit"]
SYMS = ["RELIANCE", "PIIND", "ABCAPITAL", "WELSPUNLIV", "ZEEL", "JSL", "QUICKHEAL", "MOTHERSON", "TRENT", "CYIENT"]
PAIRS = [("T", "S"), ("I", "S"), ("T", "I")]
NAMES = {"T": "Tapetide", "S": "Screener.in", "I": "Indian Stock API (via ARTHSCAN)"}

def tapetide_tables_at(path):
    _g["CACHE"] = os.path.dirname(path)
    return _g["tapetide_tables"](os.path.basename(path)[len("tapetide_"):-3])

def indianapi_tables(d, sym):
    out = {}
    for stat, key in STAT_MAP.items():
        p = os.path.join(d, f"indianapi_{sym}_{stat}.json")
        if not os.path.exists(p): continue
        j = json.load(open(p), parse_float=lambda s: s, parse_int=lambda s: s)   # keep the source's own number text
        if not isinstance(j, dict) or "rows" not in j: continue
        out[key] = {"periods": j["periods"], "rows": [(r["label"], {k: ("" if v is None else str(v)) for k, v in r["values"].items()}) for r in j["rows"]]}
    return out

def load_snapshot(d):
    man = json.load(open(os.path.join(d, "manifest.json")))
    when = {r["file"]: r for r in man["requests"] if r.get("file")}
    data = {}
    for sym in man["symbols"]:
        e = {}
        tp = os.path.join(d, f"tapetide_{sym}.md")
        if os.path.exists(tp):
            b, t = tapetide_tables_at(tp); e["T"] = {"basis": b.lower(), "tabs": t, "meta": when.get(f"tapetide_{sym}.md")}
        for view in ("consolidated", "standalone"):
            sp = os.path.join(d, f"screener_{sym}_{view}.html")
            if os.path.exists(sp):
                lab, canon, tabs = screener_tables(sp)
                e[f"S_{view}"] = {"label": lab, "canonical": canon, "tabs": tabs, "meta": when.get(f"screener_{sym}_{view}.html")}
        it = indianapi_tables(d, sym)
        if it: e["I"] = {"tabs": it, "meta": when.get(f"indianapi_{sym}_quarter_results.json")}
        data[sym] = e
    return man, data

def screener_for_basis(e, basis):
    for view in ("consolidated", "standalone"):
        s = e.get(f"S_{view}")
        if s and (s["label"] == basis or (basis == "standalone" and s["label"] == "single_view")): return s
    return None

def compare_tabs(A, B):
    """Cell comparison of two {statement: table} dicts. Returns per-statement stats and cell list."""
    res, cells = {}, []
    for key, _, _ in STATEMENTS:
        X, Y = A.get(key), B.get(key)
        if not (X and Y): res[key] = None; continue
        xr = [ROW_ALIASES.get(r, r) for r, _ in X["rows"]]; yr = [ROW_ALIASES.get(r, r) for r, _ in Y["rows"]]
        xm = {ROW_ALIASES.get(r, r): v for r, v in X["rows"]}; ym = {ROW_ALIASES.get(r, r): v for r, v in Y["rows"]}
        cnt = Counter()
        for r in dict.fromkeys(yr + xr):
            for p in dict.fromkeys(Y["periods"] + X["periods"]):
                a = xm.get(r, {}).get(p) if p in X["periods"] else None
                b = ym.get(r, {}).get(p) if p in Y["periods"] else None
                cat, d, rel = classify(a, b)
                if cat is None: continue
                cat = cat.replace("tapetide", "a").replace("screener", "b")
                cnt[cat] += 1; cells.append((key, r, p, a, b, cat))
        common = [r for r in xr if r in yr]
        res[key] = {"cells": dict(cnt), "total": sum(cnt.values()),
                    "row_names_identical": set(xr) == set(yr), "row_order_identical": common == [r for r in yr if r in xr],
                    "periods_identical": X["periods"] == Y["periods"],
                    "latest_a": X["periods"][-1] if X["periods"] else None, "latest_b": Y["periods"][-1] if Y["periods"] else None}
    return res, cells

def pct(c): t = sum(c.values()); return round(100 * (c.get("exact", 0) + c.get("rounded", 0)) / t, 3) if t else None

# ------------------------------------------------------------------ load all snapshots
snap_dirs = sorted(d for d in glob.glob(os.path.join(HERE, "snapshots", "*")) if os.path.exists(os.path.join(d, "manifest.json")))
snaps = [(os.path.basename(d), *load_snapshot(d)) for d in snap_dirs]
base_id, base_man, base = next(s for s in snaps if s[0].endswith("_baseline"))

# ------------------------------------------------------------------ 1. timestamped_snapshots.csv (long format, every numeric cell)
with open(os.path.join(OUT, "timestamped_snapshots.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["snapshot_id", "label", "source", "symbol", "basis", "statement", "row", "period", "raw_value", "value", "decimals",
                "fetched_at_utc", "source_reported_ts", "sha256"])
    for sid, man, data in snaps:
        for sym, e in data.items():
            blocks = []
            if "T" in e: blocks.append(("tapetide", e["T"]["basis"], e["T"]["tabs"], e["T"]["meta"]))
            for view in ("consolidated", "standalone"):
                s = e.get(f"S_{view}")
                if s: blocks.append(("screener", s["label"], s["tabs"], s["meta"]))
            if "I" in e: blocks.append(("indianapi_arthscan_cache", "per-statement JSON (basis inferred in provider_comparison)", e["I"]["tabs"], e["I"]["meta"]))
            for source, basis, tabs, meta in blocks:
                for key, tab in tabs.items():
                    for r, vals in tab["rows"]:
                        for p in tab["periods"]:
                            raw = vals.get(p); v, dp = parse_num(raw)
                            if v is None: continue
                            w.writerow([sid, man["label"], source, sym, basis, key, r, p, raw, v, dp,
                                        (meta or {}).get("fetched_at_utc"), json.dumps((meta or {}).get("source_reported_ts")) if meta and meta.get("source_reported_ts") else "",
                                        (meta or {}).get("sha256", "")])

# ------------------------------------------------------------------ 2. provider_comparison.csv (baseline)
rows_pc, i_basis, cells_by = [], {}, {}
for sym in SYMS:
    e = base.get(sym, {})
    if "T" not in e: continue
    tb = e["T"]["basis"]; S = screener_for_basis(e, tb)
    # infer Indian Stock API basis by comparing with each Screener view separately
    best = None
    for view in ("consolidated", "standalone"):
        s = e.get(f"S_{view}")
        if not (s and "I" in e and s["tabs"]): continue
        r, _ = compare_tabs(e["I"]["tabs"], s["tabs"])
        c = Counter(); [c.update(v["cells"]) for v in r.values() if v]
        score = pct(c)
        if score is not None and (best is None or score > best[1]): best = (s["label"], score)
    i_basis[sym] = best[0] if best else None
    I_tabs = e["I"]["tabs"] if "I" in e else {}
    I_same = I_tabs if (best and (best[0] == tb or (tb == "standalone" and best[0] == "single_view"))) else None
    srcs = {"T": e["T"]["tabs"], "S": S["tabs"] if S else None, "I": I_same}
    for a, b in PAIRS:
        if not (srcs[a] and srcs[b]): continue
        res, cells = compare_tabs(srcs[a], srcs[b]); cells_by[(sym, a, b)] = cells
        for key, v in res.items():
            if not v: continue
            c = v["cells"]
            rows_pc.append({"snapshot_id": base_id, "symbol": sym, "basis": tb, "pair": f"{a}-{b}", "statement": key,
                            "cells": v["total"], "exact": c.get("exact", 0), "rounded": c.get("rounded", 0), "partial": c.get("partial", 0),
                            "mismatch": c.get("mismatch", 0), f"missing_first": c.get("missing_a", 0), "missing_second": c.get("missing_b", 0),
                            "match_pct": pct(c), "row_names_identical": v["row_names_identical"], "row_order_identical": v["row_order_identical"],
                            "periods_identical": v["periods_identical"], "latest_period_first": v["latest_a"], "latest_period_second": v["latest_b"]})
with open(os.path.join(OUT, "provider_comparison.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows_pc[0])); w.writeheader(); w.writerows(rows_pc)

def pair_total(a, b, stmt=None, rows=None, syms=None):
    c = Counter()
    for (sym, x, y), cells in cells_by.items():
        if (x, y) != (a, b) or (syms and sym not in syms): continue
        for key, r, p, va, vb, cat in cells:
            if stmt and key != stmt: continue
            if rows and r not in rows: continue
            c[cat] += 1
    return {"cells": sum(c.values()), **dict(c), "match_pct": pct(c)}

pair_summary = {f"{a}-{b}": {"all": pair_total(a, b), **{k: pair_total(a, b, stmt=k) for k, _, _ in STATEMENTS},
                             "focus_rows": pair_total(a, b, rows=FOCUS)} for a, b in PAIRS}

# cells where T and I agree with each other but not with S, and vice versa
triad = Counter(); triad_examples = defaultdict(list)
for sym in SYMS:
    ts = {(k, r, p): (va, vb) for k, r, p, va, vb, _ in cells_by.get((sym, "T", "S"), [])}
    is_ = {(k, r, p): (va, vb) for k, r, p, va, vb, _ in cells_by.get((sym, "I", "S"), [])}
    for key in ts.keys() & is_.keys():
        tv, sv = ts[key]; iv = is_[key][0]
        tn, sn, inn = (parse_num(x)[0] for x in (tv, sv, iv))
        if None in (tn, sn, inn): continue
        def eq(x, y, xr, yr): return classify(xr, yr)[0] in ("exact", "rounded")
        ts_, is__, ti = eq(tn, sn, tv, sv), eq(inn, sn, iv, sv), eq(tn, inn, tv, iv)
        k = "all_three_agree" if ts_ and is__ else "T=I, S differs" if ti and not ts_ else "T=S, I differs" if ts_ and not is__ else "I=S, T differs" if is__ and not ts_ else "all three differ"
        triad[k] += 1
        if k != "all_three_agree" and len(triad_examples[k]) < 40:
            triad_examples[k].append({"symbol": sym, "statement": key[0], "row": key[1], "period": key[2], "T": tv, "S": sv, "I": iv})

# ------------------------------------------------------------------ 3. fingerprints in Indian Stock API
fp_I = {"derived_rows_recompute": Counter(), "derived_rows_total": Counter(), "label_EPS_in_Rs": 0, "label_CFO_EBITDA": 0, "label_CFO_OP": 0,
        "ttm_column": 0, "half_year_bs_column_when_screener_has_it": [0, 0], "finance_row_order_matches": {}, "extra_old_quarter_like_tapetide": [],
        "ttm_equals_screener": 0, "ttm_checked": 0}
fp_T = {"label_CFO_OP": 0, "extra_old_quarter": []}
for sym in SYMS:
    e = base.get(sym, {})
    if "I" not in e: continue
    I = e["I"]["tabs"]; S = screener_for_basis(e, e["T"]["basis"]); T = e["T"]["tabs"]
    for key, tab in I.items():
        for name, p, ok in derived_checks(sym, key, tab):
            fp_I["derived_rows_total"][name.split(" =")[0]] += 1; fp_I["derived_rows_recompute"][name.split(" =")[0]] += ok
        labels = [r for r, _ in tab["rows"]]
        fp_I["label_EPS_in_Rs"] += "EPS in Rs" in labels
        fp_I["label_CFO_EBITDA"] += "CFO/EBITDA" in labels; fp_I["label_CFO_OP"] += "CFO/OP" in labels
    fp_T["label_CFO_OP"] += "CFO/OP" in [r for r, _ in T.get("cash_flow", {"rows": []})["rows"]]
    if "annual_pl" in I: fp_I["ttm_column"] += "TTM" in I["annual_pl"]["periods"]
    if S and "balance_sheet" in S["tabs"] and not S["tabs"]["balance_sheet"]["periods"][-1].startswith("Mar"):
        fp_I["half_year_bs_column_when_screener_has_it"][1] += 1
        fp_I["half_year_bs_column_when_screener_has_it"][0] += "balance_sheet" in I and I["balance_sheet"]["periods"][-1] == S["tabs"]["balance_sheet"]["periods"][-1]
    if S and "quarterly" in I:
        if [p for p in I["quarterly"]["periods"] if p not in S["tabs"]["quarterly"]["periods"]]: fp_I["extra_old_quarter_like_tapetide"].append(sym)
        if [p for p in T["quarterly"]["periods"] if p not in S["tabs"]["quarterly"]["periods"] and p == T["quarterly"]["periods"][0]]: fp_T["extra_old_quarter"].append(sym)
    if S and "annual_pl" in I and "TTM" in I["annual_pl"]["periods"]:
        iv = dict(I["annual_pl"]["rows"]).get("Sales", dict(I["annual_pl"]["rows"]).get("Revenue", {})).get("TTM")
        sv = dict(S["tabs"]["annual_pl"]["rows"]).get("Sales", dict(S["tabs"]["annual_pl"]["rows"]).get("Revenue", {})).get("TTM")
        if iv and sv: fp_I["ttm_checked"] += 1; fp_I["ttm_equals_screener"] += parse_num(iv)[0] == parse_num(sv)[0]
    if sym == "ABCAPITAL":
        for src, tabs in (("I", I), ("S", S["tabs"] if S else {}), ("T", T)):
            fp_I["finance_row_order_matches"][src] = [r for r, _ in tabs.get("quarterly", {"rows": []})["rows"]]
fp_I["derived_rows"] = {k: f'{fp_I["derived_rows_recompute"][k]}/{v}' for k, v in fp_I["derived_rows_total"].items()}
del fp_I["derived_rows_recompute"], fp_I["derived_rows_total"]

# ------------------------------------------------------------------ 4. unexplained differences from Phase 1
prev = [r for r in csv.DictReader(open(os.path.join(os.path.dirname(HERE), "reports", "tapetide_screener_validation", "detailed_mismatches.csv")))
        if r["explanation"] == "unexplained" and r["symbol"] in SYMS]
mcp = json.load(open(os.path.join(HERE, "evidence", "mcp_extracts.json")))
cell_src = {s: v.get("cell_source", {}) for s, v in mcp["tapetide_mcp_get_financials"].items() if isinstance(v, dict)}
def val(tabs, key, row, per):
    if not tabs or key not in tabs: return None
    m = {ROW_ALIASES.get(r, r): v for r, v in tabs[key]["rows"]}
    return m.get(row, {}).get(per) if per in tabs[key]["periods"] else None
ud = []
for r in prev:
    e = base[r["symbol"]]; S = screener_for_basis(e, e["T"]["basis"])
    tnow = val(e["T"]["tabs"], r["statement"], r["row"], r["period"]); snow = val(S["tabs"] if S else None, r["statement"], r["row"], r["period"])
    inow = val(e["I"]["tabs"] if "I" in e else None, r["statement"], r["row"], r["period"])
    flag = cell_src.get(r["symbol"], {}).get(r["row"], {}).get(r["period"]) if r["statement"] == "quarterly" else None
    eq = lambda x, y: x is not None and y is not None and classify(x, y)[0] in ("exact", "rounded")
    i_has_period = "I" in e and r["statement"] in e["I"]["tabs"] and r["period"] in e["I"]["tabs"][r["statement"]]["periods"]
    if r["category"].startswith("missing"):
        tpart = ("Tapetide shows 'n/m' (not meaningful)" if tnow == "n/m" else "now present on Tapetide" if tnow not in (None, "", "—") else "still missing on Tapetide")
        ipart = ("Indian Stock API has the value" if inow else "Indian Stock API has the period but not the value" if i_has_period else f"Indian Stock API has no {r['period']} yet")
        verdict = f"missing cell: {tpart}; {ipart}"
    elif flag == "filing":
        verdict = "Tapetide filing override (flagged cell_source=filing); compiled value = " + ("Screener = Indian Stock API" if eq(snow, inow) else "unclear")
    elif eq(tnow, inow) and not eq(tnow, snow):
        verdict = "Tapetide = Indian Stock API, Screener differs"
    elif eq(tnow, snow) and eq(snow, inow):
        verdict = ("agree within rounding (Tapetide shows fewer decimals)" if classify(tnow, snow)[0] == "rounded" else "resolved: all three now agree")
    elif eq(inow, snow) and not eq(tnow, snow):
        verdict = "Indian Stock API = Screener, Tapetide differs (no override flag checked)" if r["symbol"] not in cell_src else "Indian Stock API = Screener, Tapetide differs (not flagged as filing)"
    else:
        verdict = "all three differ / insufficient data"
    ud.append({"symbol": r["symbol"], "statement": r["statement"], "row": r["row"], "period": r["period"], "phase1_category": r["category"],
               "phase1_tapetide": r["tapetide_value"], "phase1_screener": r["screener_value"],
               "now_tapetide": tnow, "now_screener": snow, "now_indianapi": inow,
               "tapetide_cell_source": flag or ("not checked" if r["symbol"] not in cell_src else "not flagged"),
               "indianapi_equals_screener": eq(inow, snow), "indianapi_equals_tapetide": eq(inow, tnow), "verdict": verdict})
with open(os.path.join(OUT, "unexplained_differences.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(ud[0])); w.writeheader(); w.writerows(ud)

# ------------------------------------------------------------------ 5. update_latency.csv
events = {}
ep = os.path.join(HERE, "monitor", "events.json")
if os.path.exists(ep): events = json.load(open(ep))
lat = []
def latest(tabs, key):
    return tabs[key]["periods"][-1] if tabs and key in tabs and tabs[key]["periods"] else None
def ttm_end(tabs):
    """Which quarter the TTM column ends on, inferred from the source's own quarterly Sales/Revenue."""
    try:
        q = dict(tabs["quarterly"]["rows"]); a = dict(tabs["annual_pl"]["rows"]); per = tabs["quarterly"]["periods"]
        row = "Sales" if "Sales" in q else "Revenue"
        ttm = parse_num(a[row]["TTM"])[0]
        for k in range(0, 3):
            ps = per[len(per) - 4 - k: len(per) - k]
            if len(ps) == 4 and abs(sum(parse_num(q[row][x])[0] for x in ps) - ttm) <= 2: return ps[-1]
    except Exception: return None
    return "unmatched"
for sid, man, data in snaps:
    for sym, e in data.items():
        S = screener_for_basis(e, e["T"]["basis"]) if "T" in e else None
        ev = events.get(sym, {})
        t0 = ev.get("t0_exchange_utc")
        for src, tabs, meta in (("tapetide", e.get("T", {}).get("tabs"), e.get("T", {}).get("meta")),
                                ("screener", S["tabs"] if S else None, S["meta"] if S else None),
                                ("indianapi_arthscan_cache", e.get("I", {}).get("tabs"), e.get("I", {}).get("meta"))):
            if not tabs: continue
            fa = (meta or {}).get("fetched_at_utc")
            lq = latest(tabs, "quarterly")
            mins = None
            if t0 and fa: mins = round((datetime.fromisoformat(fa) - datetime.fromisoformat(t0)).total_seconds() / 60, 1)
            q = ev.get("new_quarter") or (latest(S["tabs"], "quarterly") if S else None)
            filled = eqs = total = 0
            if q and "quarterly" in tabs and S and "quarterly" in S["tabs"]:
                tm = {ROW_ALIASES.get(r, r): v for r, v in tabs["quarterly"]["rows"]}
                for r, sv in S["tabs"]["quarterly"]["rows"]:
                    total += 1; v = tm.get(r, {}).get(q) if q in tabs["quarterly"]["periods"] else None
                    if parse_num(v)[0] is not None:
                        filled += 1; eqs += classify(v, sv.get(q))[0] in ("exact", "rounded")
            lat.append({"snapshot_id": sid, "label": man["label"], "symbol": sym, "source": src, "fetched_at_utc": fa,
                        "quarter_checked": q, "rows_filled": f"{filled}/{total}", "rows_equal_screener": f"{eqs}/{total}",
                        "latest_quarter": lq, "latest_annual": latest(tabs, "annual_pl"), "latest_balance_sheet": latest(tabs, "balance_sheet"),
                        "ttm_ends_on_quarter": ttm_end(tabs), "t0_exchange_utc": t0 or "", "minutes_after_t0": "" if mins is None else mins,
                        "has_new_quarter": "" if not ev.get("new_quarter") else (lq == ev["new_quarter"]),
                        "source_reported_ts": json.dumps((meta or {}).get("source_reported_ts")) if meta and meta.get("source_reported_ts") else ""})
with open(os.path.join(OUT, "update_latency.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(lat[0])); w.writeheader(); w.writerows(lat)

first_seen = {}
for sym, ev in events.items():
    nq = ev.get("new_quarter")
    for src in ("tapetide", "screener", "indianapi_arthscan_cache"):
        hits = [r for r in lat if r["symbol"] == sym and r["source"] == src and r["latest_quarter"] == nq and r["t0_exchange_utc"]]
        first_seen.setdefault(sym, {})[src] = min((r["minutes_after_t0"] for r in hits), default=None)

# cross-sectional staleness at baseline
stale = {}
for sym in SYMS:
    rs = {r["source"]: r for r in lat if r["snapshot_id"] == base_id and r["symbol"] == sym}
    stale[sym] = {s: {"latest_quarter": v["latest_quarter"], "latest_balance_sheet": v["latest_balance_sheet"], "ttm_ends_on": v["ttm_ends_on_quarter"]} for s, v in rs.items()}

ref = json.load(open(os.path.join(HERE, "evidence", "latency_reference.json")))
for sym, v in ref.items():
    if sym.startswith("_") or "new_quarter" not in v: continue
    t0 = v["exchange_filing"].get("time_utc")
    for src in ("tapetide", "screener", "indianapi_arthscan_cache"):
        o = v.get(src, {}); at = o.get("fetched_at") or o.get("observed_at", "")
        at_iso = at.split(" ")[0].replace("Z", "+00:00") if at else None
        mins = round((datetime.fromisoformat(at_iso) - datetime.fromisoformat(t0.replace("Z", "+00:00"))).total_seconds() / 60, 1) if (t0 and at_iso and len(at_iso) > 16) else ""
        lat.append({"snapshot_id": "reference (MCP / Phase 1)", "label": "cross-sectional reference", "symbol": sym, "source": src, "fetched_at_utc": at,
                    "quarter_checked": v["new_quarter"], "rows_filled": "", "rows_equal_screener": "",
                    "latest_quarter": o.get("latest_quarter", v["new_quarter"] if o.get("has_new_quarter") else ""), "latest_annual": "", "latest_balance_sheet": "",
                    "ttm_ends_on_quarter": "", "t0_exchange_utc": t0 or v["exchange_filing"].get("date", ""), "minutes_after_t0": mins,
                    "has_new_quarter": o.get("has_new_quarter", ""), "source_reported_ts": v["exchange_filing"]["source"]})
with open(os.path.join(OUT, "update_latency.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(lat[0])); w.writeheader(); w.writerows(lat)
json.dump({"base": base_id, "latency_reference": ref, "snapshots": [s[0] for s in snaps], "i_basis": i_basis, "pair_summary": pair_summary, "triad": dict(triad),
           "triad_examples": triad_examples, "fingerprints_indianapi": fp_I, "fingerprints_tapetide": fp_T, "unexplained": ud,
           "staleness_at_baseline": stale, "events": events, "first_seen_minutes_after_t0": first_seen},
          open(os.path.join(HERE, "evidence", "analysis_results.json"), "w"), indent=1, default=str)
print(json.dumps({"i_basis": i_basis, "pairs": {k: v["all"] for k, v in pair_summary.items()},
                  "focus": {k: v["focus_rows"] for k, v in pair_summary.items()}, "triad": dict(triad),
                  "fp_I": {k: v for k, v in fp_I.items() if k != "finance_row_order_matches"}, "fp_T": fp_T,
                  "abcap_row_order": fp_I["finance_row_order_matches"], "stale": stale}, indent=1, default=str))
print("\nUNEXPLAINED:"); [print(" ", u["symbol"], u["statement"], u["row"], u["period"], "T", u["now_tapetide"], "S", u["now_screener"], "I", u["now_indianapi"], "|", u["tapetide_cell_source"], "|", u["verdict"]) for u in ud]
