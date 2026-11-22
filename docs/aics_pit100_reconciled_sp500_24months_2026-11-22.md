# AICS PIT100 — сверка двух пересборок и S&P 500 за 24 месяца

**Результат:** [GitHub Actions run 45010911937](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/45010911937), **success**, 22 ноября 2026 года. Артефакт [14749553491](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/45010911937/artifacts/14749553491), **90 дней хранения**.

## Что проверено

Два независимо реализованных алгоритма пересчёта 64 исходных source events и 100 PIT-аудиторских отсечек согласованы месяц за месяцем:

| Показатель | Рыночное закрытие | Календарный конец месяца |
|---|---:|---:|
| Период | 2024-11 — 2026-10 | 2024-11 — 2026-10 |
| Пересчитано отдельных месяцев | **24** | **24** |
| Согласованность двух алгоритмов | **24/24** | **24/24** |
| Покрытие исследовательскими source weight-months | **50,00%** | **50,89%** |
| Известный вес исследовательских источников за октябрь 2026 (макс. 1050) | **725** | **950** |
| Недостающие источники | Не заполняются нулями | Не заполняются нулями |
| Полный сертифицированный AICS | **Нет** | **Нет** |

*50,00% и 50,89%* — доли наблюдаемого суммарного веса источников в 24-месячных исследовательских срезах, **не** точность предсказания, не сертификация модели. *725/1050* или *950/1050* — веса присутствующих кандидатных рядов, а **не** величина индекса AICS.

## Одна реальная ошибка источника, выявленная сравнением

Две разные архивные записи **Semiconductors Supply / Fed G.17** имели одинаковую заявленную дату выпуска **2025-12-23**:

- Ретроспективная оценка 74,70;
- Ретроспективная оценка 74,40.

Раньше один алгоритм выбирал последнюю запись по внутреннему порядку, другой помещал обе в карантин. Теперь **оба алгоритма помещают обе конфликтующие записи в карантин**. Предыдущее однозначное исходное исследовательское наблюдение **75,50** (2025-12-03) хранится с собственной датой и возрастом, но не признаётся independently first-release PIT-certified. Это исправление действительно изменяет исследовательский срез декабря 2025-го.

## Реальный 24-месячный S&P500 контекст

Сохранены **24 наблюдённых ретроспективно месячных закрытия S&P 500** (2024-11 — 2026-10) и 23 фактических доходности между соседними месяцами. Каждая строка нового CSV содержит:

`month`, market/calendar cutoff, observed source node count, observed weight, coverage %, **partial research points NOT AICS**, 90-day fresh weight, missing-node list, observed S&P 500 closing level and monthly return, `full_11node_AICS = null`, `AICS_SP500_spread = null`.

S&P500 series itself is retrospectively obtained, not independently verified 24 historical publisher feed snapshots. It is descriptive comparison, not a validated trading backtest. The partial candidate points **must not be compared to the 450/500 full-index entry/exit thresholds**.

## Exact reproducible files

- [Conflict-safe first reconstruction](../scripts/aics_pit100_rebuild_24m_research.py)
- [Second source-event reconstruction and 24-month observed S&P 500 alignment](../scripts/aics_pit100_rebuild_24_month_public_filing_panel.py)
- [New month-by-month reconciliation validator and Markdown/CSV export](../scripts/aics_pit100_reconcile_24m_sp500.py)
- [Negative source-date, PIT, index and S&P validation tests](../tests/test_aics_pit100_reconcile_24m_sp500.py)
- [Daily automated GitHub workflow](../.github/workflows/aics-ten-real-source-waves.yml)

Inside artifact **14749553491**:

`aics_pit100_reconciled_24m_sp500_monthly.json`

`aics_pit100_reconciled_24m_sp500_monthly.csv`

`aics_pit100_reconciled_24m_sp500_monthly.md`

Existing two independent original panels and the source original bytes / SHA-256 manifests are also included. The same successful GitHub run archived **100/100 original SEC primary documents**, **0 download failures** from those tasks. The archives are **current captures of historical published documents**, not independently historical first provider receipts.

## Remaining evidence gaps

**Project progress unchanged: 22/66 milestones (~33/100)**. **0/11 fully PIT-certified risk nodes**, **0 verified full 11-node monthly indices**, **0 independent untouched 24m OOS validations**, **0 independently verified matched named lender-dollar exposures**. Model weights remain exactly **1050**. **No investment orders or auto-reweighted production**.

Next necessary work: independently validate historical source timestamps (SEC acceptance/public dissemination intraday, dated Fed G.17 and ALFRED release vintages, revised equity constituent universe), then audit fixed node scoring formulas and out-of-sample dates. More deterministic roles/tests alone do not establish predictive skill.

**Conclusion:** both 24-month research reproductions have no remaining source-score/node-month disagreements, and the G.17 timing ambiguity is quarantined. This is a materially corrected *research data panel*, **not** a newly certified AICS forecast.
