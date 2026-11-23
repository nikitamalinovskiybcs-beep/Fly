# AICS V22: десять настоящих волн улучшения сбора и 260 SEC Company Facts

**Дата отчёта:** 22 ноября 2026. Источник фактов: [успешный Github Actions run #44954280046](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44954280046), SHA `c33bfbfd602be9568e1360fd370a6bd2b45d206c`.

**Верифицированный итог из лога и SHA-проверки**:

| Показатель | Результат |
|---|---:|
| Последовательные, реально выполненные волны | **10/10** |
| Агенты сбора, по одному узлу на волну | **10/10** |
| HTTP-запросов к оригинальным публичным издателям | **36** |
| Ответов успешно сохранено и проверено SHA-256 | **36/36 фактически выполненных HTTP-запросов** |
| SEC submissions JSON (последний публичный индекс filings) | **15 первичных исходных источников** |
| SEC XBRL companyfacts JSON | **15/15 скачанных числовых snapshot** |
| Реальных числовых SEC XBRL-объектов, отобранных из актуальных оригинальных snapshot | **260** |
| EIA demand API | **не вызывался**, потому что отсутствует `EIA_API_KEY` |
| Переписанный / придуманный 24-месячный ряд AICS | **нет** |
| Сертифицированный исторический PIT источник / результат OOS | **нет** |
| Изменения фиксированных весов 11 узлов (сумма 1050), сделки | **нет** |

**Важно про 36/36:** это число успешно архивированных **реально выполненных** HTTP-запросов, **не** показатель полноты всей вселенной данных. Один из 20 исходных источников (EIA) пропущен из-за отсутствующего API key. Повторная загрузка CoreWeave/Nebius для SPV является проверкой изменения их официального индекса, а не новыми issuer-quarter фактами.

## Что именно улучшено

Ранее 10 AICS collector agents архивировали в основном **SEC submissions metadata** плюс ALFRED DGS30/IORB, NY Fed SOFR, Fed G.17, и недоступный EIA. Теперь [новый код](../scripts/aics_ten_source_collection_rounds.py) для каждого SEC issuer получает **официальный source JSON `data.sec.gov/api/xbrl/companyfacts/CIK...`**, сохраняет его оригинальные байты, контрольную сумму и отдельно извлекает последние доступные SEC-filed numeric facts с исходным accession, единицами, периодом и filing date.

Сканируются только реальные `us-gaap` теги `NetCashProvidedByUsedInOperatingActivities`, `PaymentsToAcquirePropertyPlantAndEquipment`, `Revenues`, `RevenueFromContractWithCustomerExcludingAssessedTax`, `LongTermDebtNoncurrent`, `CashAndCashEquivalentsAtCarryingValue` — если они присутствуют. Нет фальшивой нулевой строки на отсутствующий тег. Всего сохранено **260** фактических записей, но это **не 260 независимых кварталов** и **не 260 обучающих OOS-меток**: один issuer может иметь сразу несколько filing records или сравнимых/несравнимых контуров. Исторические ценовые/basket/funding-specific показатели остаются отдельными.

Хронология: `filed_at+1 calendar day` — **исследовательская кандидатная дата**, а не доказанный dissemination timestamp. Этот collector снимает **современный snapshot** SEC; актуальный companyfacts мог обновляться или пересматриваться спустя исходные даты, поэтому записи не включаются автоматически в модель AICS и не считаются независимой PIT-аттестацией.

## Десять реальных итераций

1. **Private Credit**: ARCC, BXSL, OBDC — originals submissions + XBRL; nonaccrual metric всё ещё требует original filing tables.
2. **Insurers**: PRU, MET — оригинальные issuer submissions + текущие XBRL numeric; специфические credit/nonaccrual таблицы требуют отдельной проверки.
3. **UST 30Y**: ALFRED DGS30 текущая vintage (не исторически доказанная first-public feed).
4. **Neoclouds**: CRWV, NBIS — оригинальные SEC originals + numeric XBRL.
5. **Hyperscalers**: MSFT, AMZN, GOOGL, META — operating cash flow/capex и другие реально присутствующие XBRL values, где доступны.
6. **SPV**: второй **реальный** HTTPS запрос к CRWV/NBIS submissions и SHA comparison (не выдуманные SPV exposure числовые значения).
7. **Repo**: New York Fed SOFR и ALFRED IORB.
8. **Power/Data Centers**: SEC APLD + EIA-930 с явной недоступностью из-за отсутствующего `EIA_API_KEY`.
9. **Semiconductors Supply**: Fed G.17 + SEC NVDA и MU, XBRL accounting facts не выдают сами по себе supply bottleneck score.
10. **AI Demand**: SEC AVGO original metadata + numeric companyfacts.

**Запуск и архив:** [GitHub Actions #44954280046](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44954280046); [downloadable job artifact #14726602372](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44954280046/artifacts/14726602372). Artifact `aics-ten-actual-collection-waves-numeric-originals` содержит первичные байты, `ten_rounds_manifest.json`, `actual_sec_xbrl_facts_unverified.json`. Размер 3 613 810 bytes; retention до **19 февраля 2027**. Верификация собственных исходных SHA всех 36 записей прошла в CI. Тесты нового сборщика **5/5 пройдены**.

**Автоматика:** [aics-ten-real-source-waves.yml](../.github/workflows/aics-ten-real-source-waves.yml) срабатывает по изменениям своего кода, вручную или **по будням в 23:15 UTC** на default branch; GitHub cron может задерживаться. Соседний [AICS twenty agents workflow](../.github/workflows/aics-ten-source-agents-ml.yml) остаётся отдельным, не меняет историю из этих companyfacts автоматически.

## Где реальная незакрытая работа

1. Для CFO/capex отбирать **quarter-only** периоды, не путать YTD cash flows, diluted/taxonomical tags, cash capital expenditures и accruals; проверять issuer scope и first original filing accession, не брать исправленные значения из будущего.
2. Получить конкретные issuer nonaccrual таблицы для BDC/Insurers; XBRL generic balance-sheet data **не заменяет** required risk factor.
3. Отдельно разметить историческую source receipt timeline и corporate actions AI Equities; только после этого ML может идти на строгую **walkforward / untouched out-of-sample** проверку.
4. Для EIA source нужен `EIA_API_KEY` в Actions secret — без него Power/Data Centers остается partial. EIA-930 показывает региональный спрос на электроэнергию, не уникальное AI/data-center consumption.

**Вывод:** десять раундов сделали **реальный существенный прирост качества сырьевой базы**: из 15 найденных SEC issuer filing indexes в дополнение получены **15 оригинальных companyfacts snapshots с 260 числовыми исходными фактами**. Но 24-month V18 research coverage **50.89%** не меняем до source-to-score validation; полный AICS по-прежнему **0/24**.
