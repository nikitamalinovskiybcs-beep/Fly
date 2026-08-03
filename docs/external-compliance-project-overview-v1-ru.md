# Phoenix / Fly — внешнее описание проекта и compliance-обзор

## Статус документа

**Назначение:** материал для независимой проверки compliance, операционного
риска, модельного риска и инвестиционного комитета перед покупкой или
внедрением системы.

**Классификация:** исследовательское ПО и система поддержки решений. Это не
проспект, юридическое заключение, оценка пригодности продукта для клиента,
инвестиционная рекомендация или гарантия результата.

**Текущая коммерческая классификация:** диагностическое ПО, пока production
evidence gate заблокирован. Нельзя заявлять о готовности для live-подбора
продуктов или о доказанной доходности.

## Краткое описание

Phoenix / Fly — исследовательская платформа на Python и Streamlit для анализа
структурированных нот worst-of Phoenix. Она объединяет загрузку рыночных
данных, анализ payoff и барьеров, сравнение корзин, stress-тесты,
исследование калибровки, lifecycle бумажных нот, provenance, хранение данных и
аудит-контроли в одном процессе.

Цель платформы — сделать анализ структурированных нот прозрачнее и
воспроизводимее. Платформа не гарантирует доходность, не заменяет
лицензированного инвестиционного специалиста, не подтверждает автоматически
dealer quote и не создаёт live-сделки.

## Что делает платформа

Для заданной корзины и спецификации ноты workflow может:

1. получать рыночные данные через настроенные провайдеры и показывать источник;
2. считать показатели Phoenix и worst-of risk, включая P(KI), исследовательские
   оценки autocall, barrier-сценарии, coupon и stress-результаты;
3. сравнивать корзины и кандидатов structured products при заданных параметрах;
4. разделять estimated, simulated, historical replay, paper и realized
   информацию;
5. показывать assumptions, evidence status, freshness и blockers;
6. хранить paper-note и outcome записи для последующей realized evaluation;
7. запускать research-only calibration, self-learning и AI-review proposals;
8. сохранять audit artifacts для committee review и воспроизводимости.

## Архитектура и принцип работы

| Слой | Назначение | Значение для compliance |
| --- | --- | --- |
| Data module | Абстракция провайдеров, source labels, freshness и fallback | Проверяющий видит источник входного параметра и его verified-статус |
| Precompute/pipeline | Тяжёлые вычисления и сборка features | Рендеринг UI отделён от основных расчётов |
| Phoenix/payoff | Basket, barrier, coupon, autocall и stress logic | Terms и assumptions являются явными входами |
| Evidence gates | Data, outcome, quote, OOS и production checks | Отсутствие evidence блокирует или понижает допустимость решения |
| Calibration/OOS | Baselines, Brier, log-loss, ECE, walk-forward и fixed-24m anchors | Promotion модели требует независимой проверки |
| Paper/outcome | Simulated, replay, paper и realized lifecycle states | Paper marks не выдаются за realized performance |
| Storage | Local SQLite/DuckDB и опциональные cloud/self-hosted integrations | Локальный fallback снижает зависимость от одного cloud-провайдера |
| AI committee | Независимые research reviews и сохранение dissent | AI не меняет live weights, verdicts или trades |
| UI/audit | Decision map, evidence badges, blockers и audit reports | Можно связать вывод с его evidence status |

## Workflow принятия решения

```text
terms и basket
    -> market data и provenance
    -> payoff / P(KI) / autocall / stress calculations
    -> evidence и freshness gates
    -> baseline и OOS checks
    -> quote-fit и outcome review
    -> GOOD / CAUTION / BAD или BLOCKED research output
    -> human review до любого решения о покупке
```

Финальный output — сигнал поддержки решения, а не order, execution instruction,
suitability determination или гарантия того, что нота будет погашена через
autocall.

## Политика данных и evidence

Система различает:

- **Verified / realized:** подтверждённый внешний outcome или quote с нужными
  полями и provenance;
- **Paper:** смоделированный lifecycle с сохранёнными assumptions и marks;
- **Historical replay:** хронологический replay рыночной истории;
- **Simulated:** model-generated paths или stress-сценарии;
- **Estimated:** оценка провайдера или fallback для диагностики;
- **Missing / blocked:** требуемые данные отсутствуют или устарели.

Synthetic или сгенерированные строки не являются settled-note evidence.
Data-collector agent только проверяет внешние settled notes и не создаёт
синтетические settled records.

Replay, paper result, synthetic path или provider estimate нельзя представлять
как независимо realized market outcome.

## Количественные методы

Research stack включает детерминированные payoff/state-machine расчёты,
worst-of barrier analysis, correlated simulation, stress-сценарии,
прозрачные empirical/classical baselines, chronological replay, calibration
metrics (Brier score, log-loss и ECE) и fixed anchors на 6/12/18/24 месяцев.
Более сложные методы являются research-кандидатами и требуют evidence до
promotion.

Fixed-24m gate остаётся главным safety-контролем. Кандидат не переводится в
production только потому, что хорошо выглядит на in-sample или simulated
результате.

## Контроли AI-комитета

