# AICS V21 — 20 agents. First end-to-end CI research cycle

**As of:** 2026-11-22 · **Actual verified run:** [GitHub Actions #44953881240](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44953881240), success. The saved job contains **22 passing tests** (11 source-collection tests and 11 AICS analysis-agent tests), followed by a successful live-current capture and analysis. Source bytes and reports are available in [the 90-day artifact (ID 14727245362)](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44953881240/artifacts/14727245362). It is a GitHub artifact, not a permanent data warehouse.

## Separate responsibilities, without Phoenix-model mixing

**10 existing collectors** in [scripts/aics_ten_node_agents.py](../scripts/aics_ten_node_agents.py): Private Credit, Insurers, UST 30Y, Neoclouds, Hyperscalers, SPV, Repo, Power/Data Centers, Semiconductors Supply, AI Demand. AI Equities still has its own separate prospectively collected market-price/corporate-actions source flow.

**10 new model-operations research agents** in [scripts/aics_ten_analysis_agents.py](../scripts/aics_ten_analysis_agents.py):

| # | Class | Actual AICS duty |
|---|---|---|
| 1 | SourceLineageAgent | Verify 24 consecutive months, source-ledger schema, 11 immutable weights sum 1050 and 24 Private Credit original issuer-quarter receipts |
| 2 | PITChronologyAgent | Block forward-dated research events, retain +1 day SEC proxy versus market-close cutoff, mark historical receipt non-certified |
| 3 | CoverageAgent | Compute separate 24-month weighted research-source availability, calendar and last-weekday market |
| 4 | FreshnessAgent | Recalculate 60/90/120-day source age, exclude stale entries rather than use fictitious scores |
| 5 | ScoreAuditAgent | Reconcile original 0–100 scores and weighted partial sums using Decimal and 2-place HALF_UP |
| 6 | RiskAttributionAgent | Report named observed contributors to the latest **partial** research sum; never attribute missing scores |
| 7 | StressSensitivityAgent | Produce pure arithmetic [known sum, known sum + missing weights] and explicitly hypothetical ±10-point measured-node sensitivities |
| 8 | SP500AlignmentAgent | Align 24 actual S&P 500 closes and 23 observed monthly returns; refuse to fabricate an AICS–S&P spread |
| 9 | OnlineAnomalyAgent | Reuse causal median/MAD learner over 64 pre-existing **ex-post research** events, no supervised return model |
| 10 | GovernanceDirectorAgent | Combine the 9 agent checks with the **actual current 10-collector manifest**, explicitly block uncertified production/trading |

## Actual first end-to-end run

| Test or result | Real observed outcome |
|---|---|
| Collectors | 10/10 ran |
| Original source endpoints | 20 deduplicated requests |
| Valid original bytes written and SHA-checked | **19/20** |
| SEC submission JSON filing metadata | 15/15 downloaded; **not issuer financial statement parsing** |
| ALFRED DGS30, ALFRED IORB, NY Fed SOFR and Fed G.17 | 4/4 captured; not original historical delivery PIT |
| EIA-930 regional hourly demand | **Blocked**, `EIA_API_KEY` absent; source not replaced with a zero |
| New specialized analysis agents | **10/10 passed** |
| Total new module unit tests | **22/22 passed** |
| Retrospective ML source-score events | **64**, 0 attention flags; NOT a proof of model skill |
| Independent certified nodes | **0/11** (unchanged) |
| Full 24-month AICS | **0/24** |
| Real AICS / S&P 500 normalized spread | **0/24** |
| Production model changes / live trades | **none** |

## Findings produced by the 10 actual AICS analysis agents

| Measure | Calendar month-end | Last-weekday price-close proxy |
|---|---:|---:|
| Weighted 24-month **research source observability**, not model correctness | **50.89%** | **50.00%** |
| Weight-months | 12,825 / 25,200 | 12,600 / 25,200 |
| Source recency capped at **90 days** | **47.72%** | **46.83%** |
| Oct 2026 observed candidate nodes | **10/11** | **8/11** |
| Oct 2026 observed partial points (not full AICS) | **466.26** | **268.39** |
| Oct 2026 formal mathematical unknown-node bounds, **NOT measured points** | **466.26–566.26** | **268.39–593.39** |

The October calendar/market difference comes from different information available by cutoff (not a fall in market risk); October 31, 2026 was a Saturday. The *last-weekday* procedure remains a proxy, not an independently certified NYSE holiday/session calendar. S&P 500 month-end closing price 6032.38 (Nov 2024) → 7580.08 (Oct 2026), historical gain +25.66%; there is still **no real spread of full AICS vs. S&P**.

**Important guard:** unmultiplied AICS partial sums and arithmetic bounds must not be interpreted using the legacy multiplier-based 450–500 decision thresholds. A 24-month historical analytical report is not a 24-month untouched prospective OOS run, and the ex-post Private Credit scoring rule cannot be considered pre-registered.

## Operating cycle, code and next stage

The existing [AICS 20-agent workflow](../.github/workflows/aics-ten-source-agents-ml.yml) is now a **single chain**: source collector → SHA-verified live raw archive → causal anomaly learner → 10 AICS analysis agents → fail-closed tests → GitHub Actions summary → **90-day artifact**. Scheduled **weekdays at 22:45 UTC** on the repository default branch, plus code push / workflow_dispatch. GitHub cron can be delayed or paused; do not represent a scheduled future run as a completed one.

**Next technical priority:** Parse *actual original SEC 10-K/10-Q/8-K numeric evidence* for each issuer and add new **time-eligible quantitative node observations** to the journal. A current SEC `submissions.json` index is **filing discovery metadata only**, not the AI-specific cash-flow/credit metrics. Source-to-score mapping, original release timestamps, vintage-safe learning labels, independent 24-month OOS and AI Equities corporate actions remain gaps. Optional `EIA_API_KEY` unlocks EIA-930 data, still not direct AI data-center power consumption.

**Safety statement:** nothing has been auto-trained to predict market returns, reweighted in the 1050 scoring system, presented as an independently certified PIT backtest, or executed as a trade.
