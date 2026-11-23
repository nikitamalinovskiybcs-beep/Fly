# AICS PIT100 — проверка часов SEC, 48 винтажей ALFRED и слабый опережающий сигнал

**22 ноября 2026.** Полный цикл **[GitHub Actions 45011613323](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/45011613323) — SUCCESS**. Архив **[14750225899](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/45011613323/artifacts/14750225899)** с оригинальными исходными файлами, SHA-256 и исследовательскими JSON/CSV; retention 90 дней. GitHub workflow запускается по расписанию 23:15 UTC и при изменениях исследовательского кода.

## 1. 100 настоящих SEC SGML headers — что мы знаем

На основании **100/100 оригинальных ранее скачанных SEC primary reports** повторно скачаны **100/100 SEC accession-specific `-index-headers.html`**, проверены accession number, исходный `<ACCEPTANCE-DATETIME>` в американском Eastern time, исходные байты gzip распаковываются без потерь и имеют SHA-256. Failures: **0**.

| Source-grounded metric | Observed |
|---|---:|
| Original SEC SGML headers successful | **100/100** |
| Acceptance timestamps before 16:00 ET | **20** |
| Acceptance timestamps at/after 16:00 ET | **80** |
| Original submissions JSON clock equal SGML-converted UTC clock | **100** |
| Original submissions JSON clock equal SGML local ET clock | **0** |
| JSON clock disagrees with original header | **0** |
| Independently attested first public SEC availability | **0** |

**Scope caveat:** this is the reproducible selected 100-file accession sample across current issuer submissions (15 issuers), not an inference about all publicly traded companies or all 64 historical AICS node source events. Although all sampled JSON times matched UTC, other issuers/vintages may encode `acceptanceDateTime` inconsistently. Original SGML timestamp remains the preferred source. Original *acceptance* is not proof of first *dissemination* or first buyer feed availability; the original 2026 download does not recreate a contemporaneously saved 2024–2026 data feed.

Official SEC: [Webmaster FAQ (acceptance vs. availability)](https://www.sec.gov/about/webmaster-frequently-asked-questions), [EDGAR accessing data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data). Primary header example: `https://www.sec.gov/Archives/edgar/data/1831481/000183148126000108/0001831481-26-000108-index-headers.html`.

**Consequence:** zero artificial `filed_at + 14 days` delay in **active PIT100 research**; for a 16:00 ET market-close research slice never auto-admit a source at or after 16:00, and never auto-promote an earlier acceptance until actual public dissemination is independently supported. Older V26/V31 descriptive studies still contain legacy +14 gating and require separate migration before consistent active-model publication policy.

## 2. Original ALFRED historical realtime snapshots

**48/48** authenticated original-source day-as-of API responses downloaded and SHA-256 archived for **DGS30 (US Treasury 30Y)** and **IORB (Interest on Reserve Balances)** for each of the **24 observed historical market month-end cutoffs** 2024-11–2026-10.

Every query sets `realtime_start = realtime_end = market_cutoff_date`, rather than silently retrieving today's revised historical value. From each source response the study selects the latest valid observation strictly **before** the market close date because the actual same-day release timestamp is not independently verified.

This is real progress in recovering publication-vintage values. However it does **not** prove delivery at 16:00 ET on a particular historical trading day, nor construct/audit the UST30Y or Repo node 0–100 scoring function. No full AICS score is promoted. Official method: [FRED series observations vintage parameters](https://fred.stlouisfed.org/docs/api/fred/series_observations.html).

## 3. First fixed-cohort next-month S&P 500 falsification

Only three source-candidate nodes present in the **FIRST** historical market month (2024-11) were fixed as the cohort **without selecting surviving assets using future months**:

| Source candidate | Frozen AICS weight |
|---|---:|
| Insurers | 125 |
| Private Credit | 150 |
| Semiconductors Supply | 50 |
| **Total first-month cohort** | **325** |

Scores are deliberately described only as **ex-post original-source candidate normalized 0–100 partial research diagnostics**, NEVER the 11-node AICS; no 450/500 threshold or allocation recommended.

Compare fixed-source cohort risk at market close of month **t** with the **subsequent** S&P 500 return for month **t+1**; contemporaneous monthly return is a negative control. All **23** next-month pairs in 24 months were available.

| Exploratory observed statistic | Actual run |
|---|---:|
| Matched next-month pairs | **23** |
| Pearson corr(candidate fixed-cohort risk, **next-month** S&P 500 return) | **−0.1350** |
| Pearson corr(candidate fixed-cohort risk, **current-month** S&P 500 return) | **−0.3462** |
| Independently untouched 24-month out-of-sample forecasts | **0** |
| Evidence for leading 2000/2008 historical crisis onset | **none** |

**Interpretation:** descriptive next-month linear association is small in magnitude. The more pronounced *contemporaneous* association raises a reasonable suspicion that retrospective inputs describe stress when it is already visible; it does not prove causality. No calibrated prediction performance, backtested position policy, excess return, significance level or probability of an impending crisis can be inferred. First-month source cohort and formulas are still retrospective, and S&P500 returns were retrieved retrospectively; this is NOT independently historically preregistered OOS.

## 4. Exact source-level outputs

Verified in run 45011613323, original archived source responses and tests:

- [Original SEC SGML audit implementation](../scripts/aics_pit100_sec_sgml_clock_audit.py); source result `aics_pit100_100_sec_sgml_header_clock_audit.json`, raw SGML gzip files under `pit100_sec_sgml_header_raw/`.
- [24m ALFRED original vintage implementation](../scripts/aics_pit100_alfred_24m_vintage_audit.py); source result `aics_pit100_24m_alfred_two_source_vintages.json`, original JSON gzip under `pit100_alfred_24m_vintage_source_raw/`.
- [Fixed first-month cohort S&P500 lead/lag implementation](../scripts/aics_pit100_24m_expost_leadlag_diagnostic.py); source results `aics_pit100_24m_expost_leadlag_falsification.json` + corresponding `.csv`.
- Negative chronology / wrong-source / fake promotion tests: [SEC](../tests/test_aics_pit100_sec_sgml_clock_audit.py), [ALFRED](../tests/test_aics_pit100_alfred_24m_vintage_audit.py), [lead/lag](../tests/test_aics_pit100_24m_expost_leadlag_diagnostic.py).
- All source checks and exports are integrated in [GitHub Actions source workflow](../.github/workflows/aics-ten-real-source-waves.yml). The workflow passed full final archive & SHA checks.

## 5. Formal status and next actions

| Model requirement | Current |
|---|---|
| Verified project delivery milestones | **22/66 (~33/100)** |
| PIT100 distinct research roles and as-of audit cutoffs | **100/100** |
| Observed SEC SGML headers and time classifications | **100/100** |
| Official 24m ALFRED realtime vintage responses | **48/48** |
| Independent 24m full 11-node source-PIT certification | **0/11 nodes** |
| Complete monthly AICS index | **null** |
| Independent ex-ante calibrated forecast skill | **null** |
| Prediction / timeline of 2000 & 2008 pre-onset | **not reproduced** |
| Actual named-bank→SPV dollar contagion matrix | **not established** |
| Production trading and auto-reweighting | **disabled** |

Next highest-value progress is no longer more model versions: map the 100 SGML acceptance dates back to **the actual scoring source accessions**, obtain historical first-public provenance where possible, verify all **11 node** formulas and their market-trading cutoffs, and preregister an untouched out-of-sample historical forecasting task. Until then, a correlation of −0.135 does **not** demonstrate predictive skill. No real source observation is fabricated or backfilled.
