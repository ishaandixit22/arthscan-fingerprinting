"""Tapetide vs Screener.in financial-statement fingerprint validation.

Reads only the local cache written by fetch_sources.py (no network). Writes to reports/tapetide_screener_validation/.

Basis rule: Tapetide publishes one basis per company ("EPS basis: Consolidated|Standalone").
Each comparison pairs it ONLY with the Screener page whose own label shows the same basis.
Consolidated figures are never compared with standalone figures.

Cell categories (thresholds recorded in source_evidence.json):
  exact            numerically equal as displayed (formatting such as 13.7 vs 13.70 ignored, tracked separately)
  rounded          one value is the other rounded to fewer decimals (|d| <= 0.5 * 10^-min_dp)
  partial          relative difference <= 2%
  mismatch         anything else
  missing_tapetide / missing_screener   cell present on only one side
"""
import csv, html, json, os, re
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
OUT = os.path.join(os.path.dirname(HERE), "reports", "tapetide_screener_validation")
os.makedirs(OUT, exist_ok=True)
PARTIAL_REL = 0.02
STATEMENTS = [("quarterly", "Quarterly Results", "quarters"),
              ("annual_pl", "Profit & Loss", "profit-loss"),
              ("balance_sheet", "Balance Sheet", "balance-sheet"),
              ("cash_flow", "Cash Flow", "cash-flow"),
              ("ratios", "Ratios", "ratios")]
MISSING_TOKENS = {"", "—", "-", "–", "NA", "N/A", "null", "None"}

# ---------------------------------------------------------------- parsing
def parse_num(raw):
    s = (raw or "").strip()
    if s in MISSING_TOKENS: return None, None
    s2 = s.replace(",", "").replace("%", "").replace("₹", "").strip()
    try: v = float(s2)
    except ValueError: return None, None
    dp = len(s2.split(".")[1]) if "." in s2 else 0
    return (0.0 if v == 0 else v), dp

def tapetide_tables(sym):
    md = open(f"{CACHE}/tapetide_{sym}.md", encoding="utf-8").read()
    basis = (re.findall(r"EPS basis: (\w+)", md) or ["Unknown"])[0]
    fs = md.split("## Financial Statements", 1)[-1]
    fs = re.split(r"\n## (?!#)", fs)[0]
    out = {}
    for key, title, _ in STATEMENTS:
        m = re.search(r"### " + re.escape(title) + r"\n(.*?)(?=\n### |\Z)", fs, re.S)
        if not m: continue
        lines = [l for l in m.group(1).splitlines() if l.startswith("|")]
        if len(lines) < 3: continue
        head = [c.strip() for c in lines[0].strip("|").split("|")]
        periods = head[1:]
        rows = []
        for l in lines[2:]:
            cells = [c.strip() for c in l.strip("|").split("|")]
            rows.append((cells[0], dict(zip(periods, cells[1:]))))
        out[key] = {"periods": periods, "rows": rows}
    return basis, out

ROW_ALIASES = {"CFO/OP": "CFO/EBITDA"}   # Tapetide label -> Screener label (same definition per Screener tooltip)
def text(node): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", node))).strip()

