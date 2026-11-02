"""Build executive_summary.md and source_attribution.json from analyze.py output. Safe to re-run after each checkpoint."""
import csv, json, os, time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "reports", "three_way_fingerprinting")
R = json.load(open(os.path.join(HERE, "evidence", "analysis_results.json")))
MCP = json.load(open(os.path.join(HERE, "evidence", "mcp_extracts.json")))
lat = list(csv.DictReader(open(os.path.join(OUT, "update_latency.csv"))))
ud = R["unexplained"]; P = R["pair_summary"]; fpI = R["fingerprints_indianapi"]; ev = R.get("events", {})
base_rows = [r for r in lat if r["label"] == "baseline"]
reporters = sorted({r["symbol"] for r in base_rows if r["source"] == "screener" and r["latest_quarter"] == "Sep 2026"})
have = {src: sorted(r["symbol"] for r in base_rows if r["source"] == src and r["symbol"] in reporters and r["latest_quarter"] == "Sep 2026")
        for src in ("screener", "tapetide", "indianapi_arthscan_cache")}
complete_T = sorted(r["symbol"] for r in base_rows if r["source"] == "tapetide" and r["symbol"] in have["tapetide"] and r["rows_filled"].split("/")[0] == r["rows_filled"].split("/")[1])
eqS_T = [(r["symbol"], r["rows_equal_screener"], r["rows_filled"]) for r in base_rows if r["source"] == "tapetide" and r["symbol"] in have["tapetide"]]
vd = Counter()
for u in ud:
    v = u["verdict"]
    vd["Tapetide filing override; Screener = Indian Stock API" if v.startswith("Tapetide filing override") else
       "Tapetide = Indian Stock API, Screener differs" if v.startswith("Tapetide = Indian") else
       "Indian Stock API = Screener, Tapetide differs" if v.startswith("Indian Stock API = Screener") else
       "agree within rounding" if v.startswith("agree within") else
       "missing on Tapetide (newest-quarter gaps)" if "missing" in v and "Sep 2026" in u["period"] else
       "missing / n/m on Tapetide (historical)" if "missing" in v else v] += 1
tri = R["triad"]
mon_done = {s: e for s, e in ev.items() if not s.startswith("_")}
cp_taken = {s: {k: c for k, c in e["checkpoints"].items() if c.get("taken_utc")} for s, e in mon_done.items()}
first = R.get("first_seen_minutes_after_t0", {})
phase4_complete = bool(mon_done) and all(all(c.get("taken_utc") for c in e["checkpoints"].values()) for e in mon_done.values()) and len(mon_done) == 2

def verdicts():
    # current evidence; release timing (Phase 4) can strengthen or overturn A, B, D
    direct = "inconclusive, leaning supported" + ("" if phase4_complete else " (release-timing test pending)")
    return {"direct_screener_sourcing": direct,
            "shared_upstream_provider": "not supported for Indian Stock API as Tapetide's feed; inconclusive for any other Screener-format reseller",
            "independent_compilation": "partly supported: Tapetide's provisional new quarters and filing overrides are its own; its compiled historical base is not independent"}
V = verdicts()

