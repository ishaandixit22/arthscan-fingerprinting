# Three-way data provider fingerprinting: Tapetide, Screener.in, Indian Stock API

Updated 2026-11-06T14:48:09Z. Baseline snapshot `20261102T062632Z_baseline`; 99 snapshot(s) in total. 10 stocks.

> **Labelling:** every Indian Stock API observation in this report is **ARTHSCAN-cached data** (ARTHSCAN's stored copy of the provider's response, with its own `fetched_at`), not a direct observation of indianapi.in.

## Conclusion

- **Direct Screener sourcing: inconclusive, leaning supported (release-timing test pending).**
- **Shared upstream provider: not supported for Indian Stock API as Tapetide's feed; inconclusive for any other Screener-format reseller.**
- **Independent compilation: partly supported: Tapetide's provisional new quarters and filing overrides are its own; its compiled historical base is not independent.**

Tapetide runs two layers. Its **compiled base** is Screener-format and matches Screener cell for cell. On top, it has **its own filing layer**: provisional new quarters built from company filings, and historical cells replaced with the filed figure (its MCP flags these `cell_source: filing`). Every historical value difference in the quarterly tables traces to that layer.

Indian Stock API is also Screener-format, but Tapetide shares none of Indian Stock API's state and carries new quarters it lacks, so Indian Stock API is not Tapetide's feed. What this test cannot separate is direct Screener sourcing from another reseller of Screener-format data; the release-timing test is designed for that. None of this establishes a commercial relationship.

## Pairwise agreement (baseline, same basis only)

| Pair | Cells | Match % | Focus rows* match % |
|---|---:|---:|---:|
| Tapetide vs Indian Stock API (ARTHSCAN-cached) | 5,606 | 97.09% | 94.85% |
| Tapetide vs Screener | 5,641 | 96.44% | 93.96% |
| Indian Stock API (ARTHSCAN-cached) vs Screener | 5,652 | 95.49% | 92.98% |

*Other Income, Depreciation, Profit before tax, Net Profit, EPS, Operating/Financing Profit.

Where all three have a value: all agree on 5,354 cells; Tapetide = Indian Stock API ≠ Screener on 45; Indian Stock API = Screener ≠ Tapetide on 31; Tapetide = Screener ≠ Indian Stock API on 18. Most disagreements are timing (a source missing the newest quarter or TTM window) rather than different figures.

## Answers

**A. Does Tapetide match Screener's values first?** Tapetide's compiled values equal Screener's, but its newest quarters are often provisional figures from filings, which match Screener without being copied; release-time test pending. Of 8 stocks that have reported Sep 2026, Screener has the quarter for 8, Tapetide 7, Indian Stock API 2. Every value Tapetide shows for the new quarter equals Screener's except one ZEEL cell (Interest 3 vs 2).

**B. Does Tapetide match Indian Stock API's values first?** No. Tapetide has the new quarter for QUICKHEAL, RELIANCE, TRENT, WELSPUNLIV, ZEEL while Indian Stock API does not. QUICKHEAL is the clearest case: Indian Stock API still lacked Sep 2026 on 1 Nov 18:30 UTC, five days after the filing.

**C. Does Indian Stock API reproduce Screener's unusual derived rows?** Yes: Operating Profit 234/234, OPM % 234/234, Other Liabilities 110/110, Other Assets 122/122; `EPS in Rs`, `CFO/EBITDA`, the TTM column and Screener's finance-company row order. It shares none of Tapetide's own changes (`CFO/OP`, reordered finance rows, filing overrides).

**D. Which platform publishes newly reported quarters first?** Screener, then Tapetide, then Indian Stock API (baseline ordering); minutes-level latency pending release monitoring. TRENT filed at 10:51 UTC on 29 Oct; Indian Stock API's copy 12 hours later still lacked the quarter.

**E. Are the unexplained historical values identical?**

