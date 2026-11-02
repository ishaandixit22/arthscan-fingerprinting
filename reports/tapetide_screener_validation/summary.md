# Tapetide vs Screener.in: 20-stock financial statement fingerprint validation

Run 2026-11-02T05:32:59Z. Data fetched 2 Nov 2026. Tapetide via public `.md` stock pages (matched its official MCP on 215/215 cells); Screener.in via public company pages.

## Executive summary

- **97.03%** of 10,588 compared cells match (exact or rounding); **97.02%** are exact.
- Excluding 270 cells explained by refresh timing or EPS share basis: **99.57%** of 10,318.
- Tapetide's basis matches **Screener's default view for 20/20** stocks, including CROMPTON, where Screener has consolidated data but defaults to standalone.
- Screener-specific derived rows recompute exactly on Tapetide: Operating Profit 479/479; OPM % 476/476; Other Liabilities 217/217; Other Assets 229/229.
- 46 cells are unexplained: 33 value differences (mostly Other Income and the rows computed from it) and 13 single missing cells.
- Verdict: the evidence strongly supports **Screener-format data as Tapetide's statement source**. It cannot separate direct scraping from a reseller of Screener-format data, and says nothing about commercial relationships.

## Matching by statement type

| Statement | Cells | Exact | Rounded | Partial | Mismatch | Missing (T) | Missing (S) | Match % | Timing-adjusted % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| quarterly | 2898 | 2760 | 0 | 12 | 17 | 21 | 88 | 95.24% | 98.68% |
| annual_pl | 2872 | 2775 | 2 | 7 | 86 | 2 | 0 | 96.69% | 99.78% |
| balance_sheet | 2370 | 2290 | 0 | 0 | 0 | 80 | 0 | 96.62% | 100.00% |
| cash_flow | 1326 | 1326 | 0 | 0 | 0 | 0 | 0 | 100.00% | 100.00% |
| ratios | 1122 | 1121 | 0 | 0 | 0 | 1 | 0 | 99.91% | 99.91% |
| **All** | 10588 | 10272 | 2 | 19 | 103 | 104 | 88 | 97.03% | 99.57% |

## Consolidated vs standalone (compared separately)

| Basis | Stocks | Cells | Match % | Timing-adjusted % |
|---|---:|---:|---:|---:|
| consolidated | 17 | 9415 | 96.76% | 99.54% |
| standalone | 3 | 1173 | 99.23% | 99.83% |

Tapetide offers one basis per company, so each stock appears under one basis only. Standalone: ENRIN, BHARTIHEXA, CROMPTON. Screener has no consolidated figures for ENRIN, BHARTIHEXA.

## Stock-wise results

