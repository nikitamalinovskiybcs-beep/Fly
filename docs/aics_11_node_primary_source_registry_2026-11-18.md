# AICS — primary-source acquisition plan for all 11 nodes (2026-11-18)

This is a **source registry**, not 11 downloaded, independently attested node-score histories. Every series below must pass historical availability checks; FRED revisable series must be queried by ALFRED vintage. No synthetic values or backfilling.

| Node | W | Real primary source / retrieval path | Data gap / PIT rule |
|---|---:|---|---|
| Private Credit | 150 | SEC EDGAR companyfacts https://data.sec.gov/api/xbrl/companyfacts/ ; existing ALFRED BAMLH0A0HYM2/BAMLH0A3HYC | Credit spreads are **not** private-credit exposure; SEC issuer coverage and as-of validation required |
| Insurers | 125 | NAIC https://content.naic.org/ ; SEC EDGAR insurer 10-K/10-Q | NAIC exposure series availability/licensing and insurer universe need validation; SEC +14 days |
| UST 30Y | 125 | Treasury https://home.treasury.gov/resource-center/data-chart-center/interest-rates ; ALFRED DGS30 | Existing real vintage source; calibration and independent provenance pending |
| Neoclouds | 100 | SEC EDGAR https://www.sec.gov/search-filings ; issuer earnings/filings | Original archive contains one unverified proxy; issuer universe and SEC +14 days required |
| AI Equities | 100 | Nasdaq official historical market data https://www.nasdaq.com/market-activity ; SEC company universe | Predeclare basket, timestamped adjusted price methodology, licensing |
| Hyperscalers | 100 | SEC EDGAR companyfacts/submissions https://data.sec.gov/ | Fixed issuer list, CAPEX XBRL tags and SEC +14 days |
| SPV | 100 | SEC EDGAR submissions and issuer 8-K https://data.sec.gov/submissions/ | Private deal disclosure incomplete; publication timestamp and deal identity |
| Repo | 100 | NY Fed SOFR https://www.newyorkfed.org/markets/reference-rates/sofr ; ALFRED SOFR | SOFR is partial proxy, not a complete repo stress index |
| Power/Data Centers | 50 | EIA electricity API https://www.eia.gov/opendata/ ; EIA AEO2026 https://www.eia.gov/outlooks/aeo/ | EIA power demand not necessarily data-center-specific; forecast vintage and revisions |
| Semiconductors Supply | 50 | Federal Reserve G.17 https://www.federalreserve.gov/releases/g17/ ; FRED semiconductor industrial production https://fred.stlouisfed.org/tags/series?t=semiconductors | Historical G.17/ALFRED vintages and capacity utilization calibration |
| AI Demand | 50 | SEC EDGAR companyfacts and filings https://data.sec.gov/ | AI-specific orders/backlog often not standardized XBRL; SEC +14 days |

**Source authenticity != data retrieval != independent PIT verification != node score.** The existing authenticated ALFRED archive provides four actual source series, candidate mappings for three nodes only. A further original-package Neoclouds proxy is unverified. No numerical score is promoted without all eleven independently verified 0–100 node scores and versioned methodology.

## Data acquisition gates
1. Define fixed issuer/security universes before looking at future outcomes.
2. Retrieve actual raw values and original publication metadata from primary sources; hash raw files.
3. SEC available_at = filed_at + 14 calendar days. ALFRED must use realtime_start = realtime_end = historical as_of.
4. Validate dates, coverage, unit normalization, stale data, missingness, revision histories.
5. Produce independently attested source-to-score lineage and untouched out-of-sample testing; never interpret a green CI as source certification.

References: SEC official EDGAR APIs https://www.sec.gov/search-filings/edgar-application-programming-interfaces ; EIA official open data https://www.eia.gov/opendata/v1/ ; Federal Reserve G.17 https://www.federalreserve.gov/releases/g17/ .
