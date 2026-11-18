# Nasdaq Trader prospective listing intake (AI Equities)

The official Nasdaq Trader symbol directory specification describes two changing source files: [nasdaqlisted.txt](https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt) and [otherlisted.txt](https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt). It reports a *File Creation Time* wall-clock footer (NasdaqTrader symbol directory definitions), not a signed or historically attested UTC publication time. Daily-list corporate-action entitlements remain separate.

AICS Master now downloads the **original full bytes** of each source, pins their SHA-256 and retrieval time in an ephemeral research artifact, and locally rehashes two originals while cross-checking seven declared AICS research tickers across both exchanges. The observation is prospective: visible in this **current retrieval**, not proof that a past basket, split, dividend, ticker identity, issuer guarantee or publication cutoff was historically known. A changing venue or missing symbol blocks the current audit for inspection; it is not silently backfilled.

Original directory file redistribution and long-term retention remain subject to source rights review. Repository stores the collector and unit tests, not public copies of licensed raw directories; GitHub Actions artifact retention is 30 days. Historical corporate actions and index membership **remain unaudited** and all 21 source-to-PIT action facets remain unfilled. Original SEC docs still require filed_at+14 calendar days, ALFRED vintage rules unchanged, all 11 weights sum to 1050.

This stage does **not** advance 22/66 project milestones, independent node certification 0/11, or produce a node score/index.
