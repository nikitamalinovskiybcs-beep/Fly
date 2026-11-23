# AICS V30 — source-verified Q1→Q2 2026 cashflow and financing mechanisms

**Research date:** 2026-11-22. **Scope:** CoreWeave and Nebius, original SEC-sourced calendar-quarter cash purchases and *net cash financing activities*, denominated in USD million. These are two issuer-level statements, **not** the sum of the four hyperscalers, a bank-by-bank debt map, or a new AICS score.

## Actual Q2 observations, available only on 2026-08-26 under SEC+14

| Metric, USD million | CoreWeave Q2 2026 | Nebius Q2 2026 |
|---|---:|---:|
| Cash from operations (OCF) | 679.0 | 2,246.1 |
| Gross cash capital purchases | (6,422.0) | (5,657.4) |
| **OCF − purchases** | **−5,743.0** | **−3,411.3** |
| Total net investing cash flows (not identical to cash CapEx) | −7,166.0 | −5,645.7 |
| **Net cash provided by financing activities** | **+10,071.0** | **+2,864.9** |
| Cash FX effect separately reported | Not separately itemized | +5.9 |
| **Change in cash including restricted** | **+3,584.0** | **−528.8** |
| Cash, including restricted, beginning → end | 3,320.0 → 6,904.0 | 9,626.9 → 9,098.1 |

Accounting check, **same period, same issuer, all USD million**:

- CoreWeave: **679 − 7,166 + 10,071 = +3,584**.
- Nebius: **2,246.1 − 5,645.7 + 2,864.9 + 5.9 = −528.8**.

Do not replace total investing cash flows with the narrower gross cash capital purchase measure when reconstructing the change in cash. The *difference* covers other investing operations. CoreWeave purchases include capitalized internal-use software; Nebius 2026 purchases include PP&E **and intangibles** from continuing operations. Those are original issuer-specific definitions, not a harmonized AI-only GPU spending series.

## Why funding mechanisms differ

**CoreWeave, Q2 2026 financing cash:** +13,457 of debt issuance net of costs, −3,884 of debt repayments, +997 private placement net of costs, −492 capped-call purchases and −7 other financing = **+10,071**. This does not mean the entire net funding was new DDTL 4.0/5.0 loans or that specific banks funded the exact quarter's investment purchases. Those two separate facilities have independently verified *reported June 30 debt balances* of **2,837 and 1,101**, which may already overlap with the financing statement's company-wide debt issuance/repaid flows.

**Nebius, Q2 2026 financing cash:** +2,846.7 treasury share sales, −35.6 treasury share sale costs, +53.8 option exercises and **0** new convertible-note issuance in the separately itemized quarterly cash financing components = **+2,864.9**. An equity cash receipt is not a bank loan. The subsequently disclosed **$3.5bn** October 2026 Nebius bridge contractual capacity cannot be inserted into **Q2** funding, and does not certify a current loan draw.

## Chronological earlier warning, not ex-post causal proof

| Calendar quarter (gross purchases minus OCF) | CoreWeave | Nebius | Original SEC+14 availability |
|---|---:|---:|---|
| Q1 2026 | **4,711.0** | **214.9** | CoreWeave **2026-05-22**, Nebius **2026-05-27** |
| Q2 2026 | **5,743.0** | **3,411.3** | Both reconciled with original SEC cross-checks by **2026-08-26** |
| Deterioration Q2 minus Q1 | **+1,032.0** | **+3,196.4** | Only source-observable after **2026-08-26** |

Cash financing was available to these issuers during Q2 even as OCF covered less than gross cash purchases. **This is not evidence that lender funding had already dried up.** A valid test of actual tightening would need the *same* borrower/instrument priced at two dated terms, covenant compliance and actual available/denied loans, not merely comparing CoreWeave's different DDTL 4.0 vs DDTL 5.0 interest spreads (+225 vs +450 basis points over their contractual benchmark).

For the same reason, this V30 research does **not** assign a causal arrow from hyperscaler cash gap to SPV credit spread, a current bank funding exposure, credit run probability, or 2000/2008 numerical similarity.

## Original source chain

- [CoreWeave Q1 2026 SEC 10-Q](https://www.sec.gov/Archives/edgar/data/1769628/000176962826000222/crwv-20260331.htm) (filed May 8; eligible May 22).
- [CoreWeave Q2 2026 earnings SEC 8-K exhibit](https://www.sec.gov/Archives/edgar/data/1769628/000176962826000362/coreweave2q26earningspress.htm) (filed Aug 11; eligible Aug 25).
- [CoreWeave June 30 2026 SEC 10-Q](https://www.sec.gov/Archives/edgar/data/1769628/000176962826000366/crwv-20260630.htm) (filed Aug 12; eligible Aug 26, **after** the first release).
- [Nebius Q1 SEC 6-K](https://www.sec.gov/Archives/edgar/data/1513845/000110465926059872/tm2614392d1_ex99-1.htm) (filed May 13; eligible May 27).
- [Nebius Q2 SEC 6-K earnings exhibit](https://www.sec.gov/Archives/edgar/data/1513845/000110465926094568/tm2622968d1_ex99-1.htm) and [interim financials](https://www.sec.gov/Archives/edgar/data/1513845/000110465926094844/nbis-20260812xex99d2.htm) (filed Aug 12; eligible Aug 26).

Archived source-byte hashes and source URLs already exist in [original SEC registry](../aics_data/source_registry/neocloud_cash_h1_sec.json), while V30 itself reads previously audited research ledgers, not re-downloads or independent first-2026 publication receipts. Never reinterpret those hashes as evidence of historical feed-delivery PIT.

## V30 implementation and model relevance

- [Accounting and funding identity engine](../scripts/aics_v30_cashflow_financing_bridge.py) preserves SEC+14 and period dimensions and rejects incorrect financing-component sums, issuer mixes, early disclosures and fabricated balance exposures.
- [Negative source tests](../tests/test_aics_v30_cashflow_financing_bridge.py) assert Q1/Q2 2026 economic values, cash stock rollforward, funding components and pre-publication embargo.
- [ModelChallenger and CreditContagionAnalyst](../scripts/aics_ten_model_improvement_agents.py) distinguish *actual financings through debt vs equity cashflow* from *unproven tightening of loan costs*. [AICS 30-role coordinator](../scripts/aics_thirty_agent_cycle.py) records the 2 complete issuer Q2 bridge mechanisms.
- [CI workflow](../.github/workflows/aics-ten-real-source-waves.yml) validates and archives the V30 report with genuine source capture artifacts.

**Production gate unchanged:** original 11 AICS weights 1050, full certified AICS **null**, current lender-by-lender dollar exposure matrix **null**, independently demonstrated matched-loan repricing **0**, untouched OOS skill **null**, and no trading output. The five open core research tasks cannot be presented as completed merely because a descriptive funding bridge now exists.

**Next high-return original evidence task:** dated changes of **the same exact secured facility's** margins, actual draw/repayment and restricted/unrestricted liquidity by quarter; then lender-level exposures, pledge collateral, and lender balance-sheet funding channels. This is the distinction between merely capital-intensive growth and a transferable 2008-style credit funding shock.
