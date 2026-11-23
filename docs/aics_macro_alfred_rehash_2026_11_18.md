# AICS macro research audit — four ALFRED snapshots sources (2026-11-18)

**Research-only evidence. No certified historical PIT, 0–100 node scores, investment signals, or AICS aggregate.**

## Original archive integrity

GitHub Actions [run 44313687138](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44313687138), artifact ID `14432003774` (expires **2026-12-18**). Downloaded original ZIP, SHA-256 `03d06b287dc591d6830223bd181db401d19ce618a785b40c25a999ab1ddd5cc3`. Independent local rehash of all four CSVs and re-count of unique as-of/observation keys yielded **96 complete month-end snapshot groups, 165,913 source rows** (DGS30 95,246; SOFR 45,655; ICE high-yield OAS 12,506; ICE CCC OAS 12,506). Source timestamps respect `realtime_start <= as_of <= realtime_end`, no observation date exceeds its snapshot as-of, and all `verified_pit` fields remain false.

These are genuine archived FRED/ALFRED API responses, **not separately authenticated historical provider release vintages**. Their historical availability and later corrections still require independent review, and no 24-month untouched predictive test has been demonstrated.

## Publicly describable non-scoring observations

Values are the last actual observation included in each archived month-end as-of snapshot, **not** values on the literal calendar month-end. Both series' reported unit is percent, and changes are percentage-point differences × 100 (basis points).

| Source series / AICS candidate node | As-of 2026-09-30 (actual observation date) | As-of 2026-10-31 (actual observation date) | Month-end as-of change |
|---|---|---|---:|
| DGS30 / UST 30Y | 5.59% (Sep 29) | 5.32% (Oct 29) | **−27 bp** |
| SOFR / Repo | 3.88% (Sep 29) | 3.94% (Oct 29) | **+6 bp** |

Official series metadata: [DGS30](https://fred.stlouisfed.org/series/DGS30), [SOFR](https://fred.stlouisfed.org/series/SOFR).

A 30-year Treasury yield change is not a calibrated UST stress score. A SOFR level or month-to-month change is **not** a repository of repo-market funding stress without validated relative-rate benchmarks, collateral composition and an audited mapping.

## ICE BofA series: license-aware research handling

The existing two series `BAMLH0A0HYM2` and `BAMLH0A3HYC` are publicly issued high-yield bond OAS **proxies**, not direct private-credit loan portfolios. Official FRED source notes restrict redistribution of ICE index observations and derived top-level data; this public-repository receipt intentionally includes **only file SHA-256, series codes, archival row counts and caveats**, not their observed numerical levels or derived changes. Refer to [FRED high yield](https://fred.stlouisfed.org/series/BAMLH0A0HYM2) and [FRED CCC OAS](https://fred.stlouisfed.org/series/BAMLH0A3HYC) for authorized access.

## Reproducibility and blocked promotion

- Versioned evidence receipt: `aics_data/research/alfred_macro_archive_rehash_2026_11_18.json`.
- Safeguard: `python -m unittest discover -s tests -p test_aics_validate_alfred_macro_rehash.py -v`.
- Display metadata-only gate: `python -m scripts.aics_validate_alfred_macro_rehash`.

The validator checks the recorded as-of chronology, source file SHA-256 references, arithmetic, series counts, licensing quarantine and no-score rules. **This metadata-only run is not an independent ZIP/source rehash**; that was performed separately on the downloaded original artifact. The project stays at **22/66 (33.3%)** milestones and **0/11 certified**. No progress milestone can be credited without an independently proven next gate.
