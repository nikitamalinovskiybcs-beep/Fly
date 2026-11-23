# AICS Insurers — MetLife Q3 2026 newly SEC+14 eligible

**Research as-of:** 2026-11-20 (calendar-date cutoff). **Status:** primary filing inspected; Q3 full-submission byte-level replay and independent SHA-256 **NOT YET COMPLETED**. This is a research observation, not an attested historical PIT vintage, insurer stress score or trade signal.

## What changed today

The previous 2026-11-19 *asymmetric* PRU-Q3 / MET-Q2 panel was correct at its frozen information cutoff. The [MetLife September 2026 10-Q](https://www.sec.gov/Archives/edgar/data/1099219/000109921926000062/met-20260930.htm) was **filed 2026-11-06**, accession `0001099219-26-000062`, period ended **2026-09-30**. Strict project rule `filed_at + 14 calendar days` first permits use on **2026-11-20**. The Q3 filing must never be backdated into November 19 or earlier AICS information sets. SEC [filing index](https://www.sec.gov/Archives/edgar/data/1099219/000109921926000062/0001099219-26-000062-index.htm) identifies a **43,289,538-byte complete submission**, but these actual bytes were **not independently downloaded/rehashed for this new slice**.

MetLife Q2 is separately sourced from its [June original 10-Q](https://www.sec.gov/Archives/edgar/data/1099219/000109921926000050/met-20260630.htm), filed August 6 / available August 20, with full-source independent rehash recorded in `aics_data/research/met_2026q2_original_sec_acl_independent_rehash_2026-11-19.json`. The comparison below is a **newly eligible quarter-on-quarter source comparison**, *not* a reconstruction of what historical data feeds delivered in June or September.

## MetLife observed mortgage credit bridge

Amounts in **USD millions**. The Q3 source is the original [consolidated balance sheet and Note 9 ACL rollforward](https://www.sec.gov/Archives/edgar/data/1099219/000109921926000062/met-20260930.htm).

| Observable | 2026-06-30 (eligible Q2 filing) | 2026-09-30 (eligible Q3 filing) | Quarter movement |
|---|---:|---:|---:|
| Net mortgage loans | 82,856 | 83,839 | **+983 (+1.19%)** |
| Mortgage allowance for credit losses (ACL) | 1,358 | 1,521 | **+163 (+12.00%)** |
| Commercial-mortgage ACL | 1,016 | 1,127 | +111 |
| Agricultural-mortgage ACL | 107 | 126 | +19 |
| Residential-mortgage ACL | 235 | 268 | +33 |
| Descriptive ACL / (net mortgages + ACL) proxy | 1.61% | 1.78% | **+0.17 percentage point** |

The Q3 document itself reports *nine months* of ACL **provision 546** and **net charge-offs 218**, versus the independent eligible Q2 report's **six-month provision 316** and *net charge-offs 151*. The incremental third-quarter bridge is **provision 230**, **net charge-offs 67**, and exactly **1,358 + 230 − 67 = 1,521**. Nine-month independent within-filing reconciliation: **1,193 + 546 − 218 = 1,521**. Q3 commercial mortgage ACL accounts for **74.10%** of total ending mortgage ACL. These reserve movements are not observed default probabilities.

## What the aligned September dates do and do not establish

Prudential Financial Q3 2026 was already eligible on **2026-11-18** and its independently original-replayed PFI-excluding-Closed-Block Level-3 private fixed maturities were **$12.510bn**, **91.55%** of scoped Level-3 fixed maturities. PRU's distinct net *commercial mortgage and other loans* were **$67.004bn**, with a **$610m** subset of nonaccrual loans *without associated allowances*.

MetLife's September mortgage ACL measures an **expected-loss reserve across its commercial, agricultural, and residential mortgage portfolios**; PRU's $610m is a **specific unreserved nonaccrual subset**, not its entire loan reserve. Thus, **the two issuer statement dates are now aligned at September 30**, but the loan/risk categories **are not comparable**, and their numerators must not be ranked or aggregated. Private Level 3 is a valuation-input category, not an impairment/default or AI exposure category.

## Evidence status and next required original-source check

- Q3 values above were transcribed and arithmetically reconciled against publicly displayed original SEC 10-Q balance-sheet and ACL Note 9 tables. They are **not yet verified by replaying a fresh complete-submission SHA-256 checked source bundle**, unlike the earlier Q2/PRU original replays. Q3 full original SHA-256 is deliberately **null**, not guessed.
- The December 2025 comparatives in the later reports do **not** create a December 2025 point-in-time archive. SEC date eligibility does **not** prove historical delivery-time capture by an independent provider.
- Next: fetch the **43,289,538-byte original Q3 SEC submission**, independently SHA-256 hash its bytes, replay its embedded Q3 mortgage and ACL note, and pin a durable receipt. Then retrieve statutory NAIC/RBC and reinsurance credit-risk disclosures in their correct issuer and publication scope.
- Retain **22/66 technical milestones**, **0/11 independent historic PIT**, **0/11 certified nodes**, **AICS = N/A**; weights remain 1050. No promotion, no trading.

Machine-readable review: `aics_data/research/met_2026q3_sec_newly_eligible_credit_bridge_2026-11-20.json`.
