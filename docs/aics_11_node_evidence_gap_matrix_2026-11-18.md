# AICS evidence gap closure matrix — 2026-11-18

Source reconciliation: original package at as-of **2026-11-30** has six eligible *unverified proxy* rows across two nodes, weighted 250/1050 (23.81%). The date is a **future committee target**, not today's live as-of score. Separate authenticated GitHub Actions ALFRED artifact contains four source series and 96 month-end snapshots ending 2026-10-31; source series must not be counted as scored nodes.

| Node | Weight | Original eligible rows | State / next evidence |
|---|---:|---:|---|
| Private Credit | 150 | 5 | PROXY_UNVERIFIED; independently attest underlying filings, calibrate 0–100 score |
| Insurers | 125 | 0 | MISSING; identify PIT insurer exposure and source timestamps |
| UST 30Y | 125 | 0 | MISSING in original package; DGS30 ALFRED source collected separately, score calibration and independent as-of attestation pending |
| Neoclouds | 100 | 1 | PROXY_UNVERIFIED; corroborate and calibrate |
| AI Equities | 100 | 0 | MISSING; predeclare equity universe and PIT price/volatility method |
| Hyperscalers | 100 | 0 | MISSING; primary filing data and SEC +14-day gate |
| SPV | 100 | 0 | MISSING; primary deal/funding disclosures and availability dates |
| Repo | 100 | 0 | MISSING; dated funding series and calibration |
| Power/Data Centers | 50 | 0 | MISSING; dated power capacity/financing evidence |
| Semiconductors Supply | 50 | 0 | MISSING; dated semiconductor supply evidence |
| AI Demand | 50 | 0 | MISSING; dated demand and contract evidence |

## Ten execution gates and status

1. Immutable weights sum 1050: **verified**.
2. Original 11-node inventory: **verified**.
3. Original reconciliation on supplied archive: **verified, 6 eligible rows**.
4. SEC 14-day lag in original reconciliation: **three records excluded**, primary EDGAR provenance pending.
5. ALFRED 4-series artifact: **96 snapshots structurally verified**, independent source verification pending.
6. Score gate implementation: **committed**, nine policy unit tests now included in CI.
7. Source-to-node mapping: **documented**, not promoted to score.
8. Historical 646.3/650.7 reproduction: **blocked**, original 11-node inputs missing.
9. 24-month untouched OOS performance: **blocked**, no independently validated score series.
10. Committee approval and trading: **blocked**, no approval or trades.

**No synthetic data, no backfill, no current FRED used as historical vintage, no invented numerical index.**

## Immediate acceptance criteria
For each of 11 nodes supply source file SHA256, immutable source URI, observation period, as-of timestamp, independently verified availability date, versioned normalization and training cutoff. SEC evidence must use available_at >= filed_at + 14 calendar days. Only then recompute claimed versions with the reproducibility gate, followed by OOS tests. AICS and predictive model score remain N/A.
