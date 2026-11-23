# AICS AI Equities — first real-price capture gate (research only)

Date established: 2026-11-18. **Evidence-stage progress: 2/6; independently certified: NO.**

The existing 11-node AICS source inventory identifies Nasdaq historical market
activity as the primary price discovery route. A separate source capture has
been implemented in `scripts/aics_collect_ai_equities_prices.py`. It
requests dated JSON from Nasdaq market activity and keeps the **exact
unaltered provider bytes**, receipt SHA-256 and actual UTC retrieval time.

The frozen *research candidates* are NVDA, MSFT, GOOGL, AMZN, META, ORCL, MU.
This is not a retrospectively proven membership history or official investable
basket. The actual source response may contain corporate-action restatements,
delayed quotes, or restricted licensed data. A current retrieval of a past date
**cannot establish the response as it existed on that past date**.

## Source-to-score gates still blocked

1. Prove official provider permissions to retain and redistribute raw history.
2. Independently recalculate raw artifact SHA-256 and preserve a dated receipt.
3. Obtain genuinely dated constituent-universe and split/dividend-event records
   and document adjustment logic without future corporate-action leakage.
4. Prove available-at timestamps for each historical observation and price
   correction; explicitly isolate retrospective restatements.
5. Hold out 24 genuine untouched months and independently review node mapping.

Current-page Nasdaq reference:
https://www.nasdaq.com/market-activity/stocks/nvda/historical

Official corporate actions reference:
https://indexes.nasdaq.com/docs/Corporate_Actions_and_Events_Manual_Equities.pdf

Workflow: `.github/workflows/aics-ai-equities-prices.yml`.
The workflow **fails when zero raw sources were retrieved**. It does not report
an empty/compile-only action as success. A successful archive is at best a
research **candidate** and cannot, without independent re-hashing and source
rights review, automatically promote AI Equities from 1/6 to 2/6.

No 0–100 node stress score, AICS aggregate, predictive skill, or trade is
generated. SEC fundamentals still require filed_at + 14 calendar days;
revisable FRED series still require genuine ALFRED vintages. The immutable
AICS node weight total remains 1050.

## Source archive verified on 2026-11-18

Official Nasdaq raw JSON downloaded for NVDA, MSFT, GOOGL, AMZN, META, ORCL and MU, 63 genuine daily bars each (2026-08-20 to 2026-11-17). Seven original JSON SHA-256s were independently rechecked; total 441 rows. GitHub Actions run [44387147503](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44387147503), artifact ID 14466941540, retains the original bytes until 2026-12-18. Pinned receipts are in `aics_data/progress/ai_equities_nasdaq_raw_archive_receipt_2026-11-18.json`.

This is **raw candidate archive gate 2/6** only: historical source vintages, contemporaneous corporate-action adjustments, actual historical basket membership, source licensing and long-term archival remain unverified. The original 0–100 score remains unavailable and cannot be estimated from the 441 current-capture rows alone.
