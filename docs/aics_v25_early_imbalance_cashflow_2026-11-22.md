# AICS V25 · предкризисный дисбаланс CapEx / OCF, без подмены индекса

**Дата исследования:** 22 ноября 2026. **Исходные документы:** SEC-filed earnings/cashflow originals и четыре версии уже сохранённых исходных исследований. **Автоматический выпуск:** [GitHub Actions run 44956161636](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44956161636) — **success, 7 original-data safety tests passed**. Новая исследовательская модель: [scripts/aics_early_imbalance_cashflow_shadow.py](../scripts/aics_early_imbalance_cashflow_shadow.py). Исходные 11 весов сохраняются (=1050), дополнительный узел не создан.

## Зачем

Изначальная AICS историческая презентация сравнивала передаточный стресс в AI с telecom-2000 и shadow-banking-2008, но оба старых заявленных crossing >500 пришлись уже **после выбранного начала соответствующих потрясений**. Чтобы наблюдать ещё *накопление дисбаланса до кризиса*, отделили **funding / buildout imbalance** от existing 11-node crisis-transmission stress. Нельзя назначить историческое «70% похоже на 2000», потому что архивно сопоставимая 2000/2008 PIT-таблица пока отсутствует.

## Честная экономическая величина

**Gross consolidated cash purchases of PP&E / consolidated operating cashflow (OCF)**, одинаковая четвёрка **Microsoft, Amazon, Alphabet, Meta**, USD млн. Денежный разрыв `OCF − cash PP&E`; отрицательное число означает, что одного квартального OCF не хватает на *этот* компонент инвестиций; это **не** величина взятого нового кредита, не автоматически отрицательный свободный денежный поток по всем GAAP определениями и **не** AI-only investment. Внеоборотные активы покупаются также на накопленный cash, долг, акции, leases и иные средства. Cash PPE отличается от затрат «на AI GPU».

| SEC квартал | OCF, $млрд | cash PP&E, $млрд | OCF − cash PP&E, $млрд | cash PP&E / OCF | Негативный issuer gap | Первая дата всех 4 SEC+14 |
|---|---:|---:|---:|---:|---:|---|
| 2025 Q1 | 114.235 | 71.902 | +42.333 | 62.94% | Amazon (1/4) | 2025-05-16 |
| 2025 Q2 | 128.470 | 88.246 | +40.224 | 68.69% | 0/4 | 2025-08-15 |
| 2025 Q3 | 158.995 | 97.271 | **+61.724** | **61.18%** | **0/4** | 2025-11-13 |
| 2025 Q4 | 178.833 | 118.632 | +60.201 | 66.34% | 0/4 | 2026-02-19 |
| **2026 Q1** | **missing** | **missing** | **missing** | **missing** | **not inferred** | **missing** |
| 2026 Q2 | 171.759 | 165.050 | +6.709 | 96.09% | Amazon, Alphabet (2/4) | 2026-08-14 |
| **2026 Q3** | **175.498** | **201.923** | **−26.425** | **115.06%** | **Amazon, Alphabet, Meta (3/4)** | **2026-11-13** |

Exact date-sensitive reconstruction of each original issuer/quarter plus four-issuer aggregate can be regenerated from [research originals](../aics_data/research/hyperscalers_2025_q1_q3_original_sec_cashflow_2026-11-21.json), [2025 Q4 originals](../aics_data/research/hyperscalers_2025_q4_original_sec_cashflow_2026-11-21.json), [2026 Q2 originals](../aics_data/research/hyperscalers_cash_coverage_june_to_september_2026.json), and [2026 Q3 originals](../aics_data/research/hyperscalers_operating_cash_flow_coverage_2026_q3.json). **Original SEC filing metadata is source-named, but historical publisher-bytes receipt is not independently timestamp/PIT attested.**

## Изменение 2025 Q3 → 2026 Q3

- **Cash PP&E выросли +107.59%**, а **OCF только +10.38%**.
- Доля cash PP&E от OCF выросла **с 61.18% до 115.06%, на +53.88 процентных пункта**.
- 4-issuer OCF-minus-investment gap **с +$61.724 млрд на −$26.425 млрд**, разница **−$88.149 млрд**.
- Отрицательная разница: **0 → 3 из четырёх issuers**. Microsoft Q3 2026 остаётся +$18.633 млрд; Amazon −$34.837 млрд, Alphabet −$9.065 млрд, Meta −$1.156 млрд.

