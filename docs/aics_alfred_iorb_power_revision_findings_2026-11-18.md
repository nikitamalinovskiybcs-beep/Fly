# AICS — IORB / WPU0543: original ALFRED vintage revision audit

**Frozen research cut-off:** 2026-11-18. **Nodes:** Repo (weight 100) and Power/Data Centers (weight 50).
**All monetary / index metrics below are research-only source observations, not verified 0–100 stress scores.**

## Original evidence and reproducibility

- 48 original ALFRED as-of JSON responses: 24 monthly-end snapshots of **IORB** and 24 of **WPU0543** (2024-11-30 to 2026-10-31). All originally fetched retrospectively on 2026-11-18.
- Independently SHA-256 rehashed the complete ZIP, its manifest and each underlying JSON.
- Exact source ZIP SHA-256: `8565519b21979e7d13475d954122fc651d65baa6025a0ef55b9b4b34f83ff627`.
- Audited original observation entries, **including multiple snapshots of the same observation**: **39,934**; not distinct market observations.
- Lossless ALFRED [48-original archive run](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44398846009), verified [revision audit run](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44401901826) (**7/7 unit tests passed**).
- Full per-change JSON report archived by revision audit, artifact ID `14473955626`. Permanent SHA/count receipt: `aics_data/research/alfred_iorb_power_vintage_revision_independent_receipt_2026_11_18.json`.
- All-11-node PIT gate and master pipeline now assert that receipt rather than silently using final revised history; subsequent master workflow passed **43/43 tests** (run `44402554978`), source gate run `44402564819` passed.

## Findings from original data

| Research metric | IORB | WPU0543 |
|---|---:|---:|
| Original monthly as-of snapshots | 24 | 24 |
| Pairs of adjacent as-of snapshots | 23 | 23 |
| Existing non-missing observation comparisons | 35,773 | 2,135 |
| **Changed existing observation values** | **0** | **69** |
| Unique past observation dates revised | 0 | **25** |
| New observation-date memberships | 700 | 23 |
| Latest as-of used | 2026-10-31 | 2026-10-31 |
| Latest observed economic date in that snapshot | 2026-10-31 | 2026-09-01 |
| Value on latest observed economic date | 3.9% | 344.639 index points |

The largest absolute adjacent-snapshot correction was to **WPU0543 June 2025**, from **326.930** in the 2025-07-31 as-of snapshot to **317.815** in the 2025-08-31 as-of snapshot, a change of **−9.115 PPI index points**. The 69 revisions are **events of changed values between snapshots**, not 69 distinct economic months.

## Audit interpretation and safety barriers

1. This identifies *retrospective ALFRED vintage differences*, and is strong evidence against taking today's final WPU0543 history for a historical backtest. **It does not independently authenticate original provider release timestamps or contemporaneous availability.**
2. A 2026-10-31 as-of record showing IORB on a weekend does **not** prove weekend publication. An observation date and an official publication time are different concepts.
3. WPU0543 is a *national industrial electric-power producer price index*, **not** a data-center contracted tariff, power delivery constraint or site-level fixed-price agreement.
4. Zero IORB changes across these 23 neighboring snapshots does **not** rule out changes in other windows, data revisions, or late source publication.
5. All source-to-score mappings, exact BLS release-calendar checks, release-aware sample construction, and untouched 24-month OOS validation remain **unverified**. Do not fill gaps using current FRED/BLS histories or newly generated synthetic rows.
6. SEC `available_at = filed_at + 14 calendar days`, fixed 11-node weights sum **1050** and prohibition of IPO-era renormalization remain unchanged.

## Project control

Current milestone gauge **22/66 = 33.3%**. Historical original-source PIT attestation **0/11**; independently certified nodes **0/11**; AICS `null`, skill `null`, no trades. **Do not award a third PIT milestone merely for a successful original SHA rehash or discovered revision.**

**Next substantive gate:** independently verify calendar-day *publication* evidence (especially BLS PPI release dates) and map initial/revised vintages to the earliest provable availability. Then calibrate documented, independently reviewed node score methods without leaking revisions or crossing a 24-month untouched OOS.
