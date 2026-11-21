# AICS research credit monitor — 2026-11-18

**RESEARCH ONLY — not the certified AICS index or a trading signal.** Calculations from historical ALFRED as-of snapshots in GitHub Actions [run 44313687138](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44313687138), archive ID 14432003774, **not independently source-authenticated**.

Original ZIP SHA256: `03d06b287dc591d6830223bd181db401d19ce618a785b40c25a999ab1ddd5cc3`. Per-series source CSV SHA256 hashes match the original coverage manifest. Four series, 24 completed monthly snapshots each, November 2024–October 2026; 165,913 raw archive observations in total. No look-ahead detected by the structural checks performed, but these do not constitute independent source verification.

| Historical as-of snapshots | Nov 2024 | Sep 2026 | Oct 2026 | MoM (percentage points) | YoY (percentage points) |
|---|---:|---:|---:|---:|---:|
| DGS30 (30-year UST yield) | 4.44% | 5.59% | 5.32% | -0.27 | +0.67 |
| SOFR | 4.57% | 3.88% | 3.94% | +0.06 | -0.10 |
| ICE BofA US High Yield OAS (BAMLH0A0HYM2) | 2.74 pp | 3.12 pp | 3.44 pp | +0.32 | +0.50 |
| ICE BofA CCC & Lower OAS (BAMLH0A3HYC) | 7.35 pp | 11.79 pp | 13.27 pp | +1.48 | +4.62 |

Additional descriptive measures from the **original monthly snapshots only**:
- July 2026 → October 2026: HY +0.59 pp; CCC & Lower +2.93 pp.
- Nov 2024 → Oct 2026: HY +0.70 pp; CCC & Lower +5.92 pp.
- CCC minus HY spread difference: 4.61 pp in Nov 2024, 9.83 pp in Oct 2026, difference +5.22 pp. The cohorts differ, so this is descriptive only.
- Both credit spreads widened MoM in September and October 2026 (credit widening breadth 2/2). This **is not** an AICS score or a hot-node count.

The accompanying reproducible local research bundle contains Python stdlib code that regenerates the 24-month panel **from the original artifact ZIP**, a CSV, JSON summary, chart, and tests. Local tests: 5 passed on 2026-11-18, including a tampered archive SHA256 rejection. These are arithmetic and structural reproducibility tests, **not** a predictive OOS test.

## Methodology safeguards
- Archive `realtime_start`/`realtime_end` matching the as-of query date represents an archive *snapshot date*, not necessarily the date a source originally published or revised each observation.
- The fetched ALFRED files have `independently_verified_pit=false`; no independent re-fetch from provider was performed here.
- ICE BofA credit spreads are not direct private-credit/AI exposure metrics; SOFR rate level is not a repo stress score.
- Four descriptive series cover only **three candidate mapping nodes**; **zero independently audited node stress scores**.
- **Certified AICS: N/A; predictive skill: N/A; no trading actions.**

Next gates: independently authenticate selected ALFRED as-of snapshots against source; complete independent 11-node metric definitions and PIT provenance; validate release timing and 24 untouched months of genuine predictive OOS.