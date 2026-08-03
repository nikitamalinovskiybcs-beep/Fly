# Phoenix / Fly — External Project and Compliance Overview

## Document status

**Purpose:** pre-purchase review material for an independent compliance,
operational-risk, model-risk, and investment-committee assessment.

**Classification:** research and decision-support software. This document is
not a prospectus, legal opinion, suitability assessment, investment advice, or
guarantee of investment performance.

**Current commercial classification:** diagnostic software only while the
production evidence gate is blocked. A live-product or proven-win-rate claim is
not permitted by the current evidence state.

## Executive description

Phoenix / Fly is a Python and Streamlit research platform for analysing
worst-of Phoenix structured notes. It brings market-data ingestion, payoff and
barrier analysis, basket comparison, stress testing, calibration research,
paper-note lifecycle tracking, provenance, storage, and audit controls into one
workflow.

The platform is intended to make structured-note analysis more explicit and
reproducible. It does not itself guarantee returns, replace a licensed
investment professional, validate a dealer quote automatically, or create live
trades.

## What the platform does

For a supplied basket and note specification, the workflow can:

1. collect market data through configured providers and label its source;
2. calculate Phoenix and worst-of risk measures, including P(KI), autocall
   research estimates, barrier scenarios, coupon and stress outputs;
3. compare baskets and structured-product candidates under stated parameters;
4. separate estimated, simulated, historical-replay, paper, and realized
   information;
5. expose model assumptions, evidence status, freshness, and decision blockers;
6. retain paper-note and outcome records for later realized evaluation;
7. run research-only calibration, self-learning, and AI-review proposals; and
8. preserve audit artifacts for committee review and reproducibility.

## Architecture and operating model

| Layer | Responsibility | Compliance relevance |
| --- | --- | --- |
| Data module | Provider abstraction, source labels, freshness and fallback handling | A reviewer can identify where an input came from and whether it is verified |
| Precompute/pipeline | Heavy calculations and feature assembly | UI rendering is separated from core calculations |
| Phoenix/payoff layer | Basket, barrier, coupon, autocall and stress logic | Terms and assumptions are explicit inputs rather than hidden UI state |
| Evidence gates | Data, outcome, quote, OOS and production checks | Missing evidence blocks or downgrades decision use |
| Calibration/OOS | Baselines, Brier, log-loss, ECE, walk-forward and fixed-24m anchors | Model promotion requires independent validation |
| Paper/outcome layer | Simulated, replay, paper and realized lifecycle states | Paper marks are not represented as realized performance |
| Storage | Local SQLite/DuckDB plus optional cloud/self-hosted integrations | Local fallback reduces dependency on one cloud provider |
| AI committee | Independent research reviews and dissent preservation | AI output is advisory and cannot change live weights, verdicts or trades |
| UI/audit | Decision map, evidence badges, blockers and audit reports | A reviewer can trace a displayed conclusion to its evidence status |

## Decision workflow

```text
terms and basket
    -> market data and provenance
    -> payoff / P(KI) / autocall / stress calculations
    -> evidence and freshness gates
    -> baseline and OOS checks
    -> quote-fit and outcome review
    -> GOOD / CAUTION / BAD or BLOCKED research output
    -> human review before any purchase decision
```

The final output is a decision-support signal, not an order, execution
instruction, suitability determination, or assurance that a note will autocall.

## Evidence and data policy

The system distinguishes:

- **Verified / realized:** externally supported outcome or quote with required
  fields and provenance;
- **Paper:** simulated lifecycle with tracked assumptions and marks;
- **Historical replay:** chronological replay of market history;
- **Simulated:** model-generated paths or stress scenarios;
- **Estimated:** provider estimate or fallback diagnostic;
- **Missing / blocked:** required evidence unavailable or stale.

Synthetic or generated rows are not settled-note evidence. The data-collector
agent validates externally sourced settled notes and does not create synthetic
settled records.

The platform must not present a replay, paper result, synthetic path, or
provider estimate as an independently realized market outcome.

## Quantitative methods

The research stack includes deterministic payoff/state-machine calculations,
worst-of barrier analysis, correlated simulation, stress scenarios, transparent
empirical/classical baselines, chronological replay, calibration metrics
(including Brier score, log-loss and ECE), and fixed 6/12/18/24-month anchor
checks. More advanced methods are research candidates and require evidence
before promotion.

The fixed-24m gate remains a principal safety control. A candidate is not
promoted to production merely because an in-sample or simulated result looks
strong.

## AI committee controls

Configured providers may review a bounded problem packet and return proposals,
objections, implementation options, and acceptance tests. Each review records
provider, model, status, assumptions, and dissent. Missing, skipped, timed-out,
or quota-limited providers are not treated as approval.

