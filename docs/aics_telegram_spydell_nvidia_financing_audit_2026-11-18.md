# AICS: аудит 11 Telegram-скриншотов Spydell_finance — 18.11.2026

**Статус:** реальные вложенные изображения пользователя прочитаны визуально и хешированы (11 файлов JPG). **23 различимых имени компаний/контрагентов**, **28 утверждений о суммах/отношениях**, **12 связей** внесены в исследовательскую базу AICS. Это анализ **вторичного источника**, а не вывод о доказанном правонарушении, дефолте, круговой выручке или рекомендуемой торговой операции.

- Исходный пост Telegram обозначен в скриншотах как Spydell_finance, 16 ноября 2026 года.
- Реестр с **отдельным SHA-256 каждого изображения**, номерами скриншотов, компаниями, оригинальными формулировками и первичной сверкой: [source claim ledger](../aics_data/research/spydell_telegram_nvidia_circular_financing_claims_2026-11-18.json).
- Бинарные JPG находятся среди пользовательских вложений в чате; **в GitHub они ещё не размещены**. Наличие SHA хеша в JSON не заменяет оригинальные байты.
- Первичный отчёт NVIDIA: SEC [10-Q за период до 26 июля 2026, accession 0001045810-26-000075](https://www.sec.gov/Archives/edgar/data/1045810/000104581026000075/nvda-20260726.htm). SEC [filing index](https://www.sec.gov/Archives/edgar/data/1045810/000104581026000075/0001045810-26-000075-index-headers.html) указывает **filed_at 26.08.2026** -> AICS **available_at 09.09.2026** (+14 календарных дней).
- Точная редакция SEC HTML подтверждена публичным SEC URL; оригинальные байты SEC с SHA-256 ещё предстоит архивировать в проекте для окончательной аудиторской цепочки. **PIT score gate не открыт.**

## 1. Что из Telegram уже подтверждается SEC

Все суммы в **миллиардах USD**, если не указано иное; период **as of 26 July 2026 / NVIDIA Q2 fiscal 2027**, а не календарный Q2 2026. Отдельные сделки, балансовые активы, денежные потоки, условные гарантии и будущие обязательства **нельзя складывать** в общий «долг».

| Telegram утверждение | Проверка в NVIDIA SEC 10-Q | Уточнение риска |
|---|---|---|
| **$108.5** guarantees | **$105.0** SB Energy + **$3.5** AI-cloud land/power/shell = **$108.5** maximum gross exposure | Условные гарантии, поэтапный запуск, не уже выданные деньги и не начисленный убыток; проект SB Energy 4.25 GW / 9 фаз, арендаторы OpenAI |
| **$36** take-or-pay | Additional commitments: **$36** AI cloud agreements | Контракты cloud procurement/participation, точная характеристика «take-or-pay» требует договора. Партнёр вправе продавать мощности третьим лицам |
| **$29** leases of own GPUs | Future commitments: **$29** cloud service agreements | Облачные сервисы, в том числе R&D; это не тот же долг, что банковский кредит, и не обязательно подписанная обратная аренда собственных чипов |
| **$25** own data-center leases and **$20** transition third-party leases | Разные future lease **not commenced** disclosures: **$25** для NVIDIA, **$20** для третьих лиц | Ещё не начавшиеся аренды; сроки строительства и передачи существенны |
| **$63.06** accounts receivable; prior quarter **$40.71** | Accounts receivable **$63.059** billion as of Jul 26; Q1 IR **$40.710** billion | Изменение **+$22.349** billion. Это реальный AR stock, но AR != выданный денежный кредит и рост сам по себе не доказывает невозврат |
| **$90.68** equity portfolio | Marketable equity **$42.783** + nonmarketable equity **$47.898** = **$90.681** | Подтверждён subtotal **этих двух строк**, но не полный equity portfolio: часть long-term public shares и equity-method holdings отражаются в других строках |
| **$25** future equity investments | Note 10: **$25** equity investment commitments | Будущие условные обещания, не уже купленные акции; нельзя прибавить к AR как к текущему долгу |
| Скрытый SPV | Note 6: **$3.3** equity-method investments in infrastructure financiers; max loss exposure **$4.7** in related unconsolidated VIEs | VIE/неконсолидация в SEC раскрываются. Из этого **не следует**, что любой произвольный партнёр является юридическим SPV Nvidia |
| Частные «бумажные прибыли» | **$9.1** cumulative gross unrealized gains on nonmarketable equity | Учетная переоценка, **не поступление наличных** |
| Supplier prepayments **$6.48** | Operating cash flow: **-$6.480** change in **prepaid expenses and other assets**, **за первое полугодие** FY27 | Telegram сужает широкую статью до «авансов фабрикам памяти» без отдельного подтверждения |
| Other assets **$15.75** from **$8.30** | Balance sheet **$15.746** vs **$8.301** in Jan 2026 | Состав шире авансов поставщикам |
| Growth of supply commitments | Note 10: **$279** supply and capacity future commitments | Не балансовый долг, не гарантированная выручка |

Дополнительные SEC данные: по итогам 26.07.2026 NVIDIA отмечает возможность предоставлять некоторым инвестиционно-рейтинговым заказчикам **90 дней — 1 год** на оплату; 5 прямых клиентов составляют **22%, 14%, 13%, 11%, 10%** AR. Это реальный показатель концентрации, но личности прямых клиентов в этой таблице SEC не раскрыты.

## 2. Обязательное исправление цифры Telegram

На скриншоте **$6.41 млрд** трактуется как «все полученные авансы клиентов». SEC в Note 7 называет **$6.412 млрд total deferred revenue**, а непосредственно **customer advances, включённые в текущую отложенную выручку, — $2.8 млрд** по состоянию на 26.07.2026. В первом полугодии также были **поступления авансов $15.6 млрд** (flow), но это иная метрика, чем остаток $2.8 млрд (stock). Эти величины нельзя объявлять одной суммой или выводить из них отсутствие спроса на NVIDIA.

Показатель **59.8 дня DSO** на скриншоте — расчёт автора. Реальная выручка и AR позволяют построить **собственный явно документированный** DSO, но SEC не подтверждает конкретную формулу автора; по умолчанию не засчитываем его как audited historical observation.

## 3. Компании и связи, которые выделены из схем

**NVIDIA:** централизованный технологический поставщик, инвестор/арендатор/условный гарант (разные виды риска по каждому договору).

**AI-клиенты / neoclouds:** CoreWeave, Lambda, Firmus, SharonAI, GMI, Nscale, Crusoe, OpenAI, xAI. За исключением упоминания OpenAI в обеспеченной SB Energy аренде, *конкретные* финансовые суммы каждого частного партнёра ещё **не подтверждены оригинальными signed contracts**.

**Power/DC / SPV:** SB Energy (SEC-подтверждена гарантия), инфраструктурные финансирующие VIE (существование категории подтверждено SEC), xAI/Colossus (структуру $20 млрд ещё проверять). Визуальная стрелка «SPV» **не доказывает** договорной юридической конструкции.

**Semiconductors:** Groq (SEC прямо упоминает non-exclusive licence и **$2.944 млрд** cash flow financing line in 1H FY27, но **не все $17 млрд** Telegram), Lumentum, Coherent, Intel, Nokia, Synopsys. «$10 млрд оптики», «$17 млрд Groq» — **не удостоверены по размеру обязательств**.

**Фонды / private-credit financing:** Valor Equity, Apollo, Blackstone, Brookfield, Magnetar, Macquarie. Скриншоты **не устанавливают** точные текущие непогашенные остатки, priority waterfall и collateral-права каждой компании. Позицию частного фонда нельзя автоматически засчитать страховщику.

## 4. Остались неподтверждёнными оригинальным договором

| Утверждение Telegram | Статус |
|---|---|
| CoreWeave **$6.3 млрд** NVIDIA take-or-pay до 2032 | Требуется сверка обеих сторон и contract terms |
| Firmus/SharonAI/GMI **$29.7 млрд** пул | Требуются оригинальные сделки; не считать вместе с $36 млрд, пока не исключено пересечение |
| Lambda **$1.5 млрд** аренда / 18 тыс. GPU | Требуется подписанный lease или SEC original |
| xAI Colossus **$20 млрд** (equity $7.5 + debt $12.5), из них $2 млрд от NVIDIA | Требуется первичный кредитный контракт и распределение drawn vs committed |
| Groq **$17 млрд** ($13+4) и оптика/сети **$10 млрд** | Нужно отличить действительное исполнение, будущие платежи, рамочные и отменяемые соглашения |
| Сводный вывод «всё это скрыто, поэтому NVIDIA — квазибанк, который полностью генерирует собственную выручку» | Интерпретация автора, не доказанный accounting fraud или тождество sales = loans |

## 5. Что реально улучшено в архитектуре AICS

Сохраняем **все те же 11 узлов, веса 1050**. Новая предметная аналитическая карта:

```
NVIDIA (equity / guarantees / lease commitments / AR)
  → SPV + Power/Data Centers: 4.25 GW, $105bn contingent support (SEC confirmed)
  → Neoclouds: $36bn AI-cloud commitments (counterparties not yet allocated)
  → AI Demand: AR, extended payment terms, revenue vs cash collection
  → AI Equities: $42.783bn public + $47.898bn private equity subset
  → Semiconductors Supply: $279bn supplier/capacity commitments
  → Private Credit: unverified lender counterparties / VIE look-through required
```

**Приоритетные новые candidate features:** gross guarantee ceiling vs phase-effective exposure; pledged equipment/collateral resale value; unfunded vs drawn project debt; *third-party* revenue backed by independent cash collections; committed cloud-capacity purchases vs outside paid usage; receivables ageing and concentration; equity investment unrealized marks vs cash earnings; contractual lease assignment and recourse. Все они пока **отдельные исследовательские признаки**, не калиброванные 0–100 node scores.

### PIT и антидвойной счёт

- Период NVIDIA **2026-07-26**, SEC `filed_at=2026-08-26`, AICS `available_at=2026-09-09` (только этот проверяемый квартал, без backfill).
- Нельзя конвертировать $108.5bn maximum contingent guarantee в текущий funded loan/debt.
- Нельзя добавлять вместе сумму инвестиционных активов $90.681bn, будущие equity commitments $25bn, receivables $63.059bn и инфраструктурные гарантии $108.5bn как единый риск без causal exposure netting.
- Отчёт NVIDIA 10-Q сам по себе ещё требует SHA-256 байтов и независимой PIT source provenance фиксации перед научной сертификацией.
- Telegram screenshots, графики автора и «финансовый схематоз» — **secondary research leads**; не доказанный прогноз, не основа автоматических торговых действий.

**Итог:** screenshots **изучены и внесены в research layer AICS**. Для сертифицированного индекса **AICS = N/A, score nodes = 0/11**. Ни один из 66 этапов нельзя добавить только за исследовательское распознавание компании.
