# Phoenix Infrastructure and Process Review v1

## Scope

This review covers the code delivery path, runtime packaging, data/storage
boundaries, observability, reproducibility, rollback, and safety controls. It
is separate from the quantitative model review.

## Current result

| Area | Status | Evidence |
| --- | --- | --- |
| Python syntax/imports | PASS | `compileall` and CI import smoke checks |
| Lint | PASS | Ruff on `app.py`, `src`, and `scripts` |
| Tests | PASS in isolated CI mode | 513 tests with cloud credentials blanked |
| Streamlit health | PASS by CI design | `/ _stcore/health` launch check |
| Deployment port | PASS | Docker/Fly both use port 8080 |
| Research-only automation | PASS | workflow has read-only contents permission and safety artifact |
| Rollback controls | PASS | autopilot snapshots, trial mode, and rollback thresholds exist |
| Data freshness/provenance | PASS | market snapshot gate and lineage helpers exist |
| Full production evidence gate | BLOCKED | current fixed-24m benchmark gate is false |
| Dependency reproducibility | ATTENTION | requirements use broad minimum versions |
| Runtime hardening | ATTENTION | container runs as root and has no explicit healthcheck |
| CI coverage | IMPROVED | Ruff and full pytest were added to the workflow |

## Committee result

Two providers completed an infrastructure review: Groq and OpenRouter. The
committee verdict is **REJECT for production promotion**, not a rejection of
the engineering work. Both providers agree that:

- the fixed-24m promotion gate remains blocked;
- dependency reproducibility and container hardening need work;
- production weights, verdict, and trades must remain unchanged.

The remaining configured providers were deferred, skipped, or unavailable; the
artifact preserves those statuses rather than treating them as votes.

## Changes made in this review

1. CI now runs Ruff and the full pytest suite before compile/import checks.
2. CI test execution blanks cloud credentials so storage-default tests are
   isolated from the runner environment.
3. The infrastructure findings are stored as a review artifact for committee
   voting and future rechecks.

## Committee review packet

The committee should vote on the following infrastructure proposals:

1. Pin or lock runtime dependencies and refresh them on a scheduled workflow.
2. Add a non-root Docker user and an explicit container healthcheck.
3. Publish one versioned health schema for data, cache, storage, and model gates.
4. Persist code version, data snapshot hash, and configuration hash per run.
5. Make deployment promotion require CI, health, and safety artifacts.
6. Add cache invalidation tests for stale or partial snapshots.
7. Add an artifact retention policy for reports and rollback snapshots.
8. Add a dependency vulnerability scan without allowing it to mutate code.
9. Add deployment smoke tests against the built image, not only local Streamlit.
10. Add a cost/latency budget for external data and committee providers.

## Promotion rule

Infrastructure improvements may be merged when their tests pass. They must not
change Phoenix production weights, verdict logic, or trade creation. Model
promotion remains blocked until fixed-24m OOS/paper and BCS Capital quote-fit
evidence pass.
