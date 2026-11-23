# AICS V28 — source-dated legal credit relationship graph, **not** a contagion model

**Research snapshot:** 2026-11-22. **Scope:** 30-agent AICS research pipeline, fixed 11-node weighted index (1050). No trading or production reweighting. The purpose is to test whether pre-crisis AI infrastructure cashflow stress has identifiable lender/guarantor propagation channels, without turning contract ceilings, rents, past cash draws or consolidated totals into invented current lender losses.

## 9 legally typed, original-source-gated relationships

| Source-gated evidence | Source available under SEC +14 | Relationship / economic type | Dated amount | Current named lender exposure? |
|---|---|---|---:|---|
| CoreWeave DDTL 4.0, Compute Acquisition Co. VIII LLC | 2026-08-26 | Debt reported 2026-06-30, lender pool not individually identified | **$2.837bn** | No |
| CoreWeave DDTL 5.0, Financing DDTL V LLC | 2026-08-26 | Separate debt reported 2026-06-30, unconditional parent guarantee; precise parent loss unknown | **$1.101bn** | No |
| Nscale Ward County Borrower SPV LLC | 2026-10-02 | Fixed + floating contractual credit ceiling; actual draws unknown | **$1.850bn ceiling** | No |
| Nscale NC Borrower SPV LLC | 2026-10-02 | Fixed + floating contractual credit ceiling; actual draws unknown | **$1.200bn ceiling** | No |
| Dell Financial Services → Nscale Ward/NC borrower *group* | 2026-10-02 | Aggregate initial-term rent across 40 schedules, includes financing charges. Not debt principal, not attributable separately to each SPV | **~$2.540bn rent** | No |
| Macquarie Bank → Nscale Global Holdings Limited | 2026-10-02 | Two historical usage events dated 2025-08-01 and 2026-01-30; *not* a current outstanding balance | **$70.1m + $34.9m** | No |
| Kvandal South DC senior loan → Nscale Norway DC DA | 2026-10-02 | Original SEC-disclosed **August 2026 draw event**, lender pool not named; year-end balance unknown | **$88.1m draw** | No |
| Kvandal South DC VAT revolver → Nscale Norway DC DA | 2026-10-02 | Separate **August 2026 draw event**, lender pool not named; closing balance unknown | **$19.1m draw** | No |
| Nebius Group N.V. / Nebius Inc. / Nebius B.V. | 2026-11-05 | Three named co-borrowers on **one** $3.5bn secured-term-loan capacity, not 3× $3.5bn, actual drawn amount unknown | **$3.500bn ceiling** | No |

**Two named Nscale affiliate guarantor relationships**, both with **unquantified dollar enforceability**: Nscale Ward County, LLC → Nscale Ward County Borrower SPV, LLC, and Nscale Services US Inc. → Nscale NC Borrower SPV, LLC. The separate CoreWeave DDTL 4.0 and 5.0 recourse descriptions remain qualified; effective parent loss not estimated.

The two **named financing providers** in this network are **Dell Financial Services L.L.C.** as a disclosed financing rental counterparty, and **Macquarie Bank Limited** as lender for the historical Nscale usage events. Naming a finance provider is **not** proving current exposure. CoreWeave facility lenders, Kvandal lending syndicate and Nebius financing counterparties are still unverified.

## Chronology gates

- Before **2026-08-26**, none of the two CoreWeave June debt balances are eligible. From that date: **2** typed relationships.
- On **2026-10-02**, the Nscale Ward/NC limits, DFS rent, Macquarie historical utilizations, Kvandal two historical draws and two guarantor links first become eligible. Total typed relationships: **8**.
- From **2026-11-05**, the Nebius $3.5bn bridge capacity is date-eligible as the ninth typed relationship. Still no current drawn amount or independent historical provider delivery attestation.

All primary ledger amounts are drawn from previously source-verified original SEC records and remain date-labelled. The [Ward original SEC S-1 EX-10.23](https://www.sec.gov/Archives/edgar/data/2110365/000119312526395475/ck0002110365-ex10_23.htm), [NC original SEC S-1 EX-10.24](https://www.sec.gov/Archives/edgar/data/2110365/000119312526395475/ck0002110365-ex10_24.htm), [Nscale S-1 narrative](https://www.sec.gov/Archives/edgar/data/2110365/000119312526395475/ck0002110365-20260918.htm), [CoreWeave 10-Q](https://www.sec.gov/Archives/edgar/data/1769628/000176962826000366/crwv-20260630.htm), and [Nebius 6-K](https://www.sec.gov/Archives/edgar/data/1513845/000110465926117978/tm2628078d1_6k.htm) are the original public document references. **Nebius 6-K was manually transcribed and lacks independent raw-byte hash**, so do not misstate it as independently hashed.

## Code and governance

- [V28 topology builder](../scripts/aics_v28_credit_relationship_topology.py) consumes the existing [V27 SPV bridge](../scripts/aics_spv_funding_transmission_bridge.py), [Nscale NC source audit](../scripts/aics_spv_nscale_contract_gate.py), Ward raw rehash ledger, Nscale S-1 historical original and Nebius source ledger.
- [Negative tests](../tests/test_aics_v28_credit_relationship_topology.py) assert the 9 distinct economic-typed relationships, 2 named financing providers, 2 guarantors, and zero **current named lender dollar exposure** edges; prevent backdating before SEC+14 and prevent treating historical Kvandal/ Macquarie draws or Nebius capacity as current debt.
- [ModelChallenger and CreditContagionAnalyst](../scripts/aics_ten_model_improvement_agents.py) consume the topology. The [30-role cycle coordinator](../scripts/aics_thirty_agent_cycle.py) keeps `SPV_CREDIT_RECOURSE_NETWORK` **open**, since relationship topology is not the required lender-level current exposure matrix.
- [GitHub Actions](../.github/workflows/aics-ten-real-source-waves.yml) runs the V28 negative gates, creates a dated research JSON inside the archived 90-day Actions artifacts, and verifies the 30-role summary without automatically changing AICS weights or trading.

## Current conclusion

**We now have a dated legal topology, not a 2008-style contagion model.** It identifies actual legal borrowers, affiliate guarantees and named finance providers, while refusing to sum unlike instruments. The number of **verified named current lender-to-borrower dollar exposure edges remains zero**; independent 24-month OOS is still zero; 2000/2008 numeric similarity, crash probability and certified 11-node AICS remain **null**. Next material step: source-verifiable **current** lender-by-borrower loan balances, facility collateral, parent recourse cap, maturity/refinancing and repo/insurer spillover paths.
