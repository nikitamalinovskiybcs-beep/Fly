# Independently rerun original 2026-11-30 AICS source package reconciliation

Date: 2026-11-18. Original archive: `aics_data_pit_package.zip`. Code: `AICS_stage10_committee.zip/reconcile.py`.

Executed:
```sh
python reconcile.py --source ../aics_data_pit_package.zip --as-of 2026-11-30 --out rerun.json
python -m pytest -q test_reconcile.py
```

**Observed output**: `covered_weight=250`, `total_weight=1050`, `weighted_coverage_pct=23.81`, `eligible_rows=6`, `publishable=false`; **3 tests passed**. The reconciliation output records source SHA256 `86565a7c09d44b0199ab396318bd7cae4747a2e94deea188873712cd07f2715b`.

Only `private_credit` (5 observations, weight 150) and `neoclouds` (1 observation, weight 100) have *unverified proxy* observations. These are **not** certified 0–100 node scores. The other nine nodes have zero eligible rows in this original package. Three NVIDIA records are excluded as not available until 2026-12-01 under the project's SEC lag.

**Important scope:** this is a reproducibility check of a local source package and its existing reconciliation code, not external verification of the claimed SEC or FRED inputs. The four ALFRED series from the separate later historical collection are not eleven independently validated node scores and cannot be summed with these two proxy-node counts.

The source package cannot reproduce v4≈650.7 or v14≈646.3. `index_aics=null`, `predictive_model_score=null`, `publishable=false`; trading remains blocked.

**Next evidence request:** exact versioned 11-node input score vector, score normalization definitions, as-of dates, original source files and checksums for each claimed index value. Without these, numeric correctness is untestable.