AI output is research input only. No AI response may:

- change production weights automatically;
- mutate live verdict logic;
- create or submit a trade;
- bypass fixed-24m/OOS gates;
- convert replay or synthetic data into realized evidence.

## Current readiness and known limitations

The current system is **not represented as production-ready for live product
selection**. The compliance reviewer should treat the following as
conditions precedent:

- confirmed independent fixed-24m OOS/paper evidence;
- sufficient realized-note sample and outcome quality;
- timestamped, provenance-verified dealer quotes and quote-fit;
- validated observation schedules and complete term sheets;
- independent model validation and human model-risk sign-off;
- security, access-control, retention, incident-response, and deployment review;
- legal, regulatory, suitability, conduct, and jurisdictional review;
- documented rollback, monitoring, and change-approval procedures.

The platform also has material model-risk limitations: market data can be
stale, incomplete, provider-dependent, or affected by corporate-action and
calendar conventions; worst-of tails and correlations are difficult to
estimate; historical replay may not represent future liquidity or dealer
pricing; small realized samples can create unstable calibration; and model
selection, basket universe, missing-data treatment, and fallback rules can
introduce bias. These limitations require disclosure, sensitivity analysis, and
independent model-risk review.

The AI committee review of this document was **REVISE / BLOCKED FOR LIVE USE**:
Mistral was rate-limited (`HTTP 429`), Ollama completed an advisory approval,
Groq requested clearer limitations and AI boundaries, and OpenRouter confirmed
that fixed-24m OOS evidence, realized-note quality, quote provenance, and
independent model validation remain conditions precedent. No AI vote is a legal,
regulatory, suitability, or compliance approval.

## Compliance and due-diligence checklist

### Product and conduct

- What legal entity owns and operates the software?
- Is the intended user an adviser, broker, issuer, research analyst, or investor?
- In which jurisdictions will it be used?
- Who makes the final purchase decision?
- Is any output communicated to a client as a recommendation or solicitation?
- Are suitability, appropriateness, conflicts, inducement, and disclosure controls
  documented?

### Model risk

- Are payoff formulas independently reviewed against signed term sheets?
- Are autocall, memory coupon, observation dates, corporate actions, dividends,
  currency, and barrier-monitoring conventions complete?
- Are model outputs reconciled to independent pricing or dealer evidence?
- Are baseline, OOS, calibration, drift, and ablation reports retained?
- Are model changes versioned, approved, reproducible, and rollback-capable?

### Data and evidence

- Is each source licensed and permitted for the intended use?
- Are timestamps, timezone, corporate actions, missingness, and freshness recorded?
- Are synthetic, replay, paper, and realized records physically distinguishable?
- Are dealer quotes independently authenticated and stored immutably?
- Can an auditor reproduce a historical result from its input snapshot and code
  version?

### Technology and security

- Are secrets kept outside source control and rotated?
- Are least-privilege access, authentication, logging, and retention defined?
- Are cloud and local fallbacks tested without silently weakening evidence gates?
- Are dependencies, containers, CI, backups, and disaster recovery controlled?
- Are external AI providers approved for the data they receive?

### Operations

- Is there an owner for each production-readiness block?
- Are alerts, health checks, latency/cost budgets, incident procedures, and
  rollback tested?
- Can the system fail closed when required evidence is missing?
- Are human approvals recorded before any production use?

## Permitted and prohibited external language

### Permitted, subject to evidence

> “Research and decision-support platform for worst-of Phoenix structured-note
> analysis.”

> “Provides transparent scenario, barrier, evidence, provenance, and
> model-validation views for supervised human review.”

> “Supports paper-note and realized-outcome workflows; evidence status is shown
> explicitly.”

### Prohibited without separately verified evidence and approvals

- “Guaranteed return,” “safe,” “risk-free,” or “will autocall”;
- “proven live win rate” based only on replay, paper, synthetic, or in-sample data;
- “AI-approved investment” or “compliance-approved product”;
- “independent dealer price” without quote provenance and fit validation;
- any claim that the software replaces licensed advice, suitability review, or
  legal/compliance approval.

## Reviewer conclusion template

An external reviewer should issue one of:

- **APPROVED FOR RESEARCH / SUPERVISED PILOT**
- **APPROVED WITH CONDITIONS**
- **BLOCKED — EVIDENCE OR CONTROL GAPS**
- **REJECTED FOR INTENDED USE**

The reviewer should cite the exact evidence artifacts, code/release version,
data snapshot, unresolved assumptions, owner, and remediation deadline. The
reviewer's conclusion must not be inferred from an AI vote alone.
