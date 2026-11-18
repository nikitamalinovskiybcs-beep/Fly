# AICS — ARCC non-accrual research monitor (18 Nov 2026)

**RESEARCH ONLY.** This is NOT the certified Private Credit node, NOT an AICS index, and NOT a trading signal.

Original primary publications identified from the issuer's investor relations website and SEC exhibit documents. Values in `arcc_primary_disclosures.csv` are manually transcribed research inputs, **not raw-source SHA256 authenticated**; the fields `raw_source_sha256` are blank intentionally. No independent provider re-download occurred in this environment.

| Period | Non-accrual / amortized cost | Non-accrual / fair value | SEC filing date | AICS availability (filed + 14 calendar days) |
|---|---:|---:|---|---|
| 2025-12-31 | 1.8% | 1.2% | 2026-02-04 | 2026-02-18 |
| 2026-03-31 | 2.1% | 1.2% | 2026-04-28 | 2026-05-12 |
| 2026-06-30 | 2.4% | 1.4% | 2026-07-29 | 2026-08-12 |
| 2026-09-30 | 2.4% | 1.4% | 2026-10-27 | 2026-11-10 |

At 18 Nov 2026, non-accrual on amortized cost is up **0.6 percentage points** (relative +33.33%) since 31 Dec 2025. Non-accrual at fair value is up 0.2 pp. These measures come from **one** BDC (ARCC), and cannot infer the wider industry or the AI-sector exposure.

Source links: per-row references in the CSV, each quarter from its own issuer/SEC document. The Q3 SEC exhibit is `https://www.sec.gov/Archives/edgar/data/1287750/000162828026067382/arccq3-2026exhibit991.htm` and issuer Q3 release is `https://arcc.ares.com/news/ares-capital-corporation-announces-september-30-2026-financial-results-and-declares-fourth-quarter-2026-dividend/0bf958ac-18eb-4a60-9868-fa8914e548a8`.

Run with Python 3.10+ stdlib only:

```sh
python aics_arcc_nonaccrual_monitor.py arcc_primary_disclosures.csv --as-of 2026-11-18 --output arcc_nonaccrual_summary.json
python -m unittest discover -p 'test_aics_arcc_nonaccrual_monitor.py' -v
```

Eight local deterministic safety/unit tests passed, including no early 2026 Q3 availability, 14-day SEC lag, bad source, duplicate and false certification refusal. **No API calls or 24-month OOS backtest were run**.

Next: fetch original issuer/SEC HTML bytes with identified public sources and a genuine SEC User-Agent, save raw SHA256 and extraction offsets, cross-check 2nd BDC OBDC/MFIC quarterly disclosures, freeze metric direction and normalization, then seek independently checked node certification. 