# AICS — third ten-stage increment (2026-11-18)

This is a code-delivery checklist, **not** a declaration that historical evidence is verified.

1. Check duplicate source identifiers in evidence manifests.
2. Detect repeated observation keys (series, date, realtime interval).
3. Check observation date and real-time interval ordering.
4. Reconcile SEC eligible-filing counts with their manifest.
5. Reject repeated SEC accession numbers in the eligible filing lists.
6. Reconcile XBRL fact counts with per-company manifest totals.
7. Validate ten-digit SEC CIK formatting on companyfacts.
8. Emit an explicit research-readiness report with all blocking gates.
9. Require 24-month chronological OOS evidence and committee approval before promotion.
10. Extend offline safety CI to test that readiness remains blocked without those requirements.

## Limitations

- A green pull-request run performs syntax and offline tests, not real external data collection.
- A complete API download is not equivalent to verified historical PIT coverage.
- The FRED current-vintage series cannot be backfilled into historical PIT scoring.
- Research readiness currently intentionally reports `ready_for_production=false`.
- Production weights (11 nodes; total 1050), verdicts and trades remain unchanged.
- Only a fully evidenced, committee-reviewed future release may consider changing publication status.