def screener_tables(path):
    t = open(path, encoding="utf-8", errors="replace").read()
    canonical = (re.findall(r'<link rel="canonical" href="([^"]+)"', t) or [""])[0]
    out, labels = {}, {}
    for key, _, sec in STATEMENTS:
        m = re.search(r'<section id="' + sec + r'"(.*?)</section>', t, re.S)
        if not m: continue
        body = m.group(1)
        head_txt = text(body[:1500])
        tb = re.search(r'<table class="data-table[^"]*"(.*?)</table>', body, re.S)
        if not tb: continue
        tb = tb.group(1)
        periods = [text(x) for x in re.findall(r"<th[^>]*>(.*?)</th>", re.search(r"<thead>(.*?)</thead>", tb, re.S).group(1), re.S)][1:]
        if not periods: continue          # empty shell: Screener has no data for this basis
        labels[key] = ("consolidated" if "Consolidated Figures" in head_txt else
                       "standalone" if "Standalone Figures" in head_txt else
                       "single_view" if "Figures in" in head_txt else "unknown")
        rows = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", re.search(r"<tbody>(.*?)</tbody>", tb, re.S).group(1), re.S):
            tr = re.sub(r'<span class="has-tooltip">.*?</span>\s*</span>', " ", tr, flags=re.S)
            tds = [text(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if not tds: continue
            name = re.sub(r"\s*\+$", "", tds[0].replace("\xa0", " ")).strip()
            if name == "Raw PDF": continue
            rows.append((name, dict(zip(periods, tds[1:]))))
        out[key] = {"periods": periods, "rows": rows}
    vals = set(labels.values()) - {"unknown"}
    page_basis = vals.pop() if len(vals) == 1 else ("mixed" if vals else "unknown")
    return page_basis, canonical, out

# ---------------------------------------------------------------- comparison
def classify(tr, sr):
    tv, tdp = parse_num(tr); sv, sdp = parse_num(sr)
    if tv is None and sv is None: return None, None, None
    if tv is None: return "missing_tapetide", None, None
    if sv is None: return "missing_screener", None, None
    d = abs(tv - sv)
    rel = d / abs(sv) if sv else (0.0 if d == 0 else float("inf"))
    if d < 1e-9: return "exact", d, rel
    if d <= 0.5 * 10 ** (-min(tdp, sdp)) + 1e-9: return "rounded", d, rel
    if rel <= PARTIAL_REL: return "partial", d, rel
    return "mismatch", d, rel

def derived_checks(sym, key, tab):
    """Recompute Screener-style derived rows from the Tapetide table's own numbers."""
    rows = dict(tab["rows"]); res = []
    def n(r, p): return parse_num(rows.get(r, {}).get(p))[0]
    for p in tab["periods"]:
        if key == "balance_sheet":
            tl, ec, rs, br, ol = (n(x, p) for x in ["Total Liabilities", "Equity Capital", "Reserves", "Borrowings", "Other Liabilities"])
            if None not in (tl, ec, rs, br, ol):
                res.append(("Other Liabilities = Total Liabilities - Equity - Reserves - Borrowings", p, abs(tl - ec - rs - br - ol) <= 2))
            ta, fa, cw, iv, oa = (n(x, p) for x in ["Total Assets", "Fixed Assets", "CWIP", "Investments", "Other Assets"])
            if None not in (ta, fa, cw, iv, oa):
                res.append(("Other Assets = Total Assets - Fixed Assets - CWIP - Investments", p, abs(ta - fa - cw - iv - oa) <= 2))
        if key in ("quarterly", "annual_pl"):
            sa, ex, op, opm = (n(x, p) for x in ["Sales", "Expenses", "Operating Profit", "OPM %"])
            if None not in (sa, ex, op):
                res.append(("Operating Profit = Sales - Expenses", p, abs(sa - ex - op) <= 2))
            if None not in (sa, op, opm) and sa:
                dp = parse_num(rows["OPM %"][p])[1]
                res.append(("OPM % = Operating Profit / Sales, rounded as displayed", p, abs(round(op / sa * 100, dp) - opm) <= 10 ** -dp + 1e-9))
    return res

sample = json.load(open(os.path.join(HERE, "universe", "sample.json")))["sample"]
cells, stock_rows, mismatches, evidence_stock = [], [], [], {}
fingerprints = Counter(); derived = defaultdict(lambda: [0, 0])

for s in sample:
    sym = s["symbol"]
    t_basis, t_tabs = tapetide_tables(sym)
    pages = {}
    for view in ("consolidated", "standalone"):
        pb, canon, tabs = screener_tables(f"{CACHE}/screener_{sym}_{view}.html")
        pages[view] = {"label": pb, "canonical": canon, "tabs": tabs}
    canon = pages["consolidated"]["canonical"]
    screener_default = "consolidated" if canon.rstrip("/").endswith("/consolidated") else "standalone"
    has_consol = pages["consolidated"]["label"] == "consolidated"
    want = t_basis.lower()
    # same-basis Screener page only
    match_page = None
    for view, pg in pages.items():
        if pg["label"] == want or (want == "standalone" and pg["label"] == "single_view"):
            match_page = view; break
    ev = {"tier": s["tier"], "industry": s["industry"], "tapetide_basis": t_basis,
          "screener_labels": {v: p["label"] for v, p in pages.items()}, "screener_canonical": canon,
          "screener_default_basis": screener_default, "screener_has_consolidated": has_consol,
          "tapetide_basis_equals_screener_default": want == screener_default,
          "screener_page_compared": match_page, "statements": {}}
    if not match_page:
        ev["note"] = "no same-basis Screener view; not compared"
        evidence_stock[sym] = ev; continue
    s_tabs = pages[match_page]["tabs"]
    for key, title, _ in STATEMENTS:
        T, S = t_tabs.get(key), s_tabs.get(key)
        st = {"in_tapetide": bool(T), "in_screener": bool(S)}
        st_renamed = []
        if not (T and S):
            ev["statements"][key] = st; continue
        renamed = [r for r, _ in T["rows"] if r in ROW_ALIASES]
        if renamed:
            T = {"periods": T["periods"], "rows": [(ROW_ALIASES.get(r, r), v) for r, v in T["rows"]]}
            for r in renamed: fingerprints[f"Tapetide renames '{r}' -> Screener '{ROW_ALIASES[r]}' ({key})"] += 1
        st_renamed = renamed
        trows = [r for r, _ in T["rows"]]; srows = [r for r, _ in S["rows"]]
        common = [r for r in trows if r in srows]
        st.update({
            "row_names_identical": trows == srows or set(trows) == set(srows),
            "rows_only_tapetide": [r for r in trows if r not in srows],
            "rows_only_screener": [r for r in srows if r not in trows],
            "row_order_identical_on_common_rows": common == [r for r in srows if r in trows],
            "periods_tapetide": T["periods"], "periods_screener": S["periods"],
            "periods_identical": T["periods"] == S["periods"],
            "periods_only_tapetide": [p for p in T["periods"] if p not in S["periods"]],
            "periods_only_screener": [p for p in S["periods"] if p not in T["periods"]],
        })
        tmap, smap = dict(T["rows"]), dict(S["rows"])
        cnt = Counter(); dp_same = dp_diff = 0
        for r in sorted(set(trows) | set(srows), key=lambda x: (srows + trows).index(x)):
            for p in sorted(set(T["periods"]) | set(S["periods"]), key=lambda x: (S["periods"] + T["periods"]).index(x)):
                traw = tmap.get(r, {}).get(p) if r in tmap and p in T["periods"] else None
                sraw = smap.get(r, {}).get(p) if r in smap and p in S["periods"] else None
                cat, d, rel = classify(traw, sraw)
                if cat is None: continue
                cnt[cat] += 1
                if cat in ("exact", "rounded"):
                    tdp, sdp = parse_num(traw)[1], parse_num(sraw)[1]
                    if tdp == sdp: dp_same += 1
                    else: dp_diff += 1
                cells.append({"symbol": sym, "basis": want, "statement": key, "row": r, "period": p, "category": cat})
                if cat != "exact":
                    mismatches.append({"symbol": sym, "tier": s["tier"], "basis": want, "statement": key, "row": r,
                                       "period": p, "tapetide_value": traw, "screener_value": sraw, "category": cat,
                                       "abs_diff": "" if d is None else round(d, 6),
                                       "rel_diff_pct": "" if rel is None or rel == float("inf") else round(rel * 100, 4)})
        st["rows_renamed_by_tapetide"] = st_renamed
        st["empty_rows_dropped_by_tapetide"] = [r for r in srows if r not in trows and all(parse_num(v)[0] is None for v in smap[r].values())]
        st["cells"] = dict(cnt); st["decimal_places_identical"] = dp_same; st["decimal_places_differ_but_equal"] = dp_diff
        for name, p, ok in derived_checks(sym, key, T):
            derived[name][0] += ok; derived[name][1] += 1
        ev["statements"][key] = st
        total = sum(cnt.values())
        stock_rows.append({"symbol": sym, "tier": s["tier"], "industry": s["industry"], "basis": want,
                           "screener_page": match_page, "statement": key, "cells_compared": total,
                           "exact": cnt["exact"], "rounded": cnt["rounded"], "partial": cnt["partial"],
                           "mismatch": cnt["mismatch"], "missing_tapetide": cnt["missing_tapetide"],
                           "missing_screener": cnt["missing_screener"],
                           "match_pct": round(100 * (cnt["exact"] + cnt["rounded"]) / total, 2) if total else "",
                           "exact_pct": round(100 * cnt["exact"] / total, 2) if total else "",
                           "row_names_identical": st["row_names_identical"],
                           "row_order_identical": st["row_order_identical_on_common_rows"],
                           "periods_identical": st["periods_identical"],
                           "periods_tapetide": len(T["periods"]), "periods_screener": len(S["periods"]),
                           "first_period_t": T["periods"][0], "last_period_t": T["periods"][-1],
                           "first_period_s": S["periods"][0], "last_period_s": S["periods"][-1]})
        # fingerprints
        if key == "balance_sheet" and T["periods"] and not T["periods"][-1].startswith("Mar") and T["periods"][-1] in S["periods"]:
            fingerprints["half-year column inside annual balance sheet (same label on both)"] += 1
        if key == "annual_pl" and "TTM" in T["periods"] and "TTM" in S["periods"]:
            fingerprints["TTM column in annual P&L on both"] += 1
        if "EPS in Rs" in trows and "EPS in Rs" in srows:
            fingerprints[f"'EPS in Rs' row label ({key})"] += 1
        for fr in ("Financing Profit", "Financing Margin %", "Revenue"):
            if fr in trows and fr in srows: fingerprints[f"finance-company layout row '{fr}' ({key})"] += 1
    evidence_stock[sym] = ev

# ---------------------------------------------------------------- explanations
def explain(m):
    ev = evidence_stock[m["symbol"]]["statements"][m["statement"]]
    pt, ps = ev["periods_tapetide"], ev["periods_screener"]
    if m["category"] == "missing_screener" and m["period"] in pt and m["period"] not in ps and m["period"] in (pt[0], pt[-1]):
        return "coverage_window (period outside Screener's display window)"
    if m["category"] == "missing_tapetide" and m["period"] in ps and m["period"] not in pt and m["period"] in (ps[0], ps[-1]):
        return "coverage_window/refresh_lag (newest or oldest period not on Tapetide)"
    if m["period"] == "TTM":
        e_ = evidence_stock[m["symbol"]]
        q_ = e_["statements"].get("quarterly", {})
        whole_stock_lag = q_.get("periods_tapetide", [None])[-1] != q_.get("periods_screener", [None])[-1]
        if whole_stock_lag: return "refresh_lag (Tapetide's latest quarter is older than Screener's)"
        lag = e_.get("tapetide_annual_ttm_lags_one_quarter")
        if lag: return "refresh_lag (Tapetide TTM = Screener-style TTM one quarter earlier)"
    if m["row"] == "EPS in Rs" and m["category"] == "mismatch":
        tv, sv = parse_num(m["tapetide_value"])[0], parse_num(m["screener_value"])[0]
        if tv and sv:
            r = tv / sv
            for f in (2, 3, 5, 10, 30):
                for fac in (f, 1 / f):
                    if abs(r / fac - 1) < 0.02: return f"eps_share_basis_factor (Tapetide/Screener = {round(fac, 4)})"
    return "unexplained"

for s_ in sample:
    sym = s_["symbol"]
    try:
        b, T = tapetide_tables(sym)
        q = dict(T["quarterly"]["rows"]); per = T["quarterly"]["periods"]; pl = dict(T["annual_pl"]["rows"])
        ttm = parse_num(pl["Sales"]["TTM"])[0]
        s4 = sum(parse_num(q["Sales"][x])[0] for x in per[-5:-1]); s4n = sum(parse_num(q["Sales"][x])[0] for x in per[-4:])
        evidence_stock[sym]["tapetide_annual_ttm_lags_one_quarter"] = abs(ttm - s4) <= 2 and abs(ttm - s4n) > 2
        evidence_stock[sym]["tapetide_ttm_sales"] = ttm; evidence_stock[sym]["tapetide_own_last4q_sales"] = round(s4n, 2)
        evidence_stock[sym]["tapetide_own_prev4q_sales"] = round(s4, 2)
    except Exception as e:
        evidence_stock[sym]["ttm_check_error"] = str(e)
for m in mismatches: m["explanation"] = explain(m)
expl_of = {(m["symbol"], m["statement"], m["row"], m["period"]): m["explanation"] for m in mismatches}
for c in cells: c["explanation"] = expl_of.get((c["symbol"], c["statement"], c["row"], c["period"]), "")

def agg_adj(rows):
    ok = sum(c["category"] in ("exact", "rounded") for c in rows)
    explained = sum(c["category"] not in ("exact", "rounded") and c["explanation"] not in ("", "unexplained") for c in rows)
    base = len(rows) - explained
    return {"cells_after_excluding_explained": base, "explained_excluded": explained,
            "timing_adjusted_match_pct": round(100 * ok / base, 3) if base else None}

# ---------------------------------------------------------------- aggregate
def agg(rows):
    c = Counter()
    for r in rows: c[r["category"]] += 1
    tot = sum(c.values())
    return {"cells": tot, **dict(c), "match_pct": round(100 * (c["exact"] + c["rounded"]) / tot, 3) if tot else None,
            "exact_pct": round(100 * c["exact"] / tot, 3) if tot else None}
overall = agg(cells)
by_stmt = {k: agg([c for c in cells if c["statement"] == k]) for k, _, _ in STATEMENTS}
by_basis = {b: agg([c for c in cells if c["basis"] == b]) for b in ("consolidated", "standalone")}
by_tier = {t: agg([c for c in cells if evidence_stock[c["symbol"]]["tier"] == t]) for t in ("large", "mid", "small")}
by_stock = {s["symbol"]: agg([c for c in cells if c["symbol"] == s["symbol"]]) for s in sample}
basis_align = Counter(ev["tapetide_basis_equals_screener_default"] for ev in evidence_stock.values())
row_level = {"row_names_identical": sum(r["row_names_identical"] for r in stock_rows),
             "row_order_identical": sum(r["row_order_identical"] for r in stock_rows),
             "periods_identical": sum(r["periods_identical"] for r in stock_rows), "statement_pairs": len(stock_rows)}
only_t = Counter(); only_s = Counter()
for ev in evidence_stock.values():
    for k, st in ev["statements"].items():
        for r in st.get("rows_only_tapetide", []): only_t[f"{k}: {r}"] += 1
        for r in st.get("rows_only_screener", []): only_s[f"{k}: {r}"] += 1

with open(os.path.join(OUT, "stock_comparison.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(stock_rows[0])); w.writeheader(); w.writerows(stock_rows)
with open(os.path.join(OUT, "detailed_mismatches.csv"), "w", newline="") as f:
    fields = ["symbol", "tier", "basis", "statement", "row", "period", "tapetide_value", "screener_value", "category", "abs_diff", "rel_diff_pct", "explanation"]
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(mismatches)
adjusted = {"overall": agg_adj(cells),
            "by_statement": {k: agg_adj([c for c in cells if c["statement"] == k]) for k, _, _ in STATEMENTS},
            "by_basis": {b: agg_adj([c for c in cells if c["basis"] == b]) for b in ("consolidated", "standalone")},
            "by_stock": {s_["symbol"]: agg_adj([c for c in cells if c["symbol"] == s_["symbol"]]) for s_ in sample}}
explanations = Counter(m["explanation"] for m in mismatches)
for r in stock_rows:
    a = agg_adj([c for c in cells if c["symbol"] == r["symbol"] and c["statement"] == r["statement"]])
    r["explained_by_timing_or_basis"] = a["explained_excluded"]; r["timing_adjusted_match_pct"] = a["timing_adjusted_match_pct"]
with open(os.path.join(OUT, "stock_comparison.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(stock_rows[0])); w.writeheader(); w.writerows(stock_rows)
json.dump({"overall": overall, "timing_adjusted": adjusted, "explanations": dict(explanations), "by_statement": by_stmt, "by_basis": by_basis, "by_tier": by_tier, "by_stock": by_stock,
           "row_level": row_level, "basis_alignment": {str(k): v for k, v in basis_align.items()},
           "derived_row_checks": {k: {"pass": v[0], "total": v[1]} for k, v in derived.items()},
           "fingerprints": dict(fingerprints), "rows_only_in_tapetide": dict(only_t), "rows_only_in_screener": dict(only_s),
           "stocks": evidence_stock}, open(os.path.join(HERE, "evidence", "engine_results.json"), "w"), indent=1, default=str)
print(json.dumps({"adjusted": {k: adjusted[k] for k in ("overall", "by_statement", "by_basis")}, "explanations": dict(explanations)}, indent=1))
print(json.dumps({"overall": overall, "by_statement": by_stmt, "by_basis": by_basis, "by_tier": by_tier, "row_level": row_level,
                  "basis_alignment": dict(basis_align), "derived": {k: v for k, v in derived.items()},
                  "fingerprints": dict(fingerprints), "only_tapetide": dict(only_t), "only_screener": dict(only_s)}, indent=1))
print("\nPER STOCK:")
for sym, a in by_stock.items():
    ev = evidence_stock[sym]
    print(f"  {sym:11s} {ev['tapetide_basis']:12s} scr_default={ev['screener_default_basis']:12s} page={ev['screener_page_compared']} {a}")
