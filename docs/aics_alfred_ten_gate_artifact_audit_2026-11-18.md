# AICS ten-gate independent artifact audit

Verified against actual GitHub Actions artifact 14432003774 (run 44313687138), downloaded 2026-11-18.

- 4 ALFRED series, 96 month-end as-of snapshots, 165,913 CSV rows.
- Independently checked: SHA256 vs manifest, 24 month-ends, manifest counts, unique observations, chronology, realtime windows, source flags, numeric/missing values, quality-report errors, and fail-closed promotion flags.
- All ten structural gates passed on all four series. Missing value markers: 0.
- Latest 2026-10-31 vintage: DGS30 4,209 observations (last 2026-10-29); SOFR 2,142 (last 2026-10-29); BAMLH0A0HYM2 773 (last 2026-10-30); BAMLH0A3HYC 773 (last 2026-10-30).

**Interpretation:** These checks authenticate the artifact against its own manifest, not independently against the ALFRED source. Snapshot freshness is observation-date lag, not publication-date proof. SEC filed_at +14 days and all 11 node coverage remain unverified. PIT promotion BLOCKED; AICS and model score N/A; no trades.

Artifact run: https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44313687138
