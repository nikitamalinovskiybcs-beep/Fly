# AICS: Brace for Impact (OMI/AFREF, October 2026) — analytical source audit

**Date of research intake: 2026-11-18. Type: SECONDARY RESEARCH / CONTAGION HYPOTHESES; NOT MARKET OBSERVATIONS.**

- Authors: Matthew U. Scherer (Open Markets Institute) and Maya Jenkins (Americans for Financial Reform Education Fund)
- Publisher report date: **16 October 2026**; research text and figure labels chiefly refer to earlier periods
- User's PDF: https://www.openmarketsinstitute.org/s/Brace-for-Impact-Scherer-Jenkins-OMI-October2026-WEB-1.pdf
- Alternate publisher-hosted full text: https://ourfinancialsecurity.org/wp-content/uploads/2026/10/Brace-for-Impact-Scherer-Jenkins-OMI-October2026-WEB.pdf
- Source PDF byte archive: **NOT YET CERTIFIED** (no original-source SHA-256 verified at initial intake)
- Machine-readable registry: `aics_data/research/omi_brace_for_impact_oct2026_hypotheses.json`

## Conclusion relevant to AICS

The paper presents an **AI-linked balance-sheet and funding-contagion narrative**: potentially weak third-party AI demand -> cloud tenant pressure -> SPV/project finance/leases -> private credit and life insurers -> bank and funding-system spillovers -> equity liquidation and stranded infrastructure. This is a **scenario graph**, not a recorded cascade or a calibrated forecast. **The paper itself disclaims that a crisis is inevitable or predicts a particular sequence** (executive summary, PDF p. 6).

The model should retain its **original 11 nodes and all 1,050 weight units**. This research adds candidate indicators and source-verification tasks, **not** 0–100 scores or additional model weights.

## Explicit linkage to the 11 fixed nodes

| AICS node | Weight | Concrete research candidate prompted by report | What must independently prove it |
|---|---:|---|---|
| Private Credit | 150 | PIK interest, BDC non-accrual, bank-to-NBFI funding | BDC original SEC filings and Federal Reserve bank NBFI exposures |
| Insurers | 125 | Illiquid/private-bond concentration; captive reinsurance and ratings | NAIC original statutory filings, insurer original SEC note disclosures |
| UST 30Y | 125 | Long-rate duration / refinancing-cost transmission | Treasury/ALFRED as-of yield vintage; **indirect** report relevance |
| Neoclouds | 100 | Real debt-servicing burden versus collected cash, refinancing cliff | SEC original 10-Q/10-K, debt agreement maturity notes |
| AI Equities | 100 | Concentration, valuations, margin debt, point-in-time drawdown | Original dated index constituents and FINRA margin debt |
| Hyperscalers | 100 | Noncancelable commitments, capex vs attributable AI revenue | Original SEC lease/purchase commitment notes and depreciation policies |
| SPV | 100 | Actual borrower, guarantees, leaseback and recourse waterfalls | Executed debt agreements, loan prospectuses and affiliate maps |
| Repo | 100 | NBFI funding contagion, collateral and liquidity conditions | NY Fed repo-market primary spreads, haircuts and funding data; **indirect** |
| Power/Data Centers | 50 | Energization delays, megawatts committed vs active | Original grid-operator queue/EIA releases + issuer physical MW records |
| Semiconductors Supply | 50 | GPU useful life versus accounting depreciation, procurement | Manufacturer capacity and OEM disclosures, not merely NVIDIA revenue |
| AI Demand | 50 | Third-party paying customers; circular financing; backlog conversion | First-party contract economics and independent transaction datasets |

**No node crosses the independent PIT, audited score, OOS or independent certification gates solely because of this report.**

## Quantitative statements — quarantine until original-data recheck

The figures below are **reported in the policy paper**, not AICS-calibrated measurements:

