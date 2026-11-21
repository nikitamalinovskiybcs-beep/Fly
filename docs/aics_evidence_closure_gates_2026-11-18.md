# AICS evidence closure gates — 2026-11-18

Status: **NOT CERTIFIED**. Index and predictive skill are N/A.

## Mandatory gates
1. **Source execution**: each collector must have a successful GitHub Actions run, raw payload SHA256, retrieval timestamp, source URI and a per-source error manifest. A configured workflow is not evidence of execution.
2. **PIT**: SEC available_at = filed_at + 14 calendar days; ALFRED vintage at each evaluation date; EIA release date supported by official publication evidence; historical prices must not use retroactively adjusted values without PIT corporate-action reconstruction.
3. **Metric semantics**: no mixing units; each metric has definition, stress direction, unit, version, source, publication timing, transformations and issuer coverage. Proxy observations never certify a node automatically.
4. **11-node certification**: each node requires independent provenance review, calibration and a versioned stress score. Missing any node => certified AICS N/A. User-supplied boolean flags are insufficient.
5. **OOS**: at least 24 genuinely untouched months, fixed training cutoff, frozen transforms and label definition, comparison against legitimate baseline models. No probability calibration on OOS.
6. **Investment controls**: research only; no automated trades.

## Node-specific gaps and next evidence
| Node | Next evidence to acquire | Blocking issue |
|---|---|---|
| Private Credit | BDC non-accrual and PIK tables from original SEC filings | HY OAS is not direct private credit |
| Insurers | NAIC RBC and issuer Level 3 asset disclosures | no common XBRL coverage |
| UST 30Y | DGS30 historical ALFRED snapshots and rolling yield volatility | yield level alone not stress |
| Neoclouds | issuer filings, debt maturities, utilization and contracted capacity | limited issuer history |
| AI Equities | timestamped unadjusted prices and corporate actions | current split-adjusted history is not historical PIT |
| Hyperscalers | SEC capex and operating cash flow with compatible fiscal periods | raw capex is not stress |
| SPV | guarantees and commitments from SEC notes | leases are not automatically SPV liabilities |
| Repo | SOFR-IORB, dispersion and volume with vintage availability | SOFR level alone is not stress |
| Power/Data Centers | EIA actual release calendar and regional power constraints | industrial US price not DC-specific |
| Semiconductors Supply | inventory, COGS, lead-time evidence | absolute inventory not stress |
| AI Demand | AI-specific orders/RPO from issuer statements with date and definition | aggregate RPO not AI-specific |

## Prioritization
**P0**: verify existing workflows, secrets presence and actual run artifacts; implement fail-closed date and source validation.
**P1**: extract issuer-specific notes for Insurers/SPV/Neoclouds; document evidence gaps without imputing.
**P2**: version metric definitions, certify each node independently and run untouched walk-forward OOS.

## Gemini v1.1 integration restrictions
- Reuse its SEC period filtering, per-metric normalization and release-date fail-closed approach only after unit tests.
- Do not copy its compute_aics_at_date promotion rule: 12 samples per node do not constitute independent verification.
- Do not label its lagged binary-event baseline AR(1), and do not label an arbitrary sigmoid a calibrated probability.
- Keep the existing reproducibility gate authoritative.
