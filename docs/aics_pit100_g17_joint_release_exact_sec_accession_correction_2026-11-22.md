# AICS PIT100 — Source corrections: Fed G.17 dual release and exact SEC source lineage

**22 November 2026 — PIT audit follow-up.** This note supersedes the old claim that G.17 NAICS 3344's December 23, 2025 October and November observations are conflicting records. Original numbers have not been changed, filled or averaged. The earlier quarantine policy was wrong because it keyed by **(node, publication day)** instead of **(node, publication day, measurement period)**.

## Verified original Federal Reserve source

The Federal Reserve [archival G.17 release dated 2025-12-23](https://www.federalreserve.gov/releases/g17/20251223/table7.htm) explicitly published **October and November 2025** together after the government-shutdown release delay, as confirmed in its [technical explanation](https://www.federalreserve.gov/releases/g17/g17_technical_qa.htm) and official report to OMB.

| Industrial subsector | Measured month | Public release date | Originally recorded NAICS 3344 capacity utilization |
|---|---|---|---:|
| Semiconductors and related electronic components | **October 2025** | **2025-12-23** | **74.70%** |
| Semiconductors and related electronic components | **November 2025** | **2025-12-23** | **74.40%** |

The date is shared because these are **two different measured months in one release**, not two revised estimates for one month. For the December 2025 market/calendar month-end research date, the **latest observation-month candidate is 74.40% for November**, replacing the previously carried September candidate **75.50%** from December 3. The scalar difference is **−1.10 percentage points**, corresponding to **−0.55 incomplete weighted research points** at its fixed 50/1050 node weight. It must **not** be treated as a certified crisis signal: source age and original publisher first-feed receipt remain unverified.

The corrective code now (1) validates the date and both measured-month values against the original research source ledger, (2) distinguishes measurement period from publication date, (3) applies consistent selection in two independent 24-month market/calendar reconstructions and (4) rejects only **true same-source/same-measured-period** incompatible values. No +14-day artificial SEC delay is reintroduced.

**Code**: [first replay](../scripts/aics_pit100_rebuild_24m_research.py), [second replay](../scripts/aics_pit100_rebuild_24_month_public_filing_panel.py), [reconciliation](../scripts/aics_pit100_reconcile_24m_sp500.py).

## Specific SEC documents underlying original AICS source events

The original source ledgers identify **36 separate actual SEC accession references** underpinning **19 distinct retrospective event cohorts**:

| Risk node | Event cohorts | SEC issuer documents | Original issuers |
|---|---:|---:|---|
| Insurers | 9 | 9 | Prudential |
| Private Credit | 7 | 21 | ARCC, BXSL, OBDC |
| Neoclouds | 3 | 6 | CoreWeave, Nebius |
| **Total** | **19** | **36** | Six named issuer identities |

These are **document-level lineage candidates**, not independent confirmations of disclosed accounting amounts. Previously gathered samples of **100 real SEC filings** were only partly relevant. In [run 45012640332](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/45012640332) the completed source-accession step found **9 of 36** precise accession + original SGML header matches; **5 of 19** event cohorts had all necessary accession/header matches. (That workflow later failed at an unrelated test assertion checking the string formatting of an already accepted G.17 number; this source-match step itself completed.)

A new targeted collector only requests the **missing 27 exact issuer report documents** and their respective official original SEC index headers, records both original file SHA-256 values, or explicit HTTP/source failures. Unlike fetching 100 recent filings, the targeted archive is now tied to the economic indicator’s referenced accession. This does **not** certify original provider availability at the historical trading close, nor does matching a document mean the reported balance or ratio has been independently extracted from that document.

**Code:** [exact 36-source accession crosswalk](../scripts/aics_pit100_original_scoring_accession_lineage.py), [targeted source accession gap-fill](../scripts/aics_pit100_target_exact_missing_sec_sources.py), [live 100-primary-source collector workflow](../.github/workflows/aics-ten-real-source-waves.yml).

## Formal readiness and next actual work

The newest integration run will archive the linked SEC documents, G.17 two-month correction, S&P500 research context and ALFRED day-asof snapshots as separate source evidence. **Do not assume all targeted fetches succeeded until reviewing the resulting run manifest**.

- **22/66 signed research milestones** (~33/100 project construction, not forecast accuracy).
- **0/11 independent fully historic PIT-certified node histories.**
- **No complete 11-node AICS**, no approved crisis probability or 2000/2008 pre-onset lead-time, no independent untouched 24-month predictive backtest.
- Fixed original source research weights **1050**, no auto trading and no falsely reported financial lender-to-SPV exposures.

**Next decisive proof:** verify exact source document bytes for the missing 27 accessions, then extract relevant original financial values and cross-reference historical release timing for all remaining nodes. Original acceptance timestamp is not a historical first-public-dissemination attestation.
