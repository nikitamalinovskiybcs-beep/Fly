# AICS score claim 646.3 / 650.7: ten-step reproducibility protocol (2026-11-18)

The numbers 646.3 and 650.7 are **unverified claims**, not computed values from the four ALFRED series. The engineering maturity estimate 7/10 is subjective and must never be interpreted as forecast accuracy.

1. Freeze claim date, version, and raw 11-node score records; **not available**.
2. Preserve each original input's URI and SHA256; **missing for score claims**.
3. Verify source available_at against score date; **not done for 11 nodes**.
4. Enforce SEC available_at >= filed_at + 14 calendar days; **not verified for claims**.
5. Verify ALFRED source vintage independently; **four series structurally audited, not independently source-attested**.
6. Reproduce score normalization from prior-only training windows; **calibration missing**.
7. Recompute hot nodes (strictly >60), multiplier and fixed 1050 weights; **cannot without 11 scores**.
8. Compare independently reproduced AICS with 646.3/650.7 and log numerical differences; **pending**.
9. Run 24-month untouched out-of-sample validation against predeclared targets; **pending**.
10. Committee review and sign-off; **pending**.

Executable gate: `python scripts/aics_score_reproducibility_gate.py <11-node-evidence.json>` exits 2 and emits null index unless **all eleven** score records and source evidence satisfy checks. A passing calculation is a *reproducibility candidate*, not proof of predictive performance or authorization to trade.

**Known coverage:** original 2026-11-18 input package reported 2/11 PIT-date-admissible nodes (250/1050 weighted), but these proxy observations lacked independently verified vintages and calibrated 0–100 scores. The newer live ALFRED archive has 96 month-end snapshots for four **source series**, not four completed node scores; these counts are not additive.

**Status:** 646.3 and 650.7 unverified; certified AICS N/A; predictive model score N/A; promotion BLOCKED; no trades.
