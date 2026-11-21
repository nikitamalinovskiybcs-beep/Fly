# AICS V29 — original SEC loan maturities, pricing spreads, agent roles and refinancing calendar

**Research cutoff:** 22 November 2026. **Goal:** distinguish the 2000-style infrastructure buildout overhang from actual timing of potential 2008-style funding transmission. This is a **research-only contractual terms overlay**, not a third historical analog or an actionable credit-default model. The frozen 11 node weights total **1050** and may not change automatically.

## New source-verified contractual terms

| Borrower and facility | First possible AICS eligible date (SEC filed +14) | Contractual maturity | Draw commitment terminates | Term-defined floating margin | Required minimum DSCR (not actual) | Source |
|---|---|---|---|---|---|---|
| CoreWeave Compute Acquisition Co. VIII — DDTL 4.0 | 2026-04-14 (8-K filed 2026-03-31) | **2032-03-31** | 2027-06-30 | Daily compounded SOFR + **225 bps** | **1.15x** | [Original 8-K](https://www.sec.gov/Archives/edgar/data/1769628/000176962826000129/crwv-20260330.htm) |
| CoreWeave Financing DDTL V — DDTL 5.0 | 2026-06-01 (8-K filed 2026-05-18) | **2031-11-15** | 2026-09-30 | Daily compounded SOFR + **450 bps** | **1.35x** | [Original 8-K](https://www.sec.gov/Archives/edgar/data/1769628/000176962826000236/crwv-20260515.htm) |
| Nebius Group N.V., Nebius Inc., Nebius B.V. — Citi bridge | **2026-11-05** (6-K filed 2026-10-22) | **2027-10-16** | Not established from the source | **Term SOFR + 275 bps** initially; +25 bps per 90-day period after 2026-10-17, up to 350 bps, subject to adjustments | Minimum liquidity covenant, no quantified DSCR | [Original 6-K](https://www.sec.gov/Archives/edgar/data/1513845/000110465926117978/tm2628078d1_6k.htm) |

The contractual **capacities**, respectively **$8.5bn, $3.1bn and $3.5bn**, are **not** evidence of the outstanding or currently drawable loan amounts, and must not be summed as current debt.

CoreWeave's original [2026 Q2 10-Q](https://www.sec.gov/Archives/edgar/data/1769628/000176962826000366/crwv-20260630.htm) separately confirms **reported debt of $2.837bn on DDTL 4.0** and **$1.101bn on DDTL 5.0 at June 30, 2026**. These values become AICS source-eligible only on **2026-08-26**. They are **historical June balances**, not November 2026 current lender positions. The issuer also described monthly amortization of DDTL 5.0 beginning November 2026 with expected final payment in May 2031. That projection must not override the original **November 15, 2031 legal maturity**.

The original DDTL 4.0 **1.15×** covenant begins testing according to the loan's termination/draw and site-specific conditions; DDTL 5.0 **1.35×** likewise follows its contractual trigger. No actual measured DSCR or breach is reported here. The floating spreads are **not current coupon yields**: SOFR observations, hedge fixings, selected rate basis and true drawn balances are not applied.

## Named financing parties — role is NOT dollar credit exposure

| Named entity in original filing | Verified legal/operational role | True lender balance independently attributed? |
|---|---|---|
| **MUFG Bank, Ltd.** | Administrative agent for CoreWeave DDTL 4.0; also lead co-arranger | **No** |
| **Morgan Stanley Senior Funding, Inc.** | Administrative agent for DDTL 5.0; lead co-arranger | **No** |
| **Morgan Stanley Asset Funding, Inc.** | Lead co-arranger of DDTL 4.0 | **No** |
| **U.S. Bank Trust Company, National Association** | Collateral agent for both facilities | **No** |
| **Citibank, N.A.** | Mandated lead arranger **and lender** for the Nebius one-facility $3.5bn bridge | **No funded Citi dollar amount** |

For Nebius, naming Citi as a lender is stronger than a merely unidentified loan arranger. However, the SEC 6-K **does not state that Citi itself funded the entire $3.5bn**, nor does it certify any current amount drawn. For CoreWeave, DDTL 4.0 carries **limited bad-act parent recourse**; DDTL 5.0 carries an **unconditional parent guarantee with unquantified effective parent loss exposure**.

## Chronological result

- As of **2026-04-13**, no V29 8-K/6-K contract in this three-contract subset is available. From **2026-04-14**, DDTL 4.0 contractual terms can appear in research.
- From **2026-06-01**, both CoreWeave contract terms are available; their reported Q2 balances **cannot** enter a contemporaneous model until **2026-08-26**.
- From **2026-11-05**, the Nebius bridge maturity and pricing details become available under SEC +14.
- On **2026-11-22**, the known Nebius bridge **2027-10-16 contractual maturity is inside 365 calendar days**, while the two CoreWeave contractual maturities are in **2031 and 2032**. A known *maturity date* is not a known amount that has to be refinanced at that date.

This provides a genuine **timing axis** for AICS—pressure from cash-capex imbalance can coexist with contractual near-term funding risk in a different issuer. It **does not demonstrate** a bank credit run, a realized default, 2000-vs-2008 probability, or comparable historical ahead-of-market predictive lead time.

## Implementation

- [Three-source primary SEC contract ledger](../aics_data/research/aics_v29_contractual_refinancing_terms_primary_sec_2026-11-22.json)
- [Contractual-only maturity overlay](../scripts/aics_v29_refinancing_maturity_overlay.py), strict SEC+14 chronology checks, separation of 2026-06 historical debt from current balances
- [Fail-closed loan terms tests](../tests/test_aics_v29_refinancing_maturity_overlay.py), rejecting forged SOFR margins, maturities, agent roles, covenant ratios and current lender exposure claims
- [ModelChallenger and CreditContagionAnalyst](../scripts/aics_ten_model_improvement_agents.py) now receive source-limited maturity evidence, and [30-agent coordinator](../scripts/aics_thirty_agent_cycle.py) preserves `0` verified lender-by-lender current dollar exposures
- [CI integrated cycle](../.github/workflows/aics-ten-real-source-waves.yml) outputs an archived V29 research JSON inside the source-wave artifact, without trading or production changes

**Outstanding controls:** This subset's original 8-K/6-K URLs and terms have been rechecked against SEC originals and SEC filing indexes; raw first-filed bytes **were not independently rehashed or independently historially PIT attested in this V29 ledger**. Do not use these contractual terms to assert historical source receipt certification. No untouched fixed 24-month OOS, no crisis probability, no approved full AICS score.

**Next highest-value source task:** Identify exact per-lender funded balances/collateral and complete short-term obligation maturities for CoreWeave, Nebius and Nscale, then link into insurer/BDC counterparty exposure. Do not infer a lender loss from the mere presence of a bookrunner, administrative agent or collateral agent.
