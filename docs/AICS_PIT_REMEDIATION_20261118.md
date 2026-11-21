# AICS PIT remediation — 2026-11-18

## Finding

The previously green PR workflow was not a live evidence run: stages 5–10 were skipped by design. Therefore no production PIT coverage or live AICS score can be claimed from that run.

## Implemented historical evidence path

- `scripts/aics_collect_alfred_pit.py`: downloads **real** ALFRED as-of snapshots at 24 completed month-ends for each of DGS30, SOFR, BAMLH0A0HYM2 and BAMLH0A3HYC. A query fixes `realtime_start=realtime_end=as_of`, `observation_end=as_of`; the returned real-time interval must contain `as_of`. Pagination, source failures, retries and SHA256 are retained. No backfill from today's FRED.
- `scripts/aics_validate_alfred_pit.py`: independently checks snapshot count, as-of chronology, source hash, row counts, finite values, and unique observation keys.
- `.github/workflows/aics-alfred-pit.yml`: weekly scheduled or manual live download with artifact retention; PR runs compile only.
- `scripts/aics_research_readiness.py`: historical vintage completeness and structural checks are explicit blockers.
- Offline regression tests fail closed when historical vintages are missing.

## Expected limitations

Some credit/spread series may not expose historical ALFRED vintages. Those must remain `missing_historical_vintage` and must **never** be reconstructed using current FRED history. A completed API response does not establish a 24-month out-of-sample validation, independently approved node mapping, or committee approval.

## Result status

Historical PIT snapshot code: implemented, **live data not yet executed or independently validated**. AICS index N/A; predictive model N/A. This is a research artifact, not an investment signal.
