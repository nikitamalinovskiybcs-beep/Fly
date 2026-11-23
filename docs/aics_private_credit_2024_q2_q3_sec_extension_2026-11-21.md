# AICS V12 · Private Credit — архивный SEC-срез 2024 Q2→Q3

**Дата исследования:** 21 ноября 2026. **Ветка:** `devin/1779618014-quant-risk-framework`. **Состояние:** реальный исторический *source research*, а не сертифицированный PIT / не полный AICS. Вес Private Credit **150/1050**, множитель к исследовательской 24M-схеме не применяется.

## Что добавлено

В [реестр 6 SEC issuer-quarter observations](../aics_data/research/private_credit_2024_q2_q3_original_sec_directional_2026-11-21.json) внесены **ARCC, BXSL, OBDC** за **II и III кварталы 2024 года** с первоначальными SEC filing dates и обязательным **+14 calendar days**.

| Эмитент | Q2 2024: cost / fair non-accrual, % | Q3 2024: cost / fair, % | Δ cost / Δ fair, п.п. | Q3 SEC +14 eligibility |
|---|---:|---:|---:|---|
| ARCC | 1.5 / 0.7 | 1.3 / 0.6 | −0.2 / −0.1 | **2024-11-13** |
| BXSL | 0.3 / 0.2 | 0.2 / 0.1 | −0.1 / −0.1 | **2024-11-26** |
| OBDC | 3.1 / 1.4 | 2.1 / 0.7 | −1.0 / −0.7 | **2024-11-20** |

**Только с 26 ноября 2024** можно представить ретроспективное трехэмитентное сопоставление Q2→Q3, использующее SEC+14 для каждой исходной публикации. Направление по амортизированной стоимости: **0 из 3 эмитентов показали ухудшение**. Это даёт узкий диагностический показатель **0,00% доли ухудшившихся BDC**, но **НЕ балл стресс-узла Private Credit**, не доказательство отсутствия стресса у частного AI-кредитования и не сертифицированную торговую оценку. Не переносить это наблюдение на неопубликованные кварталы и месяцы автоматически.

## Первичные источники

- **ARCC**: исходный [2024 Q2 8-K EX-99.1](https://www.sec.gov/Archives/edgar/data/1287750/000128775024000037/arccq2-24exhibit991.htm) и [filing index 2024-07-30](https://www.sec.gov/Archives/edgar/data/1287750/0001287750-24-000037-index.htm); [2024 Q3 EX-99.1](https://www.sec.gov/Archives/edgar/data/1287750/000128775024000053/arccq3-2024exhibit991.htm) и [Q3 10-Q index 2024-10-30](https://www.sec.gov/Archives/edgar/data/1287750/0001287750-24-000054-index.htm).
- **BXSL**: исходный [2024 Q2 10-Q](https://www.sec.gov/Archives/edgar/data/1736035/000173603524000026/bxsl-20240630.htm), [filing index 2024-08-07](https://www.sec.gov/Archives/edgar/data/1736035/0001736035-24-000026-index.htm); [2024 Q3 10-Q](https://www.sec.gov/Archives/edgar/data/1736035/000173603524000035/bxsl-20240930.htm), [filing index 2024-11-12](https://www.sec.gov/Archives/edgar/data/1736035/0001736035-24-000035-index.htm). Показатель fair находится в соответствующей сноске к cost percentage.
- **OBDC**, CIK 1655888, не другой Blue Owl issuer: исходные [2024 Q2 10-Q](https://www.sec.gov/Archives/edgar/data/1655888/000165588824000019/obdc-20240630.htm) и [Q2 EX-99.1](https://www.sec.gov/Archives/edgar/data/1655888/000119312524195932/d875793dex991.htm), [Q2 10-Q index 2024-08-07](https://www.sec.gov/Archives/edgar/data/1655888/0001655888-24-000019-index.htm); [2024 Q3 10-Q](https://www.sec.gov/Archives/edgar/data/1655888/000165588824000023/obdc-20240930.htm) и [Q3 EX-99.1](https://www.sec.gov/Archives/edgar/data/1655888/000119312524252064/d854376dex991.htm), [Q3 index 2024-11-06](https://www.sec.gov/Archives/edgar/data/1655888/0001655888-24-000023-index.htm).

## Ограничения и точный следующий шаг

У **OBDC cost** — доля неплатящих *debt investments* по amortized cost; у **ARCC/BXSL** доли рассчитываются относительно *total investments*. Fair знаменатели также отличаются. **Абсолютные доли между компаниями не усреднять**, направление допустимо сравнивать только внутри одного эмитента и одного denominator. Увеличение числа отдельных issuer-observations не заменяет первичные архивные bytes, независимую историческую PIT-аттестацию, заранее зафиксированную методику и 24-месячный untouched OOS.

**Main 24M ledger без изменений**: weighted research coverage 32.04%, October 2026 partial 453.17 (10/11); full index 0/24, AICS–SPX spread 0/24, 22/66 audit steps, independent certification 0/11. Новые шесть SEC observations **не повышены** в основной score-series именно потому, что ещё нет независимо подтверждённого source-byte replay и непрерывного строго датированного квартального протокола. Никаких сделок.

**Продолжение:** получить Q4 2024, Q1–Q4 2025 ARCC/BXSL/OBDC из первоначальных SEC-релизов, закрепить индивидуальные сопоставимые знаменатели и quarterly release gaps, установить срок годности исследований (не переносить Q3 2024 в середину 2025), независимый SHA replay, а затем только ввести события в историческую 24M панель.
