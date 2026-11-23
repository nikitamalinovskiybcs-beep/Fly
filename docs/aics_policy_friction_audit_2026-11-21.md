# AICS · аудит ограничений, замедляющих research-выпуск — 21.11.2026

**Объект:** GitHub branch `devin/1779618014-quant-risk-framework`; сверены основные policy и release-файлы в `docs/`, `scripts/`, `aics_data/progress/`. **Вывод: выявлено 7 категорий избыточных либо неправильно размещённых *research* ограничений**, не исчерпывающий подсчёт всех проверок кода. Нельзя трактовать все проверки как ненужные.

## 7 кандидатных изменений

| № | Сейчас | Почему мешает | Для исследовательской версии | Для сертификации и live |
|---|---|---|---|---|
| 1 | SEC `available_at = filed_at + 14 calendar days` (`docs/aics_completion_protocol.md`, `docs/aics_evidence_closure_gates_2026-11-18.md` и много collectors) | Нефактическая двухнедельная задержка | Использовать **первое доказуемое публичное timestamp dissemination / accepted_at**; для неизвестного времени — консервативно следующая сессия и флаг proxy; не использовать `period_end` | Проверить UTC↔ET, after-hours, trading calendar, filing revisions и публичную доступность; запустить параллельное сравнение с legacy +14 |
| 2 | Research и production readiness смешаны; `aics_research_readiness.py` принудительно выдаёт `ready_for_production=False`, `chronological_24m_oos_validated=False`; `aics_committee_readiness.py` присваивает внешним gates `False` | Изменения данных сами не меняют readiness даже при положительных фактах | Разделить `research_usable`, `PIT_evidence_quality`, `production_approved`; evidence-based, не просто bool | Не повышать сертификацию из user flags, без фактического доказательства или approval |
| 3 | Полный 11-узловой AICS `null` при отсутствующем одном узле (в 24m панелях) | Нельзя видеть предварительный смысл на 24 месяцах | Отдельно публиковать **partial observed points + 11-node coverage + mathematical bounds**, не представлять за полный индекс и не подставлять пропуски | Для полного сертифицированного AICS по-прежнему обязательны все 11 узлов |
| 4 | 24 месяца untouched OOS — условие итогового выпуска (`aics_evidence_closure_gates_...`) | Сертификационный критерий ошибочно воспринимается как блокировка любой research-кривой | Разрешить описательные исторические исследования, при этом score source mapping и обученные параметры пометить `exploratory/unvalidated` | Для статистического утверждения о предсказательной силе и сигналов сохранить независимый OOS, frozen transformations |
| 5 | Две шкалы 66/66: `docs/aics_project_delivery.md` — **66/66 technical release**, `aics_data/progress/status.json` — **22/66 independent audit** | Одинаковое `66` заставляет считать проверенные вычисления «не сделанными» либо считать аудит завершённым | Показывать раздельно `technical_release=66/66` и `independent_audit=22/66` с короткой легендой | Не переименовывать 66/66 technical в 66/66 certification; independent = 0/11 |
| 6 | Повторное извлечение и независимая SHA-256 сверка одного SEC source на нескольких node/gate pathways | Лишние retrievals и избыточная работа, особенно при expiry GitHub artifacts | Ввести единый content-addressed архив `source_id + SHA + first_publication + available_at`, reuse доказанного immutable receipt с node-specific scope проверкой | Нужны оригинальные bytes, SHA, корректность исходных чисел; оптимизация не отменяет audit |
| 7 | Общий Phoenix/Ruff lint статически может проваливаться из-за кода вне AICS | Репозиторный `CI red` не равен поломке проверенного AICS research | Отдельный status `aics-research-tests`, отдельный project-wide lint; решение о research публикации базировать на scoped tests | Общий CI не объявлять зелёным, пока он реально красный |

## Что оставляем без ослабления

1. **Нет фиктивных чисел**, synthetic backfill, look-ahead или нулей вместо пропусков.
2. **Сохранить 11 фиксированных весов, сумма 1050**, но research no-multiplier версия — отдельная формула; не переносить старые 450/500 thresholds без новой валидации.
3. **Метрическая семантика, уникальный issuer/legal entity и единицы**, избежание double-counting долгов, акций, гарантий, лизинга и SPV.
4. **Реальные источники и даты публикации**; современные SEC companyfacts не являются историческими снимками PIT; для ALFRED важен release vintage.
5. **Честные метки**: исследовательский индекс, условный сценарий, independently PIT attested, true untouched OOS, сертификация и торговый сигнал — разные вещи.

## Принцип перехода — две независимые линии

- **AICS Research**: реальные датированные первичные observations, раскрытые формулы, partial / shadow index с покрытием, чувствительностью и warnings, без авто-торговли.
- **AICS Certified**: независимый point-in-time source replay, pre-registered scoring, 24m untouched OOS, independent review, отдельное утверждение и только затем любые инвестиционные ограничения.

**Не менять массово логику `+14` на `filed_at` глобальным search/replace.** Для каждого source типа требуются собственные правила public dissemination and next-session eligibility; старую серию сохранить неизменной для дифференциального теста.

## Проверяемые основания

- `docs/aics_project_delivery.md`: research technical release 66/66; declared independent certification 0/11.
- `aics_data/progress/status.json`: independent audit 22/66 and `index_aics=null`.
- `scripts/aics_research_readiness.py`, `scripts/aics_committee_readiness.py`: hardcoded readiness gates.
- `docs/aics_completion_protocol.md`, `docs/aics_evidence_closure_gates_2026-11-18.md`: legacy +14, independent PIT/OOS requirements.
- [SEC EDGAR data access](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data): some after-hours submissions are disseminated the following day.
- [SEC PDS service](https://www.sec.gov/info/edgar/ednews/dissemin.htm): dissemination of public filings after EDGAR acceptance.

**Аудит политики выполнен; реализация смены дат и dashboard статусов требует отдельного code+data regeneration.** Этот документ не меняет действующий рынок и не утверждает, что data gates уже сняты.
