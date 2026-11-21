# AICS V26 — восстановлен 2026 Q1, 7 кварталов оригинального SEC cashflow

**Дата исследования:** 22 ноября 2026. **Статус:** подтверждённые значения из первичных SEC filing exhibits; ретроспективная проверка опубликованных документов, **не** независимо аттестованный исторический PIT. Исходная рабочая задача — ранний buildout/funding-imbalance перед стрессом уровня 2000/2008, **не** новая вероятность обвала и не изменение фиксированных весов AICS (1050).

## Новое: исчезновение разрыва с Q4 2025 по Q3 2026

Четыре одни и те же компании: Microsoft, Amazon, Alphabet и Meta. Consolidated operating cashflow **минус** gross cash purchases/additions to PP&E. USD млрд. Не смешиваем gross cash PPE с поступлениями от продаж активов, кредитами, lease principal, чистым GAAP FCF по иной методике или AI-only инвестициями.

| Календарный квартал | OCF, $млрд | Cash PP&E, $млрд | OCF−PP&E, $млрд | Cash PP&E/OCF | Полный SEC+14 срез с |
|---|---:|---:|---:|---:|---|
| 2025 Q1 | 114.235 | 71.902 | +42.333 | 62.94% | 2025-05-16 |
| 2025 Q2 | 128.470 | 88.246 | +40.224 | 68.69% | 2025-08-15 |
| 2025 Q3 | 158.995 | 97.271 | +61.724 | 61.18% | 2025-11-13 |
| 2025 Q4 | 178.833 | 118.632 | +60.201 | 66.34% | 2026-02-19 |
| **2026 Q1 (NEW)** | **150.727** | **129.750** | **+20.977** | **86.08%** | **2026-05-13** |
| 2026 Q2 | 171.759 | 165.050 | +6.709 | 96.09% | 2026-08-14 |
| 2026 Q3 | 175.498 | 201.923 | **−26.425** | **115.06%** | **2026-11-13** |

*2026 Q1 SEC first-filed originals — all four reported 2026-04-29 and become eligible **2026-05-13** under SEC filed_at +14 calendar days:*

| Issuer | OCF $млн | Gross cash PP&E $млн | Gap $млн | Primary source | Primary accession |
|---|---:|---:|---:|---|---|
| Microsoft | 46,679 | 30,876 | +15,803 | [Original Q3 FY26 10-Q, direct three-month March 2026 cashflow](https://www.sec.gov/Archives/edgar/data/789019/000119312526191507/msft-20260331.htm) | 0001193125-26-191507 |
| Amazon | 26,032 | 44,203 | −18,171 | [Original Q1 2026 8-K earnings EX-99.1](https://www.sec.gov/Archives/edgar/data/1018724/000101872426000012/amzn-20260331xex991.htm) | 0001018724-26-000012 |
| Alphabet | 45,790 | 35,674 | +10,116 | [Original Q1 2026 8-K earnings EX-99.1](https://www.sec.gov/Archives/edgar/data/1652044/000165204426000043/googexhibit991q12026.htm) | 0001652044-26-000043 |
| Meta | 32,226 | 18,997 | +13,229 | [Original Q1 2026 8-K earnings EX-99.1](https://www.sec.gov/Archives/edgar/data/1326801/000162828026028364/meta-03312026xexhibit991.htm) | 0001628280-26-028364 |

Microsoft's **46,679 / 30,876** is from the **three months** ended March 31, 2026; the same 10-Q also carries **nine-month** figures **127,494 / 80,146**, which must never substitute for the calendar-quarter numbers. Amazon's gross 44,203 does **not** net 969 of equipment-sale/vendor-incentive receipts. Meta's 18,997 does **not** include separate finance-lease principal of 843. Alphabet's 45,790/35,674 are direct current-quarter columns, not TTM.

## What improved

From **2025 Q4 → 2026 Q1 → 2026 Q2 → 2026 Q3**, OCF-minus-gross-cash-PPE falls **+60.201 → +20.977 → +6.709 → −26.425** ($bn); Q4-to-Q3 change **−86.626bn**. Four distinct real quarter labels, with original first eligible dates preserved, rather than a fabricated monthly interpolation. This can be inspected *before* 2026 Q3 was public: the first measurable Q1 shift was SEC+14 available **May 13, 2026**, and the Q2 further deterioration available **August 14, 2026**.

Year-on-year 2025 Q3 → 2026 Q3 remains **−88.149bn**, and 3/4 issuers have negative cash gaps in Q3. Negative consolidated cash gap is **not** proof of new borrowings, GPU collateral deterioration, aggregate AI-only investment, a 2000/2008 probability, or market-price causation.

## Reproducible integration

- [2026 Q1 original issuer ledger](../aics_data/research/hyperscalers_2026_q1_original_sec_cashflow_2026-11-22.json)
- [Quarterly research calculator](../scripts/aics_early_imbalance_cashflow_shadow.py) now includes Q1 by default from CLI and accepts source-gated `q1=` input; legacy no-Q1 mode continues explicitly marking it missing
- [Negative and as-of tests](../tests/test_aics_early_imbalance_2026_q1.py) confirm four-source totals and **zero** Q1 data on 2026-05-12
- [30-agent research challenger](../scripts/aics_ten_model_improvement_agents.py) consumes the new Q1 records and [research orchestrator](../scripts/aics_thirty_agent_cycle.py) removes Q1 from open gaps **only after it is present in a complete four-issuer source-gated panel**
- [GitHub Actions workflow](../.github/workflows/aics-ten-real-source-waves.yml) replays the new Q1 tests and integrated improvement cycle, retaining research-only evidence artifact

**Integrity limitations:** source URLs and figures are verified against SEC filings, but raw first-published bytes have **not** been independently SHA-rehashed outside live Actions; issuer first-delivery historical provider receipts remain **unattested**. Prospective 24-month OOS skill, 2000/2008 numeric analog, market prediction, auto-reweighting, trading and approved full AICS remain **BLOCKED**.

**Next experiment:** original SEC source-specific extraction of quarterly figures from complete first-filed issuer documents into a prospective event journal; then historical AI Equities constituent/split vintage and SPV borrower→lender exposure mapping. Do not collapse source availability and independent certification into one metric.