Это **серьёзный кандидат на ранний BUILDOUT-imbalance**, независимый от цены акций и рыночных CDS. Он сам по себе не доказывает пузырь и не переводит опасность в «сходство с 2000» или probability of crisis. Отдельные источники обязанностей, GPU-utilization, AI revenue, historical fixed universes и debt leverage необходимы.

## Время и look-ahead — главное ограничение

Данные четверых issuers за **2026 Q3 не могли находиться на октябрьском рыночном закрытии 30.10.2026** при legacy SEC+14: только **13 ноября 2026** последняя запись стала пригодна для условного research. **Нельзя** использовать это ухудшение для объяснения «предупреждения в октябре». Source-gated replay на 2026-10-30 показывает **только 2026 Q2**, а на 2026-11-11 — **неполную** Q3 четвёрку (Amazon недоступен); модель не рассчитывает тотал с пропущенной компанией и не проставляет ноль.

В 2025 Q2 единственный Microsoft Q2 derived cashflow = originally dated SEC FY2025 10-K minus originally dated 2025 9M 10-Q с датой доступности более позднего оригинала. Никакой скрытой 2026 Q1 интерполяции, ретроспективной перебалансировки или замены issuer universe.

## Связь с «похоже на 2000 или 2008?»

| Измерение | На текущем подтверждённом Research |
|---|---|
| Overinvestment / buildout (ключевой механизм telecom-2000) | **Наблюдается растущий 4-company gap**. Это конкретная проверяемая экономическая переменная, но пока не доказано, что весь CapEx — AI, а аналог 2000 не нормализован |
| Demand monetization | AI-specific paid customer revenue и GPU load utilization **не подтверждены** этой cashflow таблицей |
| Collateral / GPU depreciation | Нет достаточной оригинальной цены resale GPU и debt collateral vintage |
| Hidden SPV leverage (отличительная 2008-ось) | Нет сопоставимой borrower→SPV→BDC/insurer матрицы с original recourse, guarantee и maturity |
| Repo / wholesale funding run | Текущие первичные funding observations собираются отдельно; нет подтверждения истории repo haircuts и использования future vintages |
| Вероятность crash / 2000 similarity / 2008 similarity | **null**: не подделываем вероятность |

**AICS Index:** исследовательский срез рынка октября 2026 по-прежнему **8/11**, известный вес 725/1050, неполная сумма 268.39 (это **не** новый индекс). Текущий precrisis imbalance — **отдельная независимая исследовательская таблица**, никаких изменений 11 весов, 450/500 thresholds, hot multiplier или торгового сигнала.

## Проверка и интеграция

[GitHub Actions — отдельный V25 реплей](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44956161636) воспроизвёл все **24 issuer-quarter source pairs** по шести доступным кварталам (пропуск 2026 Q1 явно показан), проверил real SEC+14 dates, одинаковый состав 4 компаний, суммы и отсутствие источников до публикации. Верифицированные числа за Q3 с точностью до USD млн:
`2025: 158995 − 97271 = 61724`; `2026: 175498 − 201923 = -26425`.

Новый Research Challenger [scripts/aics_ten_model_improvement_agents.py](../scripts/aics_ten_model_improvement_agents.py) дополнительно включает `early_cash_imbalance_research`, но **не выдаёт эти данные за историю или кризисный прогноз**. Это конкретный шаг в сторону исходной задачи AICS — ранней диагностики **до** кредитного contagion.

## Следующая приоритетная разработка

Получить первичные **2026 Q1** quarterly cashflows по всем четырём, с issuer scope, SEC filed date +14, затем построить **непрерывные** квартальные значения с 2025 Q1 по 2026 Q3. После этого проверить, сколько кварталов разрыв и спрос ухудшаются **до** независимых неприятных credit events. Отдельно собирать original AI utilization, datacenter PPA and debt/lease/SPV obligation data, которые позволят связать 2000 buildout и 2008 leverage pathways. До валидированных historical vintages и untouched OOS нулевая вероятность/индекс не оцениваются.
