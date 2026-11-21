# AICS Research Autopilot — daily 30 agents + V31–V34 batch
**Configured:** 2026-11-22, on repository default branch `devin/1779618014-quant-risk-framework`.

## Unattended schedule (GitHub Actions, UTC)
- **11:45 UTC daily, weekends included:** [20-agent current-source and analysis workflow](../.github/workflows/aics-ten-source-agents-ml.yml) — 10 source agents + 10 analysis agents, with online retrospective anomaly diagnostics; independent source receipt archives.
- **23:15 UTC daily, weekends included:** [30-role source-wave + model research workflow](../.github/workflows/aics-ten-real-source-waves.yml) — 10 source collectors + 10 analytical roles + 10 model-improvement researchers. 10 source-wave passes are sequential, not ten independent research forecasts. In the same CI, it audits V25–V31, performs [V32–V34 automated research rotation](../scripts/aics_v32_v34_autonomous_research_rotation.py), writes its independent result JSON, ranks the next evidence gaps and uploads ~90-day GitHub Actions archive.
- `workflow_dispatch` also allows manual execution. Push-triggered checks run when relevant AICS code is updated. GitHub Actions cron can be delayed or omitted due to platform load, and historical scheduled runs **have not yet occurred** on the new cadence; the full updated pipeline *has already passed on push*.

## What agents actually do each run
1. Generate **current UTC as-of** once at workflow start, instead of reusing hardcoded 2026-11-22. Source-specific SEC timestamp gates remain `available_at=filed_at+14 days`; reviewed historical research may not infer first-published PIT receipts.
2. Capture real official publisher payloads; archive raw sources with hash evidence. Unavailable EIA `EIA_RTO_DEMAND` is explicitly flagged rather than filled with synthetic values (GitHub secret `EIA_API_KEY` is still needed to enable its original EIA-930 API source).
3. Reconcile actual current-source SEC numeric candidates (without pretending snapshot metadata are original first-receipt financials). Analyze the frozen 11 AICS weight topology without inventing missing 24-month PIT history.
4. **V31**: maintain separate clocks for issuer IR CoreWeave Q3 interest expense ($846m) / revenue ($3,661m, descriptive **23.1%**) published **2026-11-10**, and the corresponding 2026-11-12 SEC 10-Q eligible only **2026-11-26**. Independent original SEC first-delivery PIT proof remains unattested. The retrospective October SOFR-minus-IORB is **+4 bps**, not a borrower-specific loan spread.
5. **V32**: identify the **three** pinned original contractual loan pricing observations. **Zero** same-facility, separately dated pricing *amendments* have been independently verified. Comparing CoreWeave DDTL 4.0 vs DDTL 5.0 spread is **not** evidence that the same loan repriced.
6. **V33**: reconcile **two original Q2 2026 issuer financing mechanisms**: CoreWeave $13.457bn net-of-costs debt issuance − $3.884bn repayments = $9.573bn net company-wide debt flows, and $10.071bn total net financing; Nebius $2.8467bn treasury share sale − $35.6m costs = $2.8111bn net treasury equity sale and $2.8649bn total net financing. Neither cash flow is a specific lender exposure, new DDTL draw, runway prediction or proved credit tightening.
7. **V34**: rank **genuine evidence gaps**, preserving zero confirmed current named lender-dollar exposures, no matched-loan repricing, zero independently certified 24-month OOS and no crisis probability. The *next automatic priority* is read from actual 30-role `next_experiments`, not hardcoded to an invented success.
8. Check fail-closed source dates, verified math, non-additivity and output controls; upload reproducible run artifacts.

## Verified launch and limitations
- [Successful full GitHub Actions run V31–V34](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44961549987), triggered on push, not yet the first scheduled event.
- Executed **30 agent roles**; **36** official HTTP attempts archived successfully; **260** actual SEC snapshot numeric facts screened, **2** direct-quarter candidate pairs retained without independent first-filing historical PIT certification; **5** source-ranked research priorities.
- V31 **5/5** negative tests and V32–V34 **4/4** negative tests passed. V32–V34 JSON was archived in GitHub Actions artifact ID **14730026293** (90-day retention).
- Separate 20-role workflow successfully passed on push after its daily schedule edit.
- Explicit unfilled gap: EIA-930 without `EIA_API_KEY`. Missing lender-by-lender funded exposures, independent originally delivered first-filing PIT, genuine full 24-month AICS/S&P OOS.
- **No** autonomously generated source code changes, deploy to production, weight adjustments, crisis probabilities, fully certified 11-node AICS score, or brokerage orders. A full generative coding agent or separately authenticated provider connections would need an additional reviewed automation and approval gate. This existing autopilot is a continuously scheduled **research/data-validation task**, not unbounded self-training.

## Operational link
See [AICS Actions](https://github.com/nikitamalinovskiybcs-beep/Fly/actions). Each run has logs, status and dated artifacts; do **not** infer automatic completion from the schedule alone. For source verification, inspect GitHub event type `schedule` in the future run record.
