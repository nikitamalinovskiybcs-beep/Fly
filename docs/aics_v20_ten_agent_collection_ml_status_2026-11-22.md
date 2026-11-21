# AICS V20 — десять агентов первичных источников и ограниченное online ML

**Отчёт:** 22 ноября 2026 · **Состояние подтверждено:** GitHub Actions run [44953439316](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44953439316), завершён успешно; 11 unit tests passed. Более поздний commit `6ab66a5...` добавляет явный статус partial и 90-day artifacts — проверка этого последнего изменения отслеживается отдельно в Actions.

## Архитектура

- **10 тематических source-агентов:** Private Credit, Insurers, UST 30Y, Neoclouds, Hyperscalers, SPV, Repo, Power/Data Centers, Semiconductors Supply, AI Demand.
- **AI Equities** — отдельный прежний Nasdaq price/corporate-action receiver, не зачисляется одиннадцатым агентом этого раннера.
- Всего **20 уникальных оригинальных источников** для 10 агентов; CoreWeave и Nebius разделяют Neoclouds/SPV, поэтому **22 source assignments → 20 single-fetch queries**, без повторной загрузки одинаковых байтов в одном цикле.
- Каждый фактически полученный ответ записывается как raw bytes, с SHA-256 в namespaced артефакте, проверенным после записи. Секреты ключей не сохраняются в URI source manifest.
- Исходный `scripts.aics_ten_node_agents` — **только сборщик текущих raw sources и метаданных**, не парсер показателей source-to-node и не сертифицированный scored AICS.
- `scripts.aics_source_anomaly_ml` — простой обучаемый на предыдущих датах **robust median/MAD anomaly detector**. Он использует **64 существовавших research score events** из V17/V18, не встраивается в индексы и не предсказывает S&P 500.

## Подтверждённый первый успешный реальный цикл

| Категория | Реальный результат |
|---|---|
| Тесты нового контура | **11 пройдены** |
| Source agents, которые отчитались | **10/10** |
| Уникальные запросы | **20** |
| Raw sources captured and SHA-checked | **19/20** |
| SEC submissions original snapshots | **15/15**, **но это индексы filing metadata**, не разобранные таблицы финансовых показателей |
| Данные других издателей | **4/5**: ALFRED DGS30, ALFRED IORB, NY Fed SOFR, Fed G.17; **EIA — без данных** |
| ML retrospective events | **64**, research alerts **0**; это не подтверждённая прогностическая точность |
| Новые independently verified 0-100 node scores | **0** |
| Полный сертифицированный 11-node AICS | **N/A** |
| 24-month independent OOS skill | **не проверен** |
| Trading actions | **не создавались** |

**Причина EIA 403:** первоначальный запрос `https://api.eia.gov/v2/` был без зарегистрированного EIA API key. [Официальная документация EIA](https://www.eia.gov/opendata/documentation.php) требует API key. Теперь collector использует **EIA-930 почасовые данные спроса энергосистемы** через `/v2/electricity/rto/region-data/data/`, а при отсутствии `EIA_API_KEY` сообщает `blocked_eia_api_key_missing`, не записывая ошибочную пустую запись и не эмулируя значения.

Для подключения EIA требуется *реальный* бесплатный API key, зарегистрированный по [EIA Open Data](https://www.eia.gov/opendata/). Добавить его **только как GitHub Actions secret с точным именем `EIA_API_KEY`**. Ключ не хранить в коде или пользовательских отчётах. Даже после подключения сетевой спрос — широкий grid proxy, **не прямое энергопотребление дата-центров AI**.

## Автоматизация и источник технической правды

Workflow [aics-ten-source-agents-ml.yml](../.github/workflows/aics-ten-source-agents-ml.yml) на **default branch** `devin/1779618014-quant-risk-framework` имеет `schedule: 45 22 * * 1-5` — GitHub cron **22:45 UTC понедельник–пятница** (GitHub Actions schedules могут задерживаться; в среде GitHub периодические задачи запускаются только для default branch). Also `push` / `workflow_dispatch` triggers.

Raw-копии и отчёты текущих ранов доступны как **Actions artifacts**, а не постоянное S3-хранилище; retention **90 days** в последнем workflow. Если нужна долговременная contemporaneous PIT-цепочка, необходимо отдельное внешнее append-only хранилище со своими ACL и lifecycle. Это **не** означает, что сегодняшнее скачивание доказывает байты из 2024 года.

**Технически ML ещё не обучается на новых исходных SEC-байтах:** его 64 события читаются из существующих V17/V18 score ledgers на каждом прогоне. Следующий обязательный этап — source-specific parsing `SEC 10-Q/8-K → SEC+filing date and XBRL facts → issuer-quarter metric → 10 node research event` и ingestion в новый source-eligible event journal; прогнозный ML с реальными outcome labels — только после chronological leakage-free walkforward и независимого OOS.

## Что должно изменяться в результате следующей итерации

1. **Проверить EIA_API_KEY**, собрать actual latest hourly grid records, если доступ авторизован.
2. **Автоматически искать новые SEC filings у 15 издателей** и считать число новых orig accession, не считать повторные / amended filings новыми independent release.
3. Восстанавливать **конкретные source-to-score показатели** из original issuer documents, со scope, units, effective period end, original public source proof и source SHA (не из одного лишь metadata snapshot).
4. Считать **source-freshness** по узлу и сохранять раздельные статусы captured/parsed/score-eligible/independently certified.
5. Выдать честный **ML supervised training readiness**: нужна зафиксированная временная модель, подтверждённые исторические constituents и финансовые outcomes, 24m walkforward/OOS; до этого только unsupervised anomaly diagnostics.

**Границы:** нет фабрикации, look-ahead, дат постфактум, обновления весов 1050, торговых сигналов или мнимого сертификата; Legacy SEC+14 остаётся отдельно от Research first-public-date proxy.