- Tapetide filing override; Screener = Indian Stock API: 19
- missing on Tapetide (newest-quarter gaps): 7
- Tapetide = Indian Stock API, Screener differs: 5
- Indian Stock API = Screener, Tapetide differs: 2
- agree within rounding: 2
- missing / n/m on Tapetide (historical): 1
- all three differ / insufficient data: 1

Every Tapetide-only difference in the quarterly tables is flagged by Tapetide's own MCP (flags checked for all 10 stocks); the 2 remaining are in annual tables, which the flags do not cover. PIIND's seven quarterly differences and two of ABCAPITAL's are flagged by Tapetide's own MCP as `cell_source: filing` (the company's filed figure replacing the compiled value); Indian Stock API equals Screener on all of them. ABCAPITAL Sep 2025 (Other Income 92 vs 170, PBT 1,212 vs 1,290, Net Profit 882 vs 961, EPS 3.27 vs 3.57) is the one case where Tapetide equals Indian Stock API and Screener differs; both Tapetide and Indian Stock API also lack ABCAPITAL's Sep 2026 quarter, so this looks like an older shared state rather than a shared error.

**F. Is there evidence of a shared upstream provider?** Indian Stock API and Tapetide both carry Screener-format data, but Tapetide shows no Indian Stock API-specific dependence and is ahead of it on new quarters. A common origin for Screener-format data is consistent with the evidence but unidentified.

## Tapetide's two-stage pipeline

| Stage | Stocks (Sep 2026) | Evidence |
|---|---|---|
| Provisional, from the filing | WELSPUNLIV (filed 2026-10-30), JSL (filed 2026-10-22), ZEEL (filed 2026-10-30), QUICKHEAL (filed 2026-10-27) | MCP `provisional_periods`; EPS always blank, WELSPUNLIV also blank Operating Profit, OPM % and Other Income; every filled value equals Screener's except ZEEL Interest |
| Compiled, Screener-format | CYIENT, TRENT, RELIANCE | Complete quarter, all cells equal to Screener |

This matters for answers A and D: a provisional quarter matching Screener does not show that Tapetide copied Screener, because filing figures are the same numbers. The release-timing test therefore tracks when each stock moves from provisional to compiled on Tapetide, and compares that with Screener and Indian Stock API.

## Release monitoring (Phase 4)

**Status: not complete.** No T+48h checkpoint has been captured yet, so no release-timing conclusion is drawn.

- Scheduler: claude.ai cloud scheduled task (server-side cron that wakes this persistent Claude session); not OS cron, launchd, GitHub Actions or a daemon; `CRON_TZ=Asia/Kolkata 13 8-23 2-7 11 *` (hourly at :13, 08:13-23:13 IST, 2-7 Nov 2026); trigger `trig_0159bajz89RVbmpSSciinzwJ`.
- Ticks logged so far: 101 (last 2026-11-06T14:44:03.911683+00:00); T0 events recorded: 2.
- Restart safety: yes: state, evidence, code and immutable snapshots are pushed to ishaandixit22/arthscan-fingerprinting (branch monitor-state) after every checkpoint; restore from a fresh GitHub clone was tested on 2026-11-02 with all 81 snapshot hashes identical.

| Company | Checkpoint | Source | Called (UTC) | Source timestamp | Latest period | Tapetide provisional | cell_source flags |
|---|---|---|---|---|---|---|---|
| PIIND | T0/T+30m | Tapetide MCP | 2026-11-04T14:45:47.557333+00:00 | 2026-10-21T06:29:42.208Z | Jun 2026 | None | 2 |
| PIIND | T0/T+30m | Indian Stock API (ARTHSCAN-cached) | 2026-11-04T14:45:47.557333+00:00 | None | None |  | 0 |
| PIIND | T+2h | Tapetide MCP | 2026-11-04T17:39:14.358353+00:00 | 2026-10-21T06:29:42.208Z | Jun 2026 | None | 2 |
| PIIND | T+2h | Indian Stock API (ARTHSCAN-cached) | 2026-11-04T17:39:14.358353+00:00 | None | None |  | 0 |
| MOTHERSON | T0 | Tapetide MCP | 2026-11-05T09:45:59.945054+00:00 | 2026-10-06T01:39:33.372Z | Jun 2026 | None | 0 |
| MOTHERSON | T0 | Indian Stock API (ARTHSCAN-cached) | 2026-11-05T09:45:59.945054+00:00 | None | None |  | 0 |
| PIIND | T+24h | Tapetide MCP | 2026-11-05T14:48:10.671678+00:00 | 2026-10-21T06:29:42.208Z | Sep 2026 | [{'period': 'Sep 2026', 'filed_on': '2026-11-04'}] | 12 |
| PIIND | T+24h | Indian Stock API (ARTHSCAN-cached) | 2026-11-05T14:48:10.671678+00:00 | None | None |  | 0 |
| MOTHERSON | T+24h | Tapetide MCP | 2026-11-06T09:47:28.727461+00:00 | 2026-10-06T01:39:33.372Z | Jun 2026 | None | 0 |
| MOTHERSON | T+24h | Indian Stock API (ARTHSCAN-cached) | 2026-11-06T09:47:28.727461+00:00 | None | None |  | 0 |
| PIIND | T+48h | Tapetide MCP | 2026-11-06T14:48:05.743179+00:00 | 2026-10-21T06:29:42.208Z | Sep 2026 | [{'period': 'Sep 2026', 'filed_on': '2026-11-04'}] | 12 |
| PIIND | T+48h | Indian Stock API (ARTHSCAN-cached) | 2026-11-06T14:48:05.743179+00:00 | None | None |  | 0 |

| Company | T0 (exchange, UTC) | Detected after | Checkpoints taken |
|---|---|---:|---|
| PIIND | 2026-11-04T14:10:36+00:00 | 33.6 min | T0, T+30m (4.5 min late), T+2h (4.4 min late) |
| MOTHERSON | 2026-11-05T09:28:36+00:00 | 15.3 min |  |

First snapshot (minutes after T0) in which each source showed the new quarter:

- PIIND: tapetide 1474.7, screener 1474.8, indianapi_arthscan_cache not yet
- MOTHERSON: tapetide not yet, screener 196.4, indianapi_arthscan_cache not yet

## What ARTHSCAN should integrate independently

| Dataset | Integrate directly | Instead of |
|---|---|---|
| Financial statements | NSE/BSE XBRL results filings (the NSE results feed links each filing's XBRL), with ARTHSCAN's own documented derived rows | Indian Stock API statements, which are Screener-format and were the slowest source here |
| Corporate filings, board meetings, corporate actions | NSE/BSE announcement feeds and archives (already partly used) | Third-party summaries |
| Shareholding pattern | NSE/BSE XBRL shareholding filings | Indian Stock API shareholding |
| Mutual funds | AMFI daily NAV file and monthly reports | Indian Stock API mutual funds |
| IPOs | NSE/BSE issue pages and bid data, SEBI offer documents (already used) | Aggregators; label any GMP as unofficial |
| Credit ratings | Rating agency press releases (CRISIL, ICRA, CARE, India Ratings) | Aggregated rating feeds |
| Prices | Keep NSE end-of-day files and the licensed Dhan live feed | |
| Analyst forecasts | A licensed estimates vendor under a direct contract | Indian Stock API forecasts, whose provenance is unclear |

Before redistributing any Screener-format data, ARTHSCAN should check the redistribution terms of every provider in its chain.

## Files

- `timestamped_snapshots.csv`: every numeric cell from every snapshot, with fetch time, source timestamp, precision and file hash.
- `provider_comparison.csv`: per stock, statement and pair.
- `update_latency.csv`: latest periods, TTM window and new-quarter completeness per source per snapshot, plus timing references.
- `unexplained_differences.csv`: the Phase 1 unexplained cells for these stocks, with current values from all three sources.
- `source_attribution.json`: answers A-F with evidence, verdicts, Tapetide's disclosed filing layer and monitoring state.
- Raw immutable snapshots: `three_way/snapshots/`. Code: `three_way/`.