Настроенные провайдеры могут проверять bounded problem packet и возвращать
proposals, objections, implementation options и acceptance tests. Для каждого
review сохраняются provider, model, status, assumptions и dissent. Пропущенный,
skipped, timeout или quota-limited провайдер не считается одобрением.

AI output — только research input. AI не может:

- автоматически менять production weights;
- менять live verdict logic;
- создавать или отправлять trade;
- обходить fixed-24m/OOS gates;
- превращать replay или synthetic data в realized evidence.

## Текущая готовность и ограничения

Система **не заявляется как production-ready для live product selection**.
Внешнему проверяющему следует считать следующими обязательными условиями:

- подтверждённые независимые fixed-24m OOS/paper evidence;
- достаточный realized-note sample и качество outcomes;
- timestamped, provenance-verified dealer quotes и quote-fit;
- проверенные observation schedules и полные term sheets;
- независимая model validation и human model-risk sign-off;
- проверка security, access control, retention, incident response и deployment;
- legal, regulatory, suitability, conduct и jurisdictional review;
- документированные rollback, monitoring и change-approval procedures.

Есть и существенные model-risk ограничения: данные могут быть stale, неполными,
зависимыми от провайдера или затронутыми corporate actions и календарными
правилами; worst-of tails и correlations трудно оценивать; historical replay
может не отражать будущую ликвидность или dealer pricing; маленькая realized
выборка может давать нестабильную calibration; universe корзин, обработка
missing data и fallback rules могут создавать bias. Это требует disclosure,
sensitivity analysis и независимой model-risk проверки.

AI-комитет проверил этот документ как **REVISE / BLOCKED FOR LIVE USE**:
Mistral получил rate limit (`HTTP 429`), Ollama дал advisory approval, Groq
попросил яснее раскрыть ограничения и границы AI, а OpenRouter подтвердил,
что fixed-24m OOS evidence, realized-note quality, quote provenance и
independent model validation остаются обязательными условиями. Ни один AI vote
не является юридическим, regulatory, suitability или compliance approval.

## Compliance и due-diligence checklist

### Product и conduct

- Какое юридическое лицо владеет и эксплуатирует ПО?
- Кто будет пользователем: adviser, broker, issuer, research analyst или investor?
- В каких юрисдикциях система будет использоваться?
- Кто принимает финальное решение о покупке?
- Передаётся ли output клиенту как recommendation или solicitation?
- Документированы ли suitability, appropriateness, conflicts, inducements и
  disclosure controls?

### Model risk

- Проверены ли payoff formulas независимо по подписанным term sheets?
- Полны ли autocall, memory coupon, observation dates, corporate actions,
  dividends, currency и barrier-monitoring conventions?
- Сверяются ли model outputs с независимым pricing или dealer evidence?
- Сохраняются ли baseline, OOS, calibration, drift и ablation reports?
- Версионируются, утверждаются, воспроизводятся и откатываются ли model changes?

### Data и evidence

- Лицензирован ли каждый источник и разрешено ли его предполагаемое использование?
- Сохраняются ли timestamps, timezone, corporate actions, missingness и freshness?
- Разделены ли физически synthetic, replay, paper и realized records?
- Аутентифицируются и immutable ли timestamped dealer quotes?
- Можно ли воспроизвести исторический result по input snapshot и code version?

### Technology и security

- Хранятся ли secrets вне source control и ротируются ли они?
- Определены ли least-privilege access, authentication, logging и retention?
- Проверяются ли cloud и local fallbacks без тихого ослабления evidence gates?
- Контролируются ли dependencies, containers, CI, backups и disaster recovery?
- Одобрены ли внешние AI-провайдеры для данных, которые им передаются?

### Operations

- Есть ли owner у каждого production-readiness block?
- Проверены ли alerts, health checks, latency/cost budgets, incident procedures
  и rollback?
- Может ли система fail closed при отсутствии обязательных evidence?
- Записываются ли human approvals до production use?

## Разрешённые и запрещённые внешние формулировки

### Допустимые при наличии соответствующего evidence

> «Исследовательская платформа и система поддержки решений для анализа
> структурированных нот worst-of Phoenix».

> «Показывает прозрачные scenario, barrier, evidence, provenance и
> model-validation views для supervised human review».

> «Поддерживает paper-note и realized-outcome workflows; evidence status
> отображается явно».

### Запрещённые без отдельной проверки и approval

- «Гарантированная доходность», «безопасно», «без риска» или «autocall
  обязательно произойдёт»;
- «доказанная live win rate», если она основана только на replay, paper,
  synthetic или in-sample data;
- «инвестиция одобрена AI» или «продукт compliance-approved»;
- «независимая dealer price» без quote provenance и fit validation;
- утверждение, что ПО заменяет licensed advice, suitability review или legal/
  compliance approval.

## Шаблон заключения внешнего проверяющего

Внешний проверяющий должен выбрать один из статусов:

- **APPROVED FOR RESEARCH / SUPERVISED PILOT**
- **APPROVED WITH CONDITIONS**
- **BLOCKED — EVIDENCE OR CONTROL GAPS**
- **REJECTED FOR INTENDED USE**

В заключении нужно указать точные evidence artifacts, code/release version,
data snapshot, нерешённые assumptions, ответственного и срок remediation.
Заключение проверяющего нельзя выводить только из AI vote.