attribution = {
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "question": "Does Tapetide obtain financial statements directly from Screener.in or from a shared upstream provider such as Indian Stock API?",
    "sources": {"T": "Tapetide public .md pages + Tapetide MCP", "S": "Screener.in public company pages",
                "I": "Indian Stock API (indianapi.in), ARTHSCAN-cached data (not a direct provider observation), as served by ARTHSCAN (/stock/{SYM}/statements, same data as /v1/ext/statements; source field confirmed via arth MCP get_statements)"},
    "important_caveat": "Indian Stock API was observed through ARTHSCAN's cached copy (arth MCP fetched_at between 29 Oct and 1 Nov). Its latency here is the latency of that copy, which is an upper bound on Indian Stock API's own latency.",
    "snapshots": R["snapshots"],
    "answers": {
        "A_tapetide_matches_screener_first": {
            "answer": "Tapetide's compiled values equal Screener's, but its newest quarters are often provisional figures from filings, which match Screener without being copied" + ("; release-time test pending" if not phase4_complete else ""),
            "evidence": {"new_quarter_coverage_at_baseline": {k: f"{len(v)}/{len(reporters)}" for k, v in have.items()},
                         "tapetide_new_quarter_cells_equal_screener": eqS_T,
                         "quickheal": "Indian Stock API lacked Sep 2026 at 2026-11-01T18:30Z (5 days after filing); Tapetide had it with values equal to Screener",
                         "release_monitoring_first_seen_minutes_after_t0": first}},
        "B_tapetide_matches_indianapi_first": {
            "answer": "No: Tapetide carried new quarters that Indian Stock API (via ARTHSCAN) did not have",
            "evidence": {"stocks_tapetide_has_new_quarter_indianapi_lacks": sorted(set(have["tapetide"]) - set(have["indianapi_arthscan_cache"])),
                         "stocks_indianapi_has_tapetide_lacks": sorted(set(have["indianapi_arthscan_cache"]) - set(have["tapetide"]))}},
        "C_indianapi_reproduces_screener_derived_rows": {
            "answer": "Yes",
            "evidence": {"derived_rows_recompute": fpI["derived_rows"], "EPS_in_Rs_label_tables": fpI["label_EPS_in_Rs"],
                         "CFO_EBITDA_label": fpI["label_CFO_EBITDA"], "CFO_OP_label (Tapetide's rename)": fpI["label_CFO_OP"],
                         "TTM_column": f'{fpI["ttm_column"]}/10', "finance_company_row_order": fpI["finance_row_order_matches"],
                         "half_year_balance_sheet_column": f'{fpI["half_year_bs_column_when_screener_has_it"][0]}/{fpI["half_year_bs_column_when_screener_has_it"][1]} (others lag)',
                         "pairwise_match_I_vs_S": P["I-S"]["all"]}},
        "D_first_to_publish_new_quarters": {
            "answer": "Screener, then Tapetide, then Indian Stock API (baseline ordering)" + ("" if phase4_complete else "; minutes-level latency pending release monitoring"),
            "evidence": {"coverage": have, "tapetide_new_quarter_complete": complete_T, "release_monitoring": cp_taken, "first_seen": first}},
        "E_unexplained_historical_values_identical": {
            "answer": "Mostly no: most Tapetide-only differences are Tapetide's own filing overrides, and Indian Stock API equals Screener on them. ABCAPITAL Sep 2025 is the exception: Tapetide = Indian Stock API, Screener differs.",
            "evidence": {"verdict_counts": dict(vd), "rows": ud}},
        "F_shared_upstream_evidence": {
            "answer": "Indian Stock API and Tapetide both carry Screener-format data, but Tapetide shows no Indian Stock API-specific dependence and is ahead of it on new quarters. A common origin for Screener-format data is consistent with the evidence but unidentified.",
            "evidence": {"triad_cells": tri, "pairwise": {k: v["all"] for k, v in P.items()},
                         "tapetide_specific_transforms_absent_from_indianapi": ["CFO/OP rename", "finance-company row reorder", "cell_source=filing overrides", "newest-quarter EPS withheld"],
                         "abcapital_sep_2025": "Tapetide and Indian Stock API both hold the older Sep 2025 figures and both lack Sep 2026; Screener has Sep 2026 and different Sep 2025 figures (consistent with a restatement after the Sep 2026 results, not verified against the filing)."}},
    },
    "verdicts": V,
    "tapetide_disclosed_filing_layer": {"note_verbatim": MCP["tapetide_mcp_get_financials"]["cell_source_note_verbatim"],
                                        "flags": {s: v.get("cell_source") for s, v in MCP["tapetide_mcp_get_financials"].items() if isinstance(v, dict)}},
    "monitoring": {"events": ev, "complete": phase4_complete},
    "limits": ["Ten stocks, one baseline snapshot plus release checkpoints.", "Numerical similarity does not establish a commercial relationship.",
               "Screener.in's own upstream is out of scope.", "Indian Stock API observed only through ARTHSCAN."],
}
json.dump(attribution, open(os.path.join(OUT, "source_attribution.json"), "w"), indent=1, default=str)