| Reported value | Section/page in PDF | Primary-source verification needed |
|---|---|---|
| **$3.1 trillion** off-balance-sheet portion across nine named tech firms | Executive summary p. 9, Figure ES-9 | Separate on/off-balance categories, leases, unfunded commitments, issuer universe and as-of date from company filings and WSJ methodology |
| **$3.7 trillion** aggregate on- and off-balance commitments/debt across same nine | Executive summary p. 9, Figure ES-9 | Same; do not label all future commitments as currently funded debt |
| **40%** top 10 companies' S&P 500 capitalization, Sep. 2026 | Executive summary p. 7; Figure 3 p. 16 | S&P index holdings / weights at September 2026 PIT |
| **$1.5 trillion** FINRA margin debt, Aug. 2026 | Executive summary p. 9, Figure ES-8 | FINRA direct monthly as-published report and available_at |
| **~20%** of life-insurer fixed-income assets private/illiquid | Part III p. 43, notes 225-228 | Original sample, issuer population, look-through definition, NAIC |
| **$2.7 trillion** bank drawn and undrawn commitments to nonbank lenders, Q1 2026 | Part III p. 42; notes 223-224 | Federal Reserve direct publications, definitions: NBFI != AI-specific |
| **$26 billion** Meta/Blue Owl/PIMCO SPV loan described | Part I p. 24, notes 76-78 | Primary borrower structure, effective date, guarantees, credit support and whether amount was funded |
| **~80%** model vendor enterprise revenues from top 1% of sampled enterprise customers | Part I p. 23, Figure 10 (Ramp) | Original Ramp sampling, denominator and report revision; do not infer industry-wide concentration |

These are **hypotheses and figures to audit**, not a financial market timeseries; they cannot be used to fill historical missing scores, compute 11-node AICS, or derive market probabilities.

## A new cross-exposure / contagion checklist (no new nodes)

1. AI Demand -> Neoclouds: utilization, paid invoices and customer contract concentration.
2. Neoclouds -> SPV -> Private Credit: signed leases, debt seniority, event of default and guarantees.
3. Private Credit -> Insurers: portfolio holdings, affiliate reinsurance/captive risks, shared exposures.
4. SPV -> Hyperscalers: lease guarantees, noncancelable obligations, consolidation rules.
5. Power/Data Centers -> SPV: power delays and collateral value.
6. AI Equities -> funding: margin debt, forced selling and liquidity. **Not equivalent to repo-market stress.**

Candidate graph edges remain **unvalidated directed hypotheses** until primary contracts and historical available-at records establish actual relationships.

## Mandatory model discipline

- Keep weights exactly `150,125,125,100,100,100,100,100,50,50,50` (= 1,050), no recalibration prompted by a persuasive report.
- `SEC.available_at = filed_at + 14 calendar days` strictly, independent of IR press release dates.
- Revisable FRED rates require historical ALFRED vintages. The report's retrospective figures cannot be inserted into prior snapshots.
- Preserve numerical units and source semantics: market-value equity exposure, unfunded lease commitments, drawn debt, and annual capex are **not directly additive**.
- Untouched 24+ month predictive OOS is absent. Zero independently certified node scores; **AICS=N/A**.
- Study is risk-oriented policy research; interpretations (e.g., likelihood of an AI crash and regulatory policy prescriptions) are attributable **to its authors**, not model-verified predictions.

## Five highest-value primary-source follow-ups

1. **SPV + Hyperscalers:** reconcile the $3.1T and $3.7T estimates line-by-line against company filing dates, entity inclusion, on/off balance and accounting treatment.
2. **Insurers:** reproduce ~20% ratio by holding type, year, sample and source.
3. **Private Credit:** obtain BDC/NAIC PIK and non-accrual details and separate AI from broad nonbank exposure.
4. **AI Demand:** confirm Ramp concentration methodology and distinguish reported backlog from realized external AI revenue.
5. **AI Equities:** retrieve official S&P top-ten holdings and FINRA margin debt, with point-in-time release records.

**Source status:** PDF full text read through publisher-hosted web indexing; direct source-file download had not succeeded at initial intake. The original binary SHA must be proven separately before marking a raw-document milestone.

**Progress effect:** **+0 certified milestones** from this secondary paper. It improves model research design, not source-level PIT readiness.
