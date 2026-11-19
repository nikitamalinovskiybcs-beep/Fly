# Nasdaq Trader prospective listing intake (AI Equities)

The official Nasdaq Trader symbol directory specification describes two changing source files: [nasdaqlisted.txt](https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt) and [otherlisted.txt](https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt). It reports a *File Creation Time* wall-clock footer (NasdaqTrader symbol directory definitions), not a signed or historically attested UTC publication time. Daily-list corporate-action entitlements remain separate.

AICS Master now downloads the **original full bytes** of each source, pins their SHA-256 and retrieval time in an ephemeral research artifact, and locally rehashes two originals while cross-checking seven declared AICS research tickers across both exchanges. The observation is prospective: visible in this **current retrieval**, not proof that a past basket, split, dividend, ticker identity, issuer guarantee or publication cutoff was historically known. A changing venue or missing symbol blocks the current audit for inspection; it is not silently backfilled.

Original directory file redistribution and long-term retention remain subject to source rights review. Repository stores the collector and unit tests, not public copies of licensed raw directories; GitHub Actions artifact retention is 30 days. Historical corporate actions and index membership **remain unaudited** and all 21 source-to-PIT action facets remain unfilled. Original SEC docs still require filed_at+14 calendar days, ALFRED vintage rules unchanged, all 11 weights sum to 1050.

This stage does **not** advance 22/66 project milestones, independent node certification 0/11, or produce a node score/index.

## First actual official seven-security capture and independent bytes check — 19 November

[Real GitHub Actions run 44496860842](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44496860842) downloaded **both exact official Nasdaq Trader text directories** at **2026-11-19T09:29:24Z** and its verification independently rebuilt the seven-security identity mapping. The original raw ZIP artifact **14516045430** was subsequently downloaded outside GitHub Actions; ZIP integrity and both source SHA-256 values were checked independently in a separate working container.

| Official current source | Original bytes | Rows in directory | SHA-256 |
|---|---:|---:|---|
| `nasdaqlisted.txt` | 348,385 | 5,608 | `5cda84ca84660408ecfcda5af7e8f8e8c5a519e754f33ad5a96d17f86e708b83` |
| `otherlisted.txt` | 544,575 | 7,692 | `3cc52144bcd516be7dad8b668d91b84ff6b56751d5fdf78d74c6e08284d69234` |

All seven research symbols were explicitly observed: **NVDA, MSFT, GOOGL, AMZN, META and MU** in the first file, **ORCL** in the second. This is security-name and current-listing presence, not confirmation of the historic basket. Provider `File Creation Time` was **2026-11-19 03:02 local wall clock**, but venue timezone is not independently authenticated; it is deliberately **not** treated as 03:02 UTC. The [durable metadata and source hash receipt](../aics_data/research/ai_equities_2026_11_19_nasdaq_current_directory_rehash.json) pins ZIP SHA-256 `4df22b44e845a036801ad36702e86b90f0e6e7233533c4f80a5732850dae5a55` and source receipt limitations.

**No retroactive model expansion:** Current security identity is not historical symbol-change or delisting history, historical seven-member basket constituency, price-corporate-action adjustment, or independent original provider PIT. Source-rights review and long-term original-byte retention remain open. Historical PIT **0/11**, independently certified nodes **0/11**, project milestones **22/66**, `index_aics=null` remain unchanged.