# ---------------------------------------------------------------- executive_summary.md
def pp(x): return "n/a" if x is None else f"{x:.2f}%"
L = ["# Three-way data provider fingerprinting: Tapetide, Screener.in, Indian Stock API", "",
     f"Updated {attribution['generated_at']}. Baseline snapshot `{R['base']}`; {len(R['snapshots'])} snapshot(s) in total. 10 stocks.", "",
     "> **Labelling:** every Indian Stock API observation in this report is **ARTHSCAN-cached data** (ARTHSCAN's stored copy of the provider's response, with its own `fetched_at`), not a direct observation of indianapi.in.", "",
     "## Conclusion", "",
     f"- **Direct Screener sourcing: {V['direct_screener_sourcing']}.**",
     f"- **Shared upstream provider: {V['shared_upstream_provider']}.**",
     f"- **Independent compilation: {V['independent_compilation']}.**", "",
     "Tapetide runs two layers. Its **compiled base** is Screener-format and matches Screener cell for cell. On top, it has **its own filing layer**: provisional new quarters built from company filings, and historical cells replaced with the filed figure (its MCP flags these `cell_source: filing`). Every historical value difference in the quarterly tables traces to that layer.", "",
     "Indian Stock API is also Screener-format, but Tapetide shares none of Indian Stock API's state and carries new quarters it lacks, so Indian Stock API is not Tapetide's feed. What this test cannot separate is direct Screener sourcing from another reseller of Screener-format data; the release-timing test is designed for that. None of this establishes a commercial relationship.", "",
     "## Pairwise agreement (baseline, same basis only)", "",
     "| Pair | Cells | Match % | Focus rows* match % |", "|---|---:|---:|---:|"]
for k, lab in (("T-I", "Tapetide vs Indian Stock API (ARTHSCAN-cached)"), ("T-S", "Tapetide vs Screener"), ("I-S", "Indian Stock API (ARTHSCAN-cached) vs Screener")):
    L.append(f"| {lab} | {P[k]['all']['cells']:,} | {pp(P[k]['all']['match_pct'])} | {pp(P[k]['focus_rows']['match_pct'])} |")
L += ["", "*Other Income, Depreciation, Profit before tax, Net Profit, EPS, Operating/Financing Profit.", "",
      f"Where all three have a value: all agree on {tri.get('all_three_agree', 0):,} cells; Tapetide = Indian Stock API ≠ Screener on {tri.get('T=I, S differs', 0)}; Indian Stock API = Screener ≠ Tapetide on {tri.get('I=S, T differs', 0)}; Tapetide = Screener ≠ Indian Stock API on {tri.get('T=S, I differs', 0)}. Most disagreements are timing (a source missing the newest quarter or TTM window) rather than different figures.", "",
      "## Answers", "",
      f"**A. Does Tapetide match Screener's values first?** {attribution['answers']['A_tapetide_matches_screener_first']['answer']}. Of {len(reporters)} stocks that have reported Sep 2026, Screener has the quarter for {len(have['screener'])}, Tapetide {len(have['tapetide'])}, Indian Stock API {len(have['indianapi_arthscan_cache'])}. Every value Tapetide shows for the new quarter equals Screener's except one ZEEL cell (Interest 3 vs 2).", "",
      f"**B. Does Tapetide match Indian Stock API's values first?** No. Tapetide has the new quarter for {', '.join(sorted(set(have['tapetide']) - set(have['indianapi_arthscan_cache'])))} while Indian Stock API does not. QUICKHEAL is the clearest case: Indian Stock API still lacked Sep 2026 on 1 Nov 18:30 UTC, five days after the filing.", "",
      f"**C. Does Indian Stock API reproduce Screener's unusual derived rows?** Yes: " + ", ".join(f"{k} {v}" for k, v in fpI["derived_rows"].items()) + f"; `EPS in Rs`, `CFO/EBITDA`, the TTM column and Screener's finance-company row order. It shares none of Tapetide's own changes (`CFO/OP`, reordered finance rows, filing overrides).", "",
      f"**D. Which platform publishes newly reported quarters first?** {attribution['answers']['D_first_to_publish_new_quarters']['answer']}. TRENT filed at 10:51 UTC on 29 Oct; Indian Stock API's copy 12 hours later still lacked the quarter.", "",
      "**E. Are the unexplained historical values identical?**", ""]
