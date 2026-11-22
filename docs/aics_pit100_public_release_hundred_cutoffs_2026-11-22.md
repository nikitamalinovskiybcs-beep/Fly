# AICS PIT100 · 100 historical as-of audits / 100 scoped roles

**Date:** 2026-11-22. **Verification:** [GitHub Actions run 45004542167](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/45004542167), **success**. Source artifact **14747067635** preserves the original collector responses alongside individual PIT audit JSON `aics_100_pit_audit_runs_public_release_policy.json`. The daily automated workflow continues at 23:15 UTC.

## Changed active PIT research policy: no artificial +14-day wait

New dedicated PIT replay uses:

- SEC first **public filing calendar date** as the earliest *calendar-day research eligibility proxy*, not `filed_at + 14`; the existing original +14 fields are treated as historical metadata from the *previous* research policy, not proof of current PIT eligibility.
- For a **market-close** backtest, a same-day SEC filing with no original, independently verified **acceptance/public availability time** is **not** treated as available before the 16:00 New York close. In the date-only fallback it becomes eligible only strictly **after** the filing date. This uses a conservative date-only guard rather than asserting the next day was an actual exchange trading session. An independently verified exact SEC acceptance/dissemination timestamp and session calendar is required to permit same-day trading features.
- Today’s independently SHA-verified SEC source bytes do **not** prove the historical first-data-feed receipt or first market availability. No retrospective price corporate-action restatements, revised macro vintages or post-facto constituent definitions are certified.
- Non-SEC Fed/G.17/NYFed/ALFRED release-date **proxies** continue to be explicitly tagged not independently historical release-vintage certified; no unconditional backfill of revised data.

Official SEC documentation distinguishes **acceptance time** from **filing date**: see [SEC EDGAR data access](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data), [SEC filing status](https://www.sec.gov/submit-filings/filer-support-resources/how-do-i-guides/determine-status-my-filing) and [SEC Webmaster FAQ (acceptance time)](https://www.sec.gov/about/webmaster-frequently-asked-questions).

## Actual implementation and work performed

The new audited [PIT100 engine](../scripts/aics_pit_100_real_cutoff_agents.py) has exactly **100 unique role identifiers**: **30 retained AICS base roles** (10 publisher-source collectors, 10 historical analysts, 10 existing model researchers) plus **70 newly created PIT specialists**. Exactly **100 unique as-of date audit passes** are executed, each with an individually serialized report and different historical cutoff. These are 100 deterministic audit tasks, **not** trained neural agents or 100 unique data publisher HTTP requests.

All 100 cutoffs are drawn by deterministic stratification from real recorded events in existing original SEC, BDC, macro/repo, financing, contract, issuer cashflow and market/calendar research ledgers. No date is invented and no synthetic market price or future value is filled in. The 100 checks are divided into ten evidence-specialist families, ten executions per family:

1. SEC original filing calendar date and absence of source acceptance-time proof
2. Private Credit original BDC quarterly publication chronology
3. Market-close source timing, with guarded same-day event
4. Calendar-day close source timing
5. 28 dated direct issuer cashflow quarters from the same four hyperscalers
6. CoreWeave and Nebius original SEC financing-cashflow statement identity
7. NY Fed SOFR / IORB repo publication date and missing historical ALFRED vintages
8. Original AI equity price history archive and missing PIT constituent/corporate-action vintages
9. Original signed credit contracts, lender name vs funded amount
10. Frozen index integrity, missing predictive certification and historical crisis-onset gates

Each run records `AICS_role_id`, actual `historical_cutoff`, `date_origin_categories`, `eligible_event_counts`, `domain_specific_source_derived_audit`, and `historical_provider_receipt_independently_verified:false`. The engine checks role count = 100, original role count = 30, new role count = 70, unique cutoff count = 100, and the source-specific economics. The [five negative tests](../tests/test_aics_pit_100_real_cutoff_agents.py) prevent false promotion and corrupted source timestamps.

The previously created [V40–V49 ten agent run](../scripts/aics_v40_v49_ten_pit_forensics_agents.py) still exists as **LEGACY +14 policy sensitivity analysis**. Its 27 SEC differences, 7 BDC differences and +14-only quarantines must **not** be described as actual lookahead violations under the new active research publication-date policy. This dedicated PIT100 path supersedes that policy for its own source-date replay. Other historical descriptive AICS research modules remain legacy snapshots until individually re-evaluated; their scores are NOT newly certified by this switch.

## GitHub Actions end-to-end proof

[Successful run 45004542167](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/45004542167) passed:

- Original 30-role live source collection + model research with genuine publisher captures (**36** actual HTTP attempts / **36** successful raw archives; not 36 unique).
- PIT100 original-source-date policy and five fail-closed independent tests.
- The 100 actual per-role replay executions with **100 unique cutoffs**.
- Final CI gates for fixed model weights and all **100** audit rows.
- Ninety-day retained artifact including the complete `aics_100_pit_audit_runs_public_release_policy.json` and SHA256 of all source files and the 30-role report.

The workflow is [aics-ten-real-source-waves.yml](../.github/workflows/aics-ten-real-source-waves.yml). The dedicated PIT100 batch is executed after completing the original 30-role live cycle; it does **not** issue 100 redundant EDGAR/FRED web downloads.

## Model completeness remains unchanged

**22/66 independently signed project milestones** (≈33/100 project completion, not forecasting accuracy). **0/11 independently certified PIT nodes.** Complete 11-node AICS, AICS/S&P 500 spread, independent 24-month OOS and 2000/2008 quantified crisis risk remain **null**. Frozen model weights sum **1050**, unchanged. No automated promotion or trades.

**Next highest-value improvement:** obtain and retain *actual* SEC EDGAR acceptance timestamps from primary filing submission headers, actual original publisher and data-feed publication times, and ALFRED date-vintages; re-evaluate older legacy +14 research using the public release clock before independently adjudicating any historical early-warning claim. The PIT100 project is a meaningful source-chronology and audit-capacity expansion, not a certified investment risk model.