| Stock | Tier | Industry | Basis | Cells | Match % | Timing-adjusted % | Mismatch + partial | Unexplained |
|---|---|---|---|---:|---:|---:|---:|---:|
| RELIANCE | large | Oil Gas & Consumable Fuels | consolidated | 571 | 100.00% | 100.00% | 0 | 0 |
| MOTHERSON | large | Automobile and Auto Components | consolidated | 561 | 100.00% | 100.00% | 0 | 0 |
| MAXHEALTH | large | Healthcare | consolidated | 513 | 93.76% | 99.59% | 10 | 2 |
| TRENT | large | Consumer Services | consolidated | 571 | 99.47% | 99.47% | 2 | 3 |
| ADANIENSOL | large | Power | consolidated | 547 | 99.82% | 99.82% | 0 | 1 |
| ENRIN | large | Capital Goods | standalone | 201 | 100.00% | 100.00% | 0 | 0 |
| JSL | mid | Metals & Mining | consolidated | 582 | 94.33% | 99.64% | 11 | 2 |
| ABCAPITAL | mid | Financial Services | consolidated | 510 | 90.39% | 98.50% | 17 | 7 |
| GODFRYPHLP | mid | Fast Moving Consumer Goods | consolidated | 561 | 100.00% | 100.00% | 0 | 0 |
| GODREJPROP | mid | Realty | consolidated | 562 | 94.31% | 99.81% | 10 | 1 |
| BHARTIHEXA | mid | Telecommunication | standalone | 408 | 98.28% | 100.00% | 7 | 0 |
| JSWINFRA | mid | Services | consolidated | 493 | 92.50% | 99.78% | 15 | 1 |
| PIIND | mid | Chemicals | consolidated | 561 | 98.57% | 98.57% | 8 | 10 |
| QUICKHEAL | small | Information Technology (reference, not in index list) | consolidated | 562 | 94.31% | 99.81% | 10 | 1 |
| NBCC | small | Construction | consolidated | 537 | 99.81% | 99.81% | 1 | 1 |
| CYIENT | small | Information Technology | consolidated | 569 | 99.82% | 99.82% | 1 | 1 |
| ZEEL | small | Media Entertainment & Publication | consolidated | 572 | 93.53% | 98.89% | 15 | 6 |
| RAMCOCEM | small | Construction Materials | consolidated | 561 | 99.82% | 99.82% | 1 | 1 |
| WELSPUNLIV | small | Textiles | consolidated | 582 | 93.47% | 98.73% | 13 | 7 |
| CROMPTON | small | Consumer Durables | standalone | 564 | 99.64% | 99.64% | 1 | 2 |

By tier: large 98.78% of 2964 cells; mid 95.48% of 3677 cells; small 97.16% of 3947 cells.

## Structure checks (100 stock × statement pairs)

- Row order identical on shared rows: **98/100**. The exceptions (ABCAPITAL quarterly, ABCAPITAL annual_pl) keep Screener's finance-company labels but use Tapetide's general template order (Interest moved below Other Income); values still match.
- Row names identical: 94/100. Every difference is one of: rows that are empty on Screener and dropped by Tapetide (12: ratios: Inventory Days, ratios: Days Payable, quarterly: Gross NPA %, quarterly: Net NPA %), Screener rows Tapetide omits (none), or Tapetide's rename of `CFO/EBITDA` to `CFO/OP` (11 stocks; Screener's own tooltip defines the row as CFO / Operating Profit).
- Periods identical: 84/100. Differences are window edges only: Tapetide keeps the quarter that rolled off Screener's 13-quarter window (8 stocks) and lacks the newest Screener period where its refresh lags.
- Decimal precision: 10,200 matching cells have identical decimal places; 74 differ only by trailing zeros (Screener `13.70`, Tapetide `13.7`). Precision breaks appear only among the unexplained cells: 5 Tapetide values with decimals inside otherwise whole-number rows.

## Screener-like fingerprints

1. **Default-view basis.** Tapetide's basis equals Screener's canonical URL basis for 20/20 stocks. CROMPTON is decisive: Screener has consolidated figures but its canonical page is standalone, and Tapetide is standalone.
2. **Derived rows.** Other Liabilities, Other Assets, Operating Profit and OPM % are Screener constructs, not filing line items; they match cell for cell and recompute exactly. Tax % keeps Screener's sign on losses (QUICKHEAL −32.79%).
3. **Half-year column in the annual balance sheet.** Screener shows it for 13 stocks; Tapetide shows the identical column for 5 of them (RELIANCE, TRENT, ADANIENSOL, CYIENT, CROMPTON) and has not added it yet for the other 8 (refresh lag). Tapetide's MCP labels it `period_months: 12`.
4. **TTM with Screener's rounding, one quarter behind** for 7 stocks (MAXHEALTH, JSL, GODREJPROP, JSWINFRA, QUICKHEAL, ZEEL, WELSPUNLIV). JSL: Tapetide TTM sales 44026 vs 44027 summed from its own quarters, so the value was computed upstream from unrounded figures.
5. **Layouts and labels.** `EPS in Rs`, TTM column, 13-quarter and 12-year windows; the finance-company layout (Revenue, Financing Profit, Financing Margin %) for ABCAPITAL.
6. **Cash flow** matches 100% once Tapetide's `CFO/OP` label is mapped to Screener's `CFO/EBITDA`.

