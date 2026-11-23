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

## Исправление после первоисточника ФРС от 23 декабря 2025

**Обновление 22.11.2026: прежнее объявление двух записей «конфликтом» было ошибочным.** ФРС во время задержек публикации одновременно выпустила значения NAICS 3344 за **октябрь 2025 — 74,70** и за **ноябрь 2025 — 74,40** с одной датой выхода **23.12.2025**. Это **разные месяцы измерения**, а не два несовместимых числа за один месяц. Прямой архив ФРС: [выпуск G.17 23.12.2025](https://www.federalreserve.gov/releases/g17/20251223/table7.htm) и [официальное разъяснение](https://www.federalreserve.gov/releases/g17/g17_technical_qa.htm).

В исправленной версии оба изначально датированных наблюдения сохранены, декабрьский месячный исследовательский срез использует более позднее наблюдение **за ноябрь — 74,40**, а не устаревшее сентябрьское 75,50. Подтверждение самой даты официального выпуска **не** подтверждает первый исторический момент доставки data-feed или самостоятельную сертификацию индекса. Прежние результаты и артефакт 45010911937 — архивная предисправительная версия; новая сверка производится в [ежедневном GitHub workflow](../.github/workflows/aics-ten-real-source-waves.yml).

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

**Conclusion (updated):** original G.17 October and November 2025 observations were jointly released Dec 23, 2025 and are not a duplicate observation conflict. New research replays preserve both with the latest observation month selected. Source first delivery and certified AICS predictive performance remain unproven.
