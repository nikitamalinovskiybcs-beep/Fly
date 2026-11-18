# AICS — second ten-stage engineering increment (2026-11-18)

**Research-only.** These are implementation milestones, not a claim of completed PIT coverage or a published index.

1. SEC XBRL: validate companyfacts per ticker.
2. Enforce `available_at = filed_at + 14 calendar days` on each fact.
3. Reject future availability and periods ending after filing.
4. Check taxonomy, tag, unit, accession, form and CIK lineage.
5. Reject nonfinite and duplicate fact records.
6. Generate SHA-256 file fingerprints and machine-readable XBRL quality report.
7. Audit the exact 11 fixed nodes and total production weight of 1050.
8. Explicitly distinguish candidate source mappings from independently validated node coverage.
9. Add offline fail-closed regression tests without invented financial series.
10. Wire validation, node audit, and safety tests into CI; serialize XBRL requests.

## Status and gates

- Existing PR evidence checks were green on commit `b227b07`, but pull-request CI does not fetch external data.
- XBRL collector and validator require a scheduled/manual run on the default branch for live verification.
- Candidate proxies are **not** approved mappings or verified node scores.
- FRED current-only historical snapshots remain unsuitable for historical PIT claims.
- All 11 validated node scores are unavailable; the index and model score remain null.
- Research automation PR #52 remains separate. Do not merge or promote without review.
- No model promotion without 24-month chronological out-of-sample/paper evidence and human approval.
- `production_weights_changed=false`, `verdict_mutated=false`, `trades_created=false`.

## Acceptance criteria for next increment

1. All new GitHub CI safety tests pass.
2. A non-PR evidence run produces complete manifests and passing quality reports.
3. XBRL collection runs with live SEC responses and passes the independent validator.
4. A coverage report lists 11 nodes, 1050 total weight and zero fabricated scores.
5. The investment committee can trace each input to a dated source and immutable hash.