for k, v in vd.most_common(): L.append(f"- {k}: {v}")
L += ["", "Every Tapetide-only difference in the quarterly tables is flagged by Tapetide's own MCP (flags checked for all 10 stocks); the 2 remaining are in annual tables, which the flags do not cover. PIIND's seven quarterly differences and two of ABCAPITAL's are flagged by Tapetide's own MCP as `cell_source: filing` (the company's filed figure replacing the compiled value); Indian Stock API equals Screener on all of them. ABCAPITAL Sep 2025 (Other Income 92 vs 170, PBT 1,212 vs 1,290, Net Profit 882 vs 961, EPS 3.27 vs 3.57) is the one case where Tapetide equals Indian Stock API and Screener differs; both Tapetide and Indian Stock API also lack ABCAPITAL's Sep 2026 quarter, so this looks like an older shared state rather than a shared error.", "",
      f"**F. Is there evidence of a shared upstream provider?** {attribution['answers']['F_shared_upstream_evidence']['answer']}", "",
      "## Tapetide's two-stage pipeline", "",
      "| Stage | Stocks (Sep 2026) | Evidence |", "|---|---|---|",
      "| Provisional, from the filing | " + ", ".join(f"{s} (filed {v['provisional_periods'][0]['filed_on']})" for s, v in MCP["tapetide_mcp_get_financials"].items() if isinstance(v, dict) and v.get("provisional_periods")) + " | MCP `provisional_periods`; EPS always blank, WELSPUNLIV also blank Operating Profit, OPM % and Other Income; every filled value equals Screener's except ZEEL Interest |",
      "| Compiled, Screener-format | " + ", ".join(s for s, v in MCP["tapetide_mcp_get_financials"].items() if isinstance(v, dict) and v.get("provisional_periods") == [] and s in have["tapetide"]) + " | Complete quarter, all cells equal to Screener |", "",
      "This matters for answers A and D: a provisional quarter matching Screener does not show that Tapetide copied Screener, because filing figures are the same numbers. The release-timing test therefore tracks when each stock moves from provisional to compiled on Tapetide, and compares that with Screener and Indian Stock API.", "",
      "## Release monitoring (Phase 4)", ""]
SCHED = json.load(open(os.path.join(HERE, "monitor", "scheduler.json")))
ticks = [json.loads(l) for l in open(os.path.join(HERE, "monitor", "ticks.jsonl"))] if os.path.exists(os.path.join(HERE, "monitor", "ticks.jsonl")) else []
L += [f"**Status: {'complete' if phase4_complete else 'not complete'}.** " + ("" if phase4_complete else "No T+48h checkpoint has been captured yet, so no release-timing conclusion is drawn."), "",
      f"- Scheduler: {SCHED['type']}; `{SCHED['cron_expression']}` ({SCHED['meaning']}); trigger `{SCHED['trigger_id']}`.",
      f"- Ticks logged so far: {len(ticks)} (last {ticks[-1]['tick_utc'] if ticks else 'none'}); T0 events recorded: {len(mon_done)}.",
      f"- Restart safety: {SCHED['survives_container_restart']}.", ""]
