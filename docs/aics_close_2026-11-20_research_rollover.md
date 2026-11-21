# AICS — исследовательский срез после закрытия 20 ноября 2026 года

**Итог research rollover = 669.09**; разница с опубликованным срезом 19 ноября = **0.00**. **Это НЕ полностью новый 11-узловой as-of-close индекс:** обновлён только рыночный узел AI Equities; остальные десять датированных оценок сохранены из исследовательского выпуска 18 ноября. Сертифицированный AICS = **N/A**, независимый PIT = **0/11**, 24-месячный OOS = **0/11**; инвестиционный сигнал и сделки **не производились**.

## 20 ноября, основная сессия США — фактические цены

Источник: таблицы historical daily open/close StockAnalysis, с атрибуцией S&P Global Market Intelligence, изучены 21 ноября 2026 года. Обозначенные `Change` у поставщика обычно сравнивают цену закрытия с предыдущим днём; ниже мы **отдельно** считаем open-to-close, как требует текущая формула AICS. ORCL торгуется на NYSE. Сырые лицензируемые страницы не архивированы, исторический exchange PIT и лицензия на повторное распространение не подтверждены.

| Бумага | Открытие, $ | Закрытие, $ | От открытия до закрытия |
|---|---:|---:|---:|
| [NVDA](https://stockanalysis.com/stocks/nvda/history/) | 143.52 | 125.53 | -12.535% |
| [MSFT](https://stockanalysis.com/stocks/msft/history/) | 493.74 | 484.52 | -1.867% |
| [GOOGL](https://stockanalysis.com/stocks/googl/history/) | 274.50 | 265.29 | -3.355% |
| [AMZN](https://stockanalysis.com/stocks/amzn/history/) | 253.48 | 246.82 | -2.627% |
| [META](https://stockanalysis.com/stocks/meta/history/) | 583.91 | 560.84 | -3.951% |
| [MU](https://stockanalysis.com/stocks/mu/history/) | 665.46 | 594.51 | -10.662% |
| [ORCL](https://stockanalysis.com/stocks/orcl/history/) | 108.48 | 101.19 | -6.720% |

**7/7 ниже открытия; равновзвешенная доходность open-to-close = −5.959674%.** AI Equities = `100 × 7/7 = 100.00` (верхняя граница шкалы); 19 ноября — также 7/7, но средняя сессионная доходность была −5.44%. Ухудшение глубины распродажи **не увеличивает** существующий уже насыщенный узел.

## Полный механический перерасчёт 11 узлов — при неизменных 10 старых входах

Ниже не выдаётся техническое повторение формулы за полную рыночную переоценку на дату закрытия.

| Узел | Вес | Research score / 100 | Пункты с множителем | Источник входа |
|---|---:|---:|---:|---|
| Private Credit | 150 | 33.33 | 64.99350 | 18 Nov release (carried) |
| Insurers | 125 | 0.91 | 1.47875 | 18 Nov release (carried) |
| UST 30Y | 125 | 78.26 | 127.17250 | 18 Nov release (carried) |
| Neoclouds | 100 | 75.78 | 98.51400 | 18 Nov release (carried) |
| AI Equities | 100 | 100.00 | 130.00000 | 20 Nov OHLC (new) |
| Hyperscalers | 100 | 13.09 | 17.01700 | 18 Nov release (carried) |
| SPV | 100 | 33.95 | 44.13500 | 18 Nov release (carried) |
| Repo | 100 | 86.96 | 113.04800 | 18 Nov release (carried) |
| Power/Data Centers | 50 | 37.50 | 24.37500 | 18 Nov release (carried) |
| Semiconductors Supply | 50 | 74.40 | 48.36000 | 18 Nov release (carried) |
| AI Demand | 50 | 0.00 | 0.00000 | 18 Nov release (carried) |

Контроль: сумма весов **1050**, базовая взвешенная сумма **514.6875**, строго горячих узлов (>60) **5**, множитель **1.30**, конечный результат **669.09375 → 669.09**. Без новых операндов десяти фундаментальных/макро-узлов нет оснований менять их значения или выполнять backfill. Repo и UST 30Y в исходном исследовательском определении используют последние доступные месячные окна по октябрь 2026 года, а не новую дневную котировку 20 ноября.

Нельзя считать `669.09` действительным независимым сигналом `>500 = exit`: это лишь исследовательская оценка по ретроспективно выбранным прокси. Никаких изменений весов, торговых решений или production verdict.

## Воспроизведение и источники

Из корня репозитория: `python -m scripts.aics_close_20261120`; проверки `python -m unittest tests.test_aics_close_20261120` (сам отчёт не утверждает прохождение CI до запуска). Входные цены и их страницы зафиксированы в [JSON-регистре](../aics_data/research/aics_2026_11_20_close_research_rollover.json), прежние 11 источников и оценки — в [19-Nov release](../aics_data/progress/research_release_2026-11-19.json), аудит независимо подтверждённых 6 этапов — [status.json](../aics_data/progress/status.json).

**Следующий реальный шаг:** легально архивировать и независимо перепроверить оригинальные OHLC Nasdaq и NYSE; для full close достать новые только допустимые PIT-входы остальных десяти узлов. До этого честное название результата — **11-node fixed-input rollover, not freshly updated certified AICS**.


## 21 November update: official-source eligibility overlay for Friday 20 November close

A second source-by-source pass is pinned in [machine-readable eleven-node overlay](../aics_data/research/aics_asof_2026_11_20_source_eligibility_overlay.json) and the fail-closed [replay](../scripts/aics_verify_close_source_eligibility_20261120.py). Run `python -m scripts.aics_verify_close_source_eligibility_20261120`. Separate [negative tests](../tests/test_aics_verify_close_source_eligibility_20261120.py) reject backdated SEC filings, unsourced node score changes, false original-byte rehashes and inconsistent Treasury points. This only **adds verified current source context**, not model calibration or historical PIT approval.

**Newly reviewed original sources and eligibility:**

- **UST 30Y, US Treasury:** official daily 30-year Treasury par yield **5.40% (2026-11-19) → 5.31% (2026-11-20), −9 bp**. [Treasury November 2026 official table](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value_month=202611&type=daily_treasury_yield_curve). The node's 78.26 score remains an October-end percentile of 20 daily *yield changes* against 23 prior monthly observations; one November daily yield is **not** the next complete comparison window. Official table is retrospectively accessed; no independent intraday release-time attestation.
- **Insurers, SEC MetLife:** 2026 Q3 filing [official accession 0001099219-26-000062](https://www.sec.gov/Archives/edgar/data/1099219/000109921926000062/0001099219-26-000062-index.htm) shows **filed 2026-11-06**, hence eligible **2026-11-20** by fixed +14 calendar-day rule. Prior [MetLife credit bridge](aics_insurers_met_q3_sec_credit_bridge_2026-11-20.md) has net mortgage **$83,839m**, allowance **$1,521m** versus prior-quarter allowance **$1,358m**; complete 43,289,538-byte SEC submission independent SHA-256 and raw replay remain **not attested**. This MET expected-loss reserve measure cannot be substituted into the **PRU nonaccrual-without-ACL** scored proxy of 0.91. Keep node 0.91; add evidence-only cross-check.
- **Neoclouds / SPV:** CoreWeave 2026 Q3 [SEC accession 0001769628-26-000465](https://www.sec.gov/Archives/edgar/data/1769628/000176962826000465/0001769628-26-000465-index.htm) filed **2026-11-12**; strict SEC+14 cutoff **2026-11-26**. Explicitly prohibit this filing from changing 20 November Neoclouds/SPV scores; earlier separate issuer IR statements are not treated as this later SEC 10-Q PIT vintage.
- **Semiconductors Supply, Federal Reserve:** latest dated original [2026-11-17 G.17 supplemental capacity Table 2](https://www.federalreserve.gov/releases/G17/20261117/table2_sup.htm) gives **October preliminary NAICS 3344 utilization 74.4%**, unchanged from the sealed October research proxy. The [next revision announcement](https://www.federalreserve.gov/releases/g17/20261117/default.htm) schedules a 2026-11-24 annual revision; it must **not** leak into 2026-11-20.
- **AI Equities:** seven dated 2026-11-20 regular-session OHLC observations are already in this document; **7/7 decliners, node 100.00**. Historical price pages were retrospectively viewed and are not independently archived provider PIT.
- **Private Credit, Hyperscalers, Repo, Power/Data Centers, AI Demand:** no new *comparable, eligible, replayed inputs for their exact frozen formulas* in this review. Retain dated earlier observations, without asserting that no public developments exist. Repo continues to use October month-end, not an arbitrary November 20 daily point.

**After the source pass:** **11/11 node eligibility statuses audited**, **5 specific new/renewed official-source cross-checks**, **1 equity score recomputed from Friday**, **0 supported changes to the other 10 historical research scores**. The mechanically reproduced research output is **669.09**; this is **not** proof that all eleven time-varying stress series were updated through Friday's close. Original strict technical audit **22/66**, independent PIT/OOS **0/11**, certified AICS **N/A**. Preserve old source semantics and weights (1050) until independently proved. No production verdict or trades.
