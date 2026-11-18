# AICS evidence pipeline — ten-stage research hardening (2026-11-18)

All stages are **research-only**. None authorizes a live AICS score, model score, production weight change, verdict change, or trade.

| Stage | Implemented control | Verification required |
|---|---|---|
| 1 | ALFRED DGS30 split into bounded vintage windows | Complete API download and historical PIT audit |
| 2 | Paginate all observation results using server count | Check counts, duplicate keys, coverage |
| 3 | Distinguish ALFRED vintages from FRED current-only snapshots | Obtain historical vintages from a defensible source for the other three series |
| 4 | SEC filing metadata retains CIK, form, filed_at, period_end, accession | Reconcile submissions with filing records |
| 5 | Apply SEC available_at = filed_at + 14 calendar days | Test against as-of cutoff |
| 6 | Ten deterministic evidence quality gates | Run on real complete artifact |
| 7 | SHA-256 fingerprints for collected evidence | Store and compare immutable workflow artifacts |
| 8 | SEC companyfacts extraction with taxonomy, tag, unit, accession and embargo | Run separate XBRL workflow and validate each fact |
| 9 | Rate-limit protection: serialize evidence collection, avoid PR re-downloads, bounded 429 retries | Check GitHub Actions and provider quotas |
| 10 | CI syntax checks, audit trail and fail-closed publication | Confirm full pipeline on default branch |

## Known blockers

- FRED current-only snapshots are not point-in-time historical vintages.
- SEC companyfacts are collected with filing embargo but remain `verified_pit=false` until independently audited.
- The 11 production node weights remain fixed at a total of 1050.
- No real AICS score until all required node coverage and provenance checks are complete.
- No model promotion without fixed 24-month chronological out-of-sample/paper evidence and human review.
- A GitHub PR passing syntax checks is not proof that scheduled production collection succeeded.
- Agent research PR #52 is separate and unmerged; no claim of autonomous ML training.
