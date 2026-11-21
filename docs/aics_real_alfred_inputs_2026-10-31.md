# Real ALFRED source values for AICS (unscored; 2026-10-31 vintage)

Extracted directly from actual GitHub Actions artifact **14432003774**, run https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44313687138, with CSV SHA256 verified against artifact manifest. Each figure is the most recent observation *contained in the 2026-10-31 as-of snapshot*, not a real-time November 18 market quote.

| Series | Observation date | Observed value | Units | Candidate AICS node |
|---|---|---:|---|---|
| DGS30 | 2026-10-29 | 5.32 | percent | UST 30Y |
| SOFR | 2026-10-29 | 3.94 | percent | Repo |
| BAMLH0A0HYM2 | 2026-10-30 | 3.44 | percentage points OAS | Private Credit proxy only (not private-credit-specific) |
| BAMLH0A3HYC | 2026-10-30 | 13.27 | percentage points OAS | Private Credit proxy only (not private-credit-specific) |

The candidate node mapping is an *analyst hypothesis*, not a validated transformation to node scores. In particular, high-yield spreads cannot be treated as direct private credit measurements, and SOFR alone is not a complete repo stress score. The 24-month snapshot history for each of four source series is preserved in the original artifact; extracted monthly latest-observation rows are separate and do not replace full vintage files.

**11-node state:** no independently verified 0–100 node scores yet. No zero-filling, fabricated normalization, or look-ahead. AICS N/A; model score N/A; promotion BLOCKED; no trades.