## Mismatches and what explains them

| Explanation | Cells |
|---|---:|
| coverage_window/refresh_lag (newest or oldest period not on Tapetide) | 91 |
| coverage_window (period outside Screener's display window) | 88 |
| refresh_lag (Tapetide TTM = Screener-style TTM one quarter earlier) | 68 |
| unexplained | 46 |
| refresh_lag (Tapetide's latest quarter is older than Screener's) | 10 |
| eps_share_basis_factor (Tapetide/Screener = 2) | 7 |
| eps_share_basis_factor (Tapetide/Screener = 30) | 6 |

Tapetide's own processing, visible in the differences:
- **EPS restated by exact factors:** BHARTIHEXA ×2 (7 cells); JSWINFRA ×30 (6 cells). Consistent with Tapetide's own split/bonus adjustment (its forecasts tool reports `eps_adjustments`).
- **Newest-quarter EPS withheld** for GODREJPROP, JSL, JSWINFRA, MAXHEALTH, QUICKHEAL, WELSPUNLIV, ZEEL (Tapetide's MCP marked QUICKHEAL's Sep 2026 quarter as provisional; not checked for the others).
- **Unexplained value differences** (full list in detailed_mismatches.csv):
  - MAXHEALTH quarterly EPS in Rs Jun 2026: Tapetide 3.32 vs Screener 3.31 (partial)
  - TRENT quarterly Profit before tax Mar 2025: Tapetide 417 vs Screener 416 (partial)
  - TRENT quarterly Profit before tax Sep 2025: Tapetide 478 vs Screener 477 (partial)
  - JSL quarterly Other Income Mar 2024: Tapetide 54.98 vs Screener 53 (mismatch)
  - ABCAPITAL quarterly Other Income Sep 2025: Tapetide 92 vs Screener 170 (mismatch)
  - ABCAPITAL quarterly Depreciation Mar 2024: Tapetide 53.5 vs Screener 52 (mismatch)
  - ABCAPITAL quarterly Depreciation Jun 2024: Tapetide 55.44 vs Screener 54 (mismatch)
  - ABCAPITAL quarterly Profit before tax Sep 2025: Tapetide 1,212 vs Screener 1,290 (mismatch)
  - ABCAPITAL quarterly Tax % Sep 2025: Tapetide 27% vs Screener 26% (mismatch)
  - ABCAPITAL quarterly Net Profit Sep 2025: Tapetide 882 vs Screener 961 (mismatch)
  - ABCAPITAL quarterly EPS in Rs Sep 2025: Tapetide 3.27 vs Screener 3.57 (mismatch)
  - PIIND quarterly Other Income Mar 2025: Tapetide 73.4 vs Screener 75 (mismatch)
  - PIIND quarterly Other Income Sep 2025: Tapetide 82.5 vs Screener 85 (mismatch)
  - PIIND quarterly Other Income Mar 2026: Tapetide 75.6 vs Screener 74 (mismatch)
  - PIIND quarterly Other Income Jun 2026: Tapetide 64.1 vs Screener 66 (mismatch)
  - PIIND quarterly Profit before tax Mar 2025: Tapetide 431 vs Screener 432 (partial)
  - PIIND quarterly Profit before tax Sep 2025: Tapetide 523 vs Screener 525 (partial)
  - PIIND quarterly Profit before tax Jun 2026: Tapetide 320 vs Screener 322 (partial)
  - PIIND annual_pl Other Income Mar 2025: Tapetide 344 vs Screener 345 (partial)
  - PIIND annual_pl EPS in Rs Mar 2024: Tapetide 111 vs Screener 110.83 (rounded)
  - PIIND annual_pl EPS in Rs Mar 2025: Tapetide 109 vs Screener 109.43 (rounded)
  - NBCC quarterly Other Income Dec 2024: Tapetide 55.2 vs Screener 54 (mismatch)
  - CYIENT quarterly Profit before tax Mar 2026: Tapetide 96.7 vs Screener 95 (partial)
  - ZEEL quarterly Sales Jun 2024: Tapetide 2,131 vs Screener 2,130 (partial)
  - ZEEL quarterly Interest Sep 2026: Tapetide 3 vs Screener 2 (mismatch)
  - ZEEL quarterly Profit before tax Mar 2024: Tapetide 114 vs Screener 115 (partial)
  - ZEEL quarterly Net Profit Dec 2023: Tapetide 58.54 vs Screener 58 (partial)
  - ZEEL annual_pl Profit before tax Mar 2026: Tapetide 273 vs Screener 274 (partial)
  - RAMCOCEM annual_pl Interest Mar 2026: Tapetide 419 vs Screener 421 (partial)
  - WELSPUNLIV quarterly Other Income Mar 2024: Tapetide 41.48 vs Screener 42 (partial)
  - WELSPUNLIV quarterly Other Income Jun 2026: Tapetide 32.71 vs Screener 34 (mismatch)
  - WELSPUNLIV quarterly Profit before tax Jun 2026: Tapetide 219 vs Screener 220 (partial)
  - CROMPTON annual_pl Other Income Mar 2025: Tapetide 63.2 vs Screener 64 (partial)

## Evidence for and against the hypothesis

**Supports Screener-format sourcing**
- 97% exact cell matches across 20 stocks, 5 statements, both bases and all three size tiers; after timing adjustment no stock is below 98.50% (ABCAPITAL).
- Screener presentation choices reproduced: default basis, derived rows, half-year column, TTM rounding, display windows, finance layout.
- Refresh lags behave like periodic snapshots of a windowed source: Tapetide's tables are updated separately (quarterly fresher than annual) and keep quarters that have rolled off Screener's window.

**Weakens or qualifies it**
- Tapetide applies its own logic on top: EPS restatement, withheld provisional EPS, a renamed cash-flow ratio, dropped empty rows, its own row order for finance companies.
- 33 unexplained value differences, mostly Other Income, some with more decimals than Screener shows. Either Tapetide corrects some cells from another source (e.g. filings) or Screener revised them after Tapetide's snapshot. This test cannot tell which.

**Direct vs shared upstream**
- Direct scraping of Screener and a reseller of Screener-format data produce the same artefacts. indianapi.in (arthscan's provider) already matched Screener on 252/252 RELIANCE cells, so such resellers exist.
- Independent compilation from filings is not supported by the evidence.
- None of this establishes a commercial relationship.

## Recommended next investigation

**Three-way, time-stamped refresh study (Tapetide, Screener.in, indianapi.in) through the next results batch.** Snapshot the same companies on a fixed schedule as they announce results, and compare:
1. Order and latency of first appearance of a new quarter on each source.
2. Whether Tapetide's intermediate states (pre-revision values, lagging TTM, missing half-year column) match Screener's or indianapi.in's earlier snapshots.
3. Whether the unexplained Other Income cells exist identically on indianapi.in; if they do, Tapetide more likely buys from that reseller than from Screener directly.
This discriminates direct from shared-upstream sourcing, which a single-snapshot comparison cannot.

## Method and limits

- Sample: seed 42, Nifty 100 / Midcap 150 / Smallcap 250 lists; RELIANCE and QUICKHEAL fixed (QUICKHEAL is outside the Smallcap 250 list).
- Access: public pages only, single pass with 4–6.5 s spacing per host and a stop on HTTP 429; Tapetide `/api/` (robots-disallowed) and its login-protected developer docs were not used.
- One snapshot in time, so refresh timing affects results; both raw and timing-adjusted figures are reported.
- Screener.in's own provenance (who supplies Screener) is out of scope.
- Files: `stock_comparison.csv` (stock × statement, plus ALL rows), `detailed_mismatches.csv` (every non-exact cell with explanation), `source_evidence.json` (method, fingerprints, full results). Code: `fingerprint/`.
