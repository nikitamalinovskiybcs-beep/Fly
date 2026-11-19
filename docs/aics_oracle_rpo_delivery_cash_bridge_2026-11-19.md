# AICS research: Oracle RPO delivery ladder versus data-center commitments and cash

**Frozen information cutoff: 2026-11-19. Research facts, NOT certified AICS.**
Nodes touched: **AI Demand** and **Power/Data Centers**; related Oracle financing is not an invented SPV look-through exposure.

## Source / exact eligibility

[Oracle original 2026-08-31 10-Q](https://www.sec.gov/Archives/edgar/data/1341439/000119312526389274/orcl-20260831.htm), accession `0001193125-26-389274`, filed **2026-09-11**, AICS permitted from **2026-09-25** (SEC +14 calendar days). Original SEC full submission SHA256 previously pinned in the project registry: `78399754d5b5f49d693606da359985811d1f53ae349b9850383886261e92d559` (10,806,151 bytes). The facts below are read from the published primary 10-Q, not derived from a third-party AI spending forecast. New lines are **manually source-reviewed**, not independently re-extracted from original bytes. Machine-readable review: [Oracle contract and cash research](../aics_data/research/oracle_rpo_lease_commitments_cash_bridge_2026-11-19.json).

## Expected contractual revenue is back-loaded (Note 1)

Oracle reported **$664bn** remaining performance obligations (RPO) as of August 31, 2026, vs **$455bn** on the August 31, 2025 comparative in the *same later filing* (+$209bn, +45.93%). Management expects the RPO to be recognized on the following approximate schedule:

| Recognition interval | Approximate share | Implied approximate value |
|---|---:|---:|
| Next 12 months | 13% | $86.32bn |
| Months 13–36 | 37% | $245.68bn |
| Months 37–60 | 34% | $225.76bn |
| After month 60 | 16% | $106.24bn |
| **Total** | **100%** | **$664bn** |

Approximately **87% ($577.68bn)** is not expected to be recognized in the next twelve months. This is not a default indicator: timing is an estimate, RPO is **not received cash**, does not prove customer identity/AI-only revenue, and the comparison with 2025 is not a separately archived 2025 PIT vintage.

## Delivery commitments (Note 6): separate liabilities from future contracts

- **$288bn** in *additional lease commitments*, substantially for data centers, expected to begin approximately FY2027 Q2–FY2029, with 15–19-year contract terms. Oracle explicitly says they were **not** reflected in August 31, 2026 balance-sheet lease liabilities or the then-current maturities schedule.
- On-balance-sheet discounted lease liabilities were **$34.621bn operating** plus **$9.185bn finance** = **$43.806bn**; the separate undiscounted schedule for those liabilities was $48.050bn + $15.195bn = $63.245bn. Comparing discounted present value with future undiscounted commitments as if the amounts were the same instrument would be misleading.
- Separately disclosed unconditional purchases and certain other commitments, mainly cloud-component and data-center power/supply contracts, totaled **$34.150bn**, reconciled as $5.449bn + $6.176bn + $3.863bn + $4.318bn + $6.768bn + $0.954bn + $6.622bn across the reported fiscal buckets.

Do **not** sum RPO + $288bn + $34.150bn into "AI debt" or claim all contracts were AI-specific, currently payable or SPV-guaranteed. Distinct legal classification, possible overlap, counterparty risks, and maturity horizons remain to be independently analyzed.

## Actual FY2027 Q1 cash flow (three months ended August 31, 2026)

| SEC cash-flow item | USD millions |
|---|---:|
| Net cash provided by operations (CFO) | 23,103 |
| Within CFO: customer prepayments with significant financing component | 11,363 |
| Cash capital expenditures (outflow) | (28,499) |
| **Reported free cash flow = CFO − cash capex** | **(5,396)** |
| Equity at-the-market proceeds, financing section | 19,909 |

The specific financing-related customer-prepayment line equals **49.18% of CFO**. A purely mechanical subtraction gives CFO less that cash-flow item of $11.740bn and CFO-less-that-item minus capex of **−$16.759bn**. This is **not adjusted GAAP CFO, recurring operating cash or a company-defined FCF metric**: customer prepayments have contractual liabilities and may recur. The ATM proceeds are equity financing, **not revenue or customer prepayments**; $6.247bn unpaid capex is a noncash note and is **not added to cash capex**.

## Committee interpretation and certification boundary

A strong multi-year *company-wide* backlog coexists with immediate asset-build spending and future lease/purchase obligations. The cash-flow evidence specifically shows how large customer advance financing and external equity proceeds contributed to the quarter's funding. This motivates monitoring **execution timing, cash conversion, credit concentration and lease recognition**, but does not justify a statistically calibrated stress number, prediction or exit-to-cash verdict.

**11 immutable nodes, weights total 1050. 22/66 technical milestones, independently attested historical PIT 0/11, untouched 24m OOS 0/11, certified 0/11, `index_aics=null`.** SEC original bytes were retrospectively archived, so independently attested contemporaneous release delivery is missing. ALFRED macro vintage and no-look-ahead rules are unchanged.