CK = [json.loads(l) for l in open(os.path.join(HERE, "evidence", "checkpoint_mcp.jsonl"))] if os.path.exists(os.path.join(HERE, "evidence", "checkpoint_mcp.jsonl")) else []
attribution["monitoring"]["checkpoint_mcp_captures"] = CK
json.dump(attribution, open(os.path.join(OUT, "source_attribution.json"), "w"), indent=1, default=str)
if CK:
    L += ["| Company | Checkpoint | Source | Called (UTC) | Source timestamp | Latest period | Tapetide provisional | cell_source flags |", "|---|---|---|---|---|---|---|---|"]
    for c in CK:
        src = "Indian Stock API (ARTHSCAN-cached)" if c.get("label") == "ARTHSCAN-cached" else "Tapetide MCP"
        L.append(f"| {c.get('symbol')} | {c.get('checkpoint')} | {src} | {c.get('called_at_utc')} | {c.get('updated_at') or c.get('fetched_at')} | {c.get('latest_period')} | {c.get('provisional_periods', '')} | {sum(len(v) for v in (c.get('cell_source') or {}).values())} |")
    L.append("")
if mon_done:
    L += ["| Company | T0 (exchange, UTC) | Detected after | Checkpoints taken |", "|---|---|---:|---|"]
    for s, e in mon_done.items():
        L.append(f"| {s} | {e['t0_exchange_utc']} | {e['detection_lag_min']} min | " + ", ".join(f"{k} ({c.get('late_by_min', 0)} min late)" if k != "T0" else "T0" for k, c in e["checkpoints"].items() if c.get("taken_utc")) + " |")
    if first: L += ["", "First snapshot (minutes after T0) in which each source showed the new quarter:", ""] + [f"- {s}: " + ", ".join(f"{k} {v if v is not None else 'not yet'}" for k, v in d.items()) for s, d in first.items()]
else:
    L += ["Pending. MOTHERSON and PIIND have earnings calls on 5 Nov 2026 and had not filed results at the baseline. An hourly scheduled check polls NSE's official announcements RSS feed and records T0 from the exchange's own timestamp, then takes three-source snapshots at T+30m, +2h, +24h and +48h. This summary and update_latency.csv are rebuilt after each checkpoint."]
L += ["", "## What ARTHSCAN should integrate independently", "",
      "| Dataset | Integrate directly | Instead of |", "|---|---|---|",
      "| Financial statements | NSE/BSE XBRL results filings (the NSE results feed links each filing's XBRL), with ARTHSCAN's own documented derived rows | Indian Stock API statements, which are Screener-format and were the slowest source here |",
      "| Corporate filings, board meetings, corporate actions | NSE/BSE announcement feeds and archives (already partly used) | Third-party summaries |",
      "| Shareholding pattern | NSE/BSE XBRL shareholding filings | Indian Stock API shareholding |",
      "| Mutual funds | AMFI daily NAV file and monthly reports | Indian Stock API mutual funds |",
      "| IPOs | NSE/BSE issue pages and bid data, SEBI offer documents (already used) | Aggregators; label any GMP as unofficial |",
      "| Credit ratings | Rating agency press releases (CRISIL, ICRA, CARE, India Ratings) | Aggregated rating feeds |",
      "| Prices | Keep NSE end-of-day files and the licensed Dhan live feed | |",
      "| Analyst forecasts | A licensed estimates vendor under a direct contract | Indian Stock API forecasts, whose provenance is unclear |", "",
      "Before redistributing any Screener-format data, ARTHSCAN should check the redistribution terms of every provider in its chain.", "",
      "## Files", "",
      "- `timestamped_snapshots.csv`: every numeric cell from every snapshot, with fetch time, source timestamp, precision and file hash.",
      "- `provider_comparison.csv`: per stock, statement and pair.",
      "- `update_latency.csv`: latest periods, TTM window and new-quarter completeness per source per snapshot, plus timing references.",
      "- `unexplained_differences.csv`: the Phase 1 unexplained cells for these stocks, with current values from all three sources.",
      "- `source_attribution.json`: answers A-F with evidence, verdicts, Tapetide's disclosed filing layer and monitoring state.",
      "- Raw immutable snapshots: `three_way/snapshots/`. Code: `three_way/`."]
open(os.path.join(OUT, "executive_summary.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
