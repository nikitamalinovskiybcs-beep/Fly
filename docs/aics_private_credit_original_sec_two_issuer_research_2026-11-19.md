# AICS Private Credit — ARCC + OBDC original SEC cross-issuer source audit

**Research date:** 2026-11-19. **Project branch:** `devin/1779618014-quant-risk-framework`. **Node:** Private Credit, immutable weight **150/1050**.

**Original-source verification outcome:** 2 BDC issuers, 8 issuer-reporting-period entries, 16 separate source-extracted non-accrual percentage values (8 amortized-cost and 8 fair-value). Research-only, **AICS N/A**.

## Successful reproducible primary-source execution

- [ARCC SEC corrected original Q4 2025 + Q1–Q3 2026 timeline](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44410609866), including the *prior 2024 comparative first visible in a Feb 2026 filing*; originals separately cross-verified. 5 period entries, 10 values. Full raw SEC-archive hashes and original CIK in `aics_data/research/arcc_q4_sec_corrected_nonaccrual_sources_2026-11-18.json`.
- [OBDC direct SEC original archive](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44415057328), 3 dated filing-index/EX-99.1 pairs; **6 source HTML bytes hashes independently rechecked**, 9 tests passed. Original archive SHA `3af6fc515102edefe4e533f431b87bc87c25b87d6565616ace3fcc2ca07141e8`, archive artifact `14478023804`. Permanent per-file SHA-256 receipt in `aics_data/research/obdc_original_nonaccrual_source_receipt_2026-11-19.json`.
- [ARCC+OBDC 16-value independent cross-issuer original SEC rehash and compare](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44415659119), **8/8 tests passed**; archived result artifact `14480125166`. Three original-source ZIP archives verified before producing any output.

## Real non-accrual disclosures by reporting period

**Percent of the respective issuer's investments**; cost and fair-value are *different denominators*.

| Period end | ARCC cost | ARCC fair value | OBDC cost | OBDC fair value |
|---|---:|---:|---:|---:|
| 2026-03-31 | 2.1% | 1.2% | 2.0% | 1.0% |
| 2026-06-30 | 2.4% | 1.4% | 2.8% | 0.8% |
| 2026-09-30 | 2.4% | 1.4% | 2.9% | 0.8% |

- Q3 ARCC − OBDC = **−0.5 percentage points at cost**, **+0.6 percentage points at fair value**. These are issuer-to-issuer comparisons, not aggregate credit stress.
- OBDC Q1→Q3: **+0.9 pp at cost**, **−0.2 pp at fair value**.
- ARCC Q1→Q3: **+0.3 pp at cost**, **+0.2 pp at fair value**.
- ARCC 2025-12-31 original Q4 2025 SEC 8-K was filed 2026-02-04; **SEC+14 makes it source-candidate available 2026-02-18**. The separately reported *2024-12-31 comparative* was first in that 2026 document and must **never** enter a 2024 backtest. This repaired earlier overly conservative or unproved issuer news-page availability assumptions.

## Verified SEC filing +14 gates for 2026 quarterly values

| Quarter | ARCC available_at | OBDC available_at |
|---|---|---|
| 2026 Q1 | 2026-05-12 | 2026-05-20 |
| 2026 Q2 | 2026-08-12 | 2026-08-19 |
| 2026 Q3 | 2026-11-10 | 2026-11-18 |

Cross-issuer comparison for a quarter cannot be historically visible before the later of the two dates. Never fill January–February with September's scores or revise past outcomes after they become known.

## Progress and scientific certification

**Engineering milestone ledger remains 22/66 (33.3%). Independently certified nodes 0/11, full AICS N/A.** This source expansion is substantive issuer breadth and real numeric verification, but by the project's declared six-stage rules it does not complete independent full-node historical PIT attestation, independent 24-month predictive OOS, or approved 0–100 stress calibration.

**Hard limitations:**

1. Two listed BDCs are not representative of the whole private-credit market or AI-infrastructure financing. Do not assign universe coverage or issuer weighting from these data.
2. SEC originals were downloaded after their historical dates and authenticated by filing, original HTML, SHA-256 and +14 days; they are **not** independent live contemporaneous feed archives. Record both factual filing date and separate archive retrieval date.
3. Cost percentage and fair-value percentage have different denominators. Do not combine them, and do not sum overlapping portfolio measurements or infer recoveries directly.
4. Only three *matched* 2026 quarters are shown. Do not fabricate 24 monthly observations, a score, hot-node status, credit predictive skill, or trades.
5. Actions ZIP artifacts expire; durable GitHub JSON receipts retain per-original SHA/provenance but are not substitutes for retained original source bytes. Plan legally permissible long-term raw-source retention.

**Next primary-source step:** add BXSL original SEC 2026 Q3 and earlier quarters with exact denominator definition and original filing date, then widen BDC coverage in a predeclared issuer universe. Consider KBDC/GBDC/OBDC/ARCC only after confirming each issuer's original filings and compatible definitions. Do not promote a node on the strength of a larger list alone.
