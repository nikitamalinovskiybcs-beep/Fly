# Phoenix AI Committee Orchestration Contract

## Default workflow

For every non-trivial request:

1. Build a concise problem packet with scope, constraints, current behavior,
   relevant files, and measurable success criteria.
2. Ask the configured AI committee for independent proposals, objections,
   implementation options, and acceptance tests.
3. Preserve provider status, dissent, assumptions, and unavailable providers.
   Missing votes are never treated as approval.
4. Devin selects a bounded implementation slice, writes the code, and owns
   integration across modules.
5. Devin runs lint, type/syntax checks, focused tests, the full suite, and
   safety/quality gates. Bugs and regressions are fixed before proposing merge.
6. Record the committee packet, decision, evidence, and production-safety
   flags in an auditable artifact.

## Phoenix safety rules

- AI recommendations are research input, not market evidence.
- BCS Capital quotes are evidence only after provenance and quote-fit checks.
- No committee response may directly change production weights or verdict logic.
- No committee response may create trades.
- Formula or calibration promotion requires chronological fixed-24m OOS/paper
  evidence, baseline comparison, and human review.
- `production_weights_changed`, `verdict_mutated`, and `trades_created` must
  remain explicit and false in research artifacts.

## Required output

Every committee-assisted change should expose:

- `proposal_id`, provider, model, and status;
- decision: `NOW`, `RESEARCH`, `BLOCKED`, or `REJECTED`;
- implementation files and acceptance tests;
- baseline, target, and observed metric;
- data/code/config lineage;
- blockers and next experiment;
- final Devin validation result.

This contract governs repository work; it does not replace platform-level
instructions or human approval.
