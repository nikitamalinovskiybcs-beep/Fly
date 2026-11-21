# AICS — reconciliation of 37 companies and three unverified financing graphs

**As of 2026-11-18. Research-only evidence; no 0–100 node score or investment action.**

Source of truth: `aics_data/research/aics_extended_company_universe_omi_telegram_2026-11-18.json`.
Reproduce/validate with:

```sh
python -m unittest discover -s tests -p test_aics_extended_company_universe.py -v
python -m unittest discover -s tests -p test_aics_reconcile_company_universe.py -v
python -m scripts.aics_reconcile_company_universe --out aics_data/source_evidence/omi_telegram_company_reconciliation.json
```

## Provenance before scoring

- 37 distinct research candidates: 26 named in the **secondary** OMI 88-page report and 11 introduced **only** by the 11 Telegram screenshots.
- Three distinct **reported** project groups: Abilene Texas/Stargate, Meta Louisiana data-center financing, and NVIDIA-related contracts reported outside the OMI paper. Neither OMI descriptions nor Telegram screenshots establish executed contract terms.
- 0 of these three groups have independently verified legal-entity CIKs, borrower/guarantor recourse or drawn exposures in this registry. No amount is aggregated and no amount is used as node stress.
- The original user-provided OMI PDF is pinned by SHA-256 `466b8a875752c85e23a41d5e33ad985c44f437ddc5cf801e132310c4e28bff60`. The report remains secondary research, not a substitute for SEC/contract originals.
- The 11 official AICS nodes and weights sum to **1050**, unchanged. The technical ledger currently shows **22/66 = 33.3%** milestones; **0/11 independent certification**; aggregate AICS **N/A**.

## Candidate mention counts by existing AICS node

These are overlapping mentions of companies in the research registry, **not** source completeness, economic exposures, stress scores, nor estimates of risk. A company may appear in multiple node columns, and a project may have many counterparties.

| Node | Weight | Candidate company mentions |
|---|---:|---:|
| Private Credit | 150 | 4 |
| Insurers | 125 | 5 |
| UST 30Y | 125 | 0 |
| Neoclouds | 100 | 9 |
| AI Equities | 100 | 8 |
| Hyperscalers | 100 | 6 |
| SPV | 100 | 13 |
| Repo | 100 | 1 |
| Power/Data Centers | 50 | 6 |
| Semiconductors Supply | 50 | 8 |
| AI Demand | 50 | 11 |

Macro nodes UST 30Y and Repo depend on historical market series rather than corporate mentions. Zero mentions is **not** a market-data availability statement. Repo's single company mention does **not** prove repo-market stress.

## Source-to-score gates for three project groups

| Reported project graph | What remains missing before an economic exposure metric |
|---|---|
| Abilene Texas/Stargate | Borrower/debtor legal identities; original project loan and lease contracts; security and parent recourse; *actual drawn* funding, dates and counterparties |
| Meta Louisiana data-center financing | Original SPV documents; lease vs guarantee distinction; drawn loans and risk transfer; insurance/fund holdings without double counting |
| NVIDIA-related Telegram contract claims | Date-specific SEC original and exact issuer/supplier contract originals; distinguish investment carrying value, future equity commitments, VIE max loss, capacity commitments and guarantees; independently verify drawn balances |

No liabilities, commitments, guarantees, carrying values and market equities may be summed as though they were additive debt. Publication date and availability date must be preserved. SEC requires `available_at = filed_at + 14 calendar days`; revised FRED observations require ALFRED vintage evidence.

## Machine-verifiable guard

`scripts/aics_reconcile_company_universe.py` stops with a nonzero exit if a Telegram-only entity claims OMI physical pages, an unknown/duplicated company enters the registry, a candidate receives a stress score or non-null financial exposure, a reported relationship is called a primary or verified contract, model weights change, or the progress/status file claims certification.

Its JSON output leaves `node_stress_scores`, `index_aics` and `aggregated_exposure_usd` as `null`, and `milestones_added` as `0`. This closes a validation gap only. The next genuine milestone requires primary historical PIT, mapping review and untouched 24-month OOS; no synthetic observations, backfill or look-ahead are permitted.
