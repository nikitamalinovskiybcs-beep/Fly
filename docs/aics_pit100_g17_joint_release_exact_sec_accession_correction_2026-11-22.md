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

## Verified follow-up: 36 of 36 original source documents recovered

The corrected dual-calendar SEC filing-clock workflow [45013754247](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/45013754247) ended **SUCCESS**; full original-source artifact [14751177481](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/45013754247/artifacts/14751177481). Its live source-data lines show:

- **9/36** source accessions originally identified in the general 100-file batch.
- **27/27** missing **exact original issuer scoring source documents and SEC SGML index headers** successfully downloaded and SHA-256 archived, **0** live targeted download failures.
- **36/36** now have relevant original accession and verified SEC original-header source bytes; this covers the **19/19** original research source cohorts at the original-document identity level.
- **7 of the 27 newly retrieved original headers** had a different calendar day for **`<ACCEPTANCE-DATETIME>` vs `FILED AS OF DATE`**, which is legal for after-hours acceptance. The old check wrongly rejected two CoreWeave accessions: original 2025 Q1 accepted May 14 after close, formally filed May 15; original 2025 Q2 accepted August 12 after close, formally filed August 13. The new implementation preserves and validates both SGML source clock fields separately.
- **0 independently validated original accounting numeric values** extracted from these 36 source documents. **0/11** true independently historical PIT-certified nodes. An acceptance time—even perfectly independently verified against the original SGML—is **not** the first public dissemination receipt.

The same full run recorded two independent 24-month original-event reconstructions agreeing with **0 remaining node-month differences**, 48/48 actual original ALFRED date-asof API requests, and fixed-three-node 23-pair ex-post S&P next-month correlation **−0.135**. The G.17 correction gives October-2025 **74.70** and November-2025 **74.40** in their jointly published Dec23 event, with November the latest measurement visible by December month-end.

This outcome genuinely resolves the **document identity and original-file source completeness** gap for these 19 event cohorts; it does **not** resolve the underlying missing historical public-availability receipts, original financial line item parsing, 11-node certification or 24month untouched OOS forecasting.


**Code:** [exact 36-source accession crosswalk](../scripts/aics_pit100_original_scoring_accession_lineage.py), [targeted source accession gap-fill](../scripts/aics_pit100_target_exact_missing_sec_sources.py), [live 100-primary-source collector workflow](../.github/workflows/aics-ten-real-source-waves.yml).

## Formal readiness and next actual work

**Latest verified successful run 45013754247:** 27/27 targeted source documents were fetched; all 36 source accession references are now archived; two independent monthly reconstructions agree 24/24. Nevertheless, neither historical first-feed receipts nor underlying accounting amounts are independently certified.

- **22/66 signed research milestones** (~33/100 project construction, not forecast accuracy).
- **0/11 independent fully historic PIT-certified node histories.**
- **No complete 11-node AICS**, no approved crisis probability or 2000/2008 pre-onset lead-time, no independent untouched 24-month predictive backtest.
- Fixed original source research weights **1050**, no auto trading and no falsely reported financial lender-to-SPV exposures.

**Next decisive proof:** verify exact source document bytes for the missing 27 accessions, then extract relevant original financial values and cross-reference historical release timing for all remaining nodes. Original acceptance timestamp is not a historical first-public-dissemination attestation.
