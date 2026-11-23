# Phoenix AI Committee Shortlist v1

This shortlist selects the highest-value, testable improvements from the 200-item
research catalog. It is tailored to BCS Capital as the sole dealer quote source.

## NOW: implement and measure

| Rank | Proposal | Why now | Acceptance gate |
| --- | --- | --- | --- |
| 1 | `phoenix-021` observation-date contract | Prevents payoff timing ambiguity | Contract tests cover all observation branches |
| 2 | `phoenix-030` payoff conservation and bounds | Catches impossible payouts before scoring | Bounds and conservation tests pass |
| 3 | `phoenix-009` raw/calibrated/empirical loss comparison | Makes the current probability gap visible | Report contains all three values and provenance |
| 4 | `phoenix-017` log-loss and ECE gates | Brier alone is insufficient for calibration | Metrics are emitted beside Brier |
| 5 | `phoenix-010` input contract promotion block | Stops invalid data from reaching the score | Out-of-contract inputs produce a visible block |
| 6 | `phoenix-061` source and `as_of` on observations | Required for auditability | Every market observation carries both fields |
| 7 | `phoenix-063` stale-price rejection | Avoids scoring on stale market data | Stale input yields a data-quality blocker |
| 8 | `phoenix-067` missing-symbol and partial-basket gate | Worst-of requires the complete basket | Partial baskets cannot receive a normal verdict |
| 9 | `phoenix-068` feature lineage | Explains every score component | Score output links components to source features |
| 10 | `phoenix-070` immutable snapshot hashes | Makes replay reproducible | Benchmark records snapshot and code hashes |
| 11 | `phoenix-059` BCS Capital quote-fit gate | Connects model output to the only dealer evidence | Quote-fit is visible and advisory until promotion |
| 12 | `phoenix-121` acceptance test per proposal | Prevents vague committee recommendations | Every candidate has a measurable test |
| 13 | `phoenix-122` baseline metric per proposal | Enables objective selection from 200 ideas | Candidate includes baseline and target |
| 14 | `phoenix-129` record failed experiments | Prevents repeating rejected ideas | Failed candidates remain in the audit artifact |
| 15 | `phoenix-160` drift status in the verdict UI | Keeps the live process operationally honest | Drift state is visible with a blocker reason |

## RESEARCH: do not promote yet

- `phoenix-001`, `phoenix-007`, `phoenix-011`–`phoenix-019`: formula and
  calibration changes require chronological OOS evidence.
- `phoenix-026`, `phoenix-041`–`phoenix-046`: barrier and dependence model
  alternatives require replay and regime validation.
- `phoenix-131`–`phoenix-150`: experiment and paper automation should run in
  isolated research artifacts before any production promotion.
- `phoenix-151`–`phoenix-159`: drift-triggered recalibration must remain
  recommendation-only until false-positive rates are measured.

## BLOCKED

Any proposal that changes production weights, mutates the verdict directly,
creates trades, bypasses OOS/paper gates, or treats an AI vote as market
evidence is blocked by policy.

## Selection rule

The committee should re-vote only on this shortlist, using impact, falsifiability,
implementation cost, evidence quality, and safety. A proposal can move from
`NOW` to production only after tests, fixed-24m OOS/paper evidence, and BCS
Capital quote-fit evidence pass independently.
