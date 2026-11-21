# AICS CI v1.2.0 — integration decision and verified result

**Source:** user-supplied attachment `aics_ci_workflow_and_tests_v1_2_0.txt` (217 lines).
**Target:** `nikitamalinovskiybcs-beep/Fly`, branch `devin/1779618014-quant-risk-framework`.
**CI verification:** GitHub Actions [run 44400607220](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44400607220) — successful, **41/41 real unit tests** (9 scoring-gate + 7 minimal-model + 10 existing PIT + 10 adapted upload + 5 master runner).

## Implemented safely

| Supplied feature | AICS implementation | Decision |
|---|---|---|
| Master workflow schedule/dispatch | `.github/workflows/aics-master-run.yml`, Mon–Fri 06:00 UTC and dispatch | Adopted for **frozen-source audit only**, not evidence collection |
| `scripts/aics_master_pipeline.py` | Newly implemented script of this name | Fixed missing dependency; refuses non-`2026-11-18` cutoffs for the frozen evidence snapshot |
| ALFRED vintage isolation | `scripts/aics_pit_research_slice.py`, `tests/test_aics_pit_integrity_v1_2_0.py` | Adopted with strict `realtime_start <= as_of <= realtime_end`; research-only |
| SEC 14-day date gate | Same new code/tests plus canonical AICS engine | Adopted with `available_at = filed_at + 14 calendar days`; never accept earlier |
| Absent node means no AICS | Canonical `scripts/aics_index.py` + new unit tests | Adopted; index remains Python `None`/JSON `null`, rather than string `"N/A"` |
| `H=4\implies M=1.25` | Canonical `aics_index.calculate` unit test | Adopted for test arithmetic ONLY |
| Extra dependencies `numpy`, `pandas`, `requests`, `pytest` | Standard-library `unittest` and existing code | Avoided redundant installation for this job |
| Raw/processed data upload | Existing source collectors + source-specific Actions artifacts | Deliberately not claimed by master job; master archives research audit JSONs |
| Secrets `FRED_API_KEY`, `SEC_USER_AGENT`, `EIA_API_KEY` | Existing independent source pipelines | Not injected into a metadata-only audit; no simulated EIA ingestion |

## Not adopted as a certifiable stress score

The uploaded `compute_aics_at_date` averages within-series **12-point percentiles** and can produce an 11-node index if all series appear to have twelve numbers. This is unsafe as a production shortcut: the input fields do not establish *original provider release date*, redefinitions/revisions, licensing, issuer identity, independent source-to-score calibration or a genuinely untouched **24-month OOS**. In particular, `available_at` is a claim that must be verified; a valid date string is not proof. We did not overwrite the existing `tests/test_aics_pit_integrity.py`, and we did not feed synthetic test vectors into any stored financial timeseries.

The master runner **audits a frozen existing-receipt snapshot only**, rather than falsely re-labeling current public API responses as market vintages available on a past date. Dedicated FRED/ALFRED, SEC and NY Fed collection workflows remain separate. The weekday schedule reruns this guard for the frozen snapshot; it does **not** imply nightly data refresh or an independently validated PIT score.

## Certification / committee gate

- Model nodes: **11**, immutable total weight **1050**; no IPO-era denominator renormalization.
- Validated technical milestones: **22/66 = 33.3%**, not model forecast accuracy.
- Independently attested source PIT: **0/11**.
- Independently certified node scores: **0/11**.
- AICS numeric index: **null**; predictive skill: **null**; promotion **BLOCKED**; no trading.
- Run report: `docs/audit/aics_master_ci_report_2026-11-18.json`, stored as GitHub Actions artifact for 30 days, plus `docs/audit/aics_11_node_free_source_pit_2026-11-18.json`.
