# AICS Priority100 — evidence-first 100-task dispatch

**Version:** 2026-11-22. **Branch:** `devin/1779618014-quant-risk-framework`.
**Implementation:** [priority workbench](../scripts/aics_priority100_workbench.py), [fail-closed tests](../tests/test_aics_priority100_workbench.py), integrated [daily source workflow](../.github/workflows/aics-ten-real-source-waves.yml).

## Why the allocation changed

100 formerly executed historical as-of roles are useful for checking dates, but **repeated deterministic replays are not evidence of forecasting skill**. The strongest missing component is independently traced original financial accounting numbers, not another arbitrary version count. This is an **additional** evidence-first workbench; it does not overwrite the original 100 PIT cutoffs or invent 100 separate trained AI workers.

| Priority | Unique executed verification units | Scope | Completion standard |
|---|---:|---|---|
| P0 | 36 | One original issuer source accession per task: exact referenced SEC document and original SGML index header; re-open gzip and SHA-256 independently | Document checksum + independently extracted exact original numeric facts, with unit, period and context |
| P0 | 19 | One original accounting research scoring cohort per task: PRU 9, three BDC 7, CoreWeave/Nebius 3 | All required original accounting items independently replayed and aggregate formula checked |
| P1 | 24 | One market month each, Nov 2024–Oct 2026, reconstructed panels and S&P500 retrospective context | Period-specific source availability, original vintage, no survivorship and preregistered scoring |
| P1 | 11 | One of the frozen 11 weighted model nodes | Hist. PIT + verified formula + 24-month independently untouched OOS |
| P2 | 10 | Negative checks: no missing accessions, correct month counts, no later S&P target in input, no auto-trades, no false 2000/2008 prediction claim | All controls remain fail-closed |
| **Total** | **100** | Different, identified work units | Count does not imply 100 validated independent model forecasts |

**Priority P0 depends on sources:** There are 36 distinct original filing accessions behind 19 event cohorts, not 36 independently audited accounting values. The earlier GitHub Actions run recovered 27 missing precise filing documents; 9 accessions appeared in a broader 100-filing archive. The *exact referenced document URL* is now an explicit separate gate: matching the SEC accession's header alone does not prove its sampled primary-document filename is the exact referenced report. An unknown or mismatched document remains blocked, not promoted.

## Exact automated deliverables

- The workflow produces `aics_data/agent_runs/ten_real_collection_rounds/aics_priority100_evidence_queue.json`, archived with raw source files and all other AICS receipts.
- 36 original-document tasks re-open source files and their headers, stream-decompress under a 48MB cap and verify SHA-256 against the original independently archived metadata. Missing archives, tampered bytes or incorrect exact referenced primary documents are flagged without making up data.
- 19 financial cohort tasks carry upstream issuer/accession dependencies; a cohort cannot pass merely because its dates or source URLs match.
- 24 market-month tasks verify unchanged 1050 weight, source coverage/missing-node partition, true per-month cutoff alignment and explicitly **partial** scores.
- 11 frozen-node tasks check unchanged original weights and no false certification.
- 10 independent protection checks block fake forecast/OOS claims, wrong lead/lag framing, changing monthly reconstruction method and trading promotion.
- Unit tests include tampered gzip payload, duplicate accession, fabricated independent OOS and corrupted monthly coverage weights.

## Current truth and deliberate stops

The **research-release technical acceptance** is 66/66 under an explicitly simplified sixth criterion. The **original independent project audit** remains 22/66, with **0/11 independently PIT-certified nodes**. A research AICS snapshot of 669.09 is not a certified signal.

The prior 24-month candidate comparison has 23 **ex-post** next-month S&P500 pairs and Pearson correlation **−0.135**, a weak descriptive association. No independent predictive lead time for crises in 2000 or 2008 has been established. **No** profit score, investable AICS/S&P spread, crisis probability, automatic orders or live model promotion.

SEC public filing-day is the active *PIT100 research proxy*, not an independently attested intraday first-public receipt. No synthetic historical fill or hidden +14 delay is introduced.

## Evidence sequencing for the next execution

1. Rehash the exact 36 original documents and headers. Identify base-sample accessions whose original referenced report **filename** differs from that sampled filing, and treat these as unresolved documents.
2. Independently parse original accounting values for 9 PRU observations, 7 × 3 BDC issuer-quarter values and 3 × 2 Neocloud issuer-quarter values; keep quarters and disclosure units separate and do not double-count financing, lease, guarantee or facility ceilings.
3. Only when original numeric and historical public-delivery proofs exist, reconcile source-to-score maps for all 11 nodes and reserve a truly untouched OOS window.
4. Apply the resulting frozen signal *without backfilling*, separately against S&P next-month returns, QQQ drawdowns and historical 2000/2008 pre-onset evidence. Unresolved signals must remain null.

**Automation:** the existing GitHub scheduled workflow is configured for 23:15 UTC; source collection may fail and GitHub schedules may be delayed. Check each live GitHub Actions conclusion. The full CI has an unrelated broad Ruff lint failure; do not report everything as green. A push-triggered pipeline must complete successfully before claiming this new 100-task report was generated.

**No new count is added to 22/66** merely because the 100 tasks are scheduled, iterated or have correctly documented missing evidence.

## Follow-up: PRU nine-quarter original numeric replay

After the initial Priority100 run failed on an input-schema mistake (the reconciled monthly `market_source_nodes_research_only` was an **integer count**, not a node-name array), the monthly test contract was corrected: exact known-node names are recovered from the complement of the missing-node roster, the integer count and the original fixed weight sum are independently checked. Three negative tests were added, including duplicate/mismatched node counts. The failed run was [45018254075](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/45018254075). A later run must be checked before asserting its success.

A second new, execution-scoped workbench [`aics_pru_original_9_numeric_replay.py`](../scripts/aics_pru_original_9_numeric_replay.py) independently reopens each exact original Prudential SEC filing from the verified Priority100 archive; it detects the narrow period-matched narrative disclosure **loans on non-accrual without related ACL** and the specific table row **total commercial mortgage and other loans, net**, then recalculates `100 × numerator / denominator` to 0.01 precision. Ambiguous tables, absent phrases, mismatched periods or tampered original bytes are blocked. It compares its freshly extracted numbers to the nine issuer research events, without falling back to their retrospectively documented numbers when original text cannot be parsed.

The output `aics_pru_nine_original_source_numeric_replay.json` reports the observed number actually matched **out of nine**, and explicitly retains `certified_AICS_nodes=0`, first delivery unattested, and no investment trading. Unit tests use synthetic HTML **only to validate parser behavior**, not to populate live historical financial observations. Do not assume 9/9 real issuer sources pass until the final GitHub Actions run is verified. PRU covers one issuer's scoped research ratio; it is not a verified industry-wide Insurers stress proxy.

The original [2026Q3 Prudential SEC 10-Q](https://www.sec.gov/Archives/edgar/data/1137774/000113777426000221/pru-20260930.htm) provides a manually independently checked **$610m** no-related-ACL nonaccrual narrative and **$58,685m** narrow net loans portfolio row, consistent with **1.04%** to two decimals. This standalone factual check does **not** prove the automated replay will pass every issuer quarter, or that the percentage has predictive power.

## Manual SEC triage of three distinct PRU original periods

Direct reading of each period's **own original SEC report**, not copied values from a later issuer filing:

| Period | Original SEC HTML | Non-accrual without related ACL ($m) | Narrow total commercial mortgage and other loans, net ($m) | Original-only research ratio |
|---|---|---:|---:|---:|
| 2024 Q3 | [filed 2024-10-31](https://www.sec.gov/Archives/edgar/data/1137774/000113777424000247/pru-20240930.htm) | 138 | 53,500 | 0.26% |
| 2024 Q4 | [filed 2025-02-13](https://www.sec.gov/Archives/edgar/data/1137774/000113777425000044/pru-20241231.htm) | 207 | 53,987 | 0.38% |
| 2026 Q3 | [filed 2026-11-04](https://www.sec.gov/Archives/edgar/data/1137774/000113777426000221/pru-20260930.htm) | 610 | 58,685 | 1.04% |

Figures are from the footnote narrative and narrow commercial mortgage/other loans portfolio table. The corresponding broader reported loan totals (e.g. consolidated carrying values) are **not** interchangeable denominators. Even when all three numbers are manually reconciled, they describe one insurance issuer's credit portfolio rather than AI-specific financing and do not upgrade the Insurers node to a certified market stress indicator. The nine-filing machine replay independently reopens original archive bytes before comparing against research-ledger numbers; its actual completed count depends on the result of the GitHub Actions execution.

## Full original-Prudential nine-quarter manual SEC primary-document verification

On 22 November, individually opened each period's own first-party EDGAR original, checked the **non-accrual-without-related-ACL** statement in issuer accounting note, verified the **narrow net portfolio investment-mix row** (not consolidated larger balance), and independently recomputed to half-up two decimals. These are manual source-to-numeric comparisons, not the still-pending automated raw-gzip SHA replay, and not historical data-feed PIT certification.

| Original period | SEC direct source | Nonaccrual no-ACL ($m) | Narrow portfolio net ($m) | Manual recomputed ratio |
|---|---|---:|---:|---:|
| 2024 Q3 | [original 10-Q](https://www.sec.gov/Archives/edgar/data/1137774/000113777424000247/pru-20240930.htm) | 138 | 53,500 | 0.26% |
| 2024 Q4 | [original 10-K](https://www.sec.gov/Archives/edgar/data/1137774/000113777425000044/pru-20241231.htm) | 207 | 53,987 | 0.38% |
| 2025 Q1 | [original 10-Q](https://www.sec.gov/Archives/edgar/data/1137774/000113777425000060/pru-20250331.htm) | 274 | 54,169 | 0.51% |
| 2025 Q2 | [original 10-Q](https://www.sec.gov/Archives/edgar/data/1137774/000113777425000108/pru-20250630.htm) | 423 | 54,612 | 0.77% |
| 2025 Q3 | [original 10-Q](https://www.sec.gov/Archives/edgar/data/1137774/000113777425000178/pru-20250930.htm) | 415 | 55,829 | 0.74% |
| 2025 Q4 | [original 10-K](https://www.sec.gov/Archives/edgar/data/1137774/000113777426000048/pru-20251231.htm) | 442 | 56,195 | 0.79% |
| 2026 Q1 | [original 10-Q](https://www.sec.gov/Archives/edgar/data/1137774/000113777426000095/pru-20260331.htm) | 250 | 56,436 | 0.44% |
| 2026 Q2 | [original 10-Q](https://www.sec.gov/Archives/edgar/data/1137774/000113777426000176/pru-20260630.htm) | 757 | 57,458 | 1.32% |
| 2026 Q3 | [original 10-Q](https://www.sec.gov/Archives/edgar/data/1137774/000113777426000221/pru-20260930.htm) | 610 | 58,685 | 1.04% |

All nine manual original-statement ratios equal the research-ledger values at displayed precision. **Do not** mark independent historical source ingestion time, 24-month OOS, issuer representativeness, AI-linked loss attribution or a certified Insurers 0-100 stress node as passed. Machine-extraction status is reported independently by the new nine-document replay run.

## Priority100 follow-up: 33/36 source-byte status and ARCC seven-quarter source parsing

The complete [successful original Priority100 GitHub Actions run 45018937898](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/45018937898) executed **100/100** evidence-verification tasks. Its artifact recorded **33/36** exact primary-document+header SHA rehashes, **0 independently recalculated underlying accounting source metrics**, **0 certified PIT nodes**, and **no full index**. Those three exclusions were exclusively Prudential original SEC documents for **2026-Q1/Q2/Q3** with the **same (CIK, accession, filename)** but an `investor.prudential.com` mirror URL instead of the equivalent `www.sec.gov/Archives/edgar/data` URL. The SHA-verified raw bytes were already archived through the SEC original archive. The earlier full-URL string equality was an overly restrictive source-identity test, not evidence of three absent filings.

A reviewed [canonical source identity function](../scripts/aics_pit100_original_scoring_accession_lineage.py) now accepts only a strict original SEC CIK/accession/filename path or Prudential's specifically allowed IR original URL with identical accession and filename. It does not accept arbitrary host aliases, wrong filenames, cross-issuer CIKs or changed accessions. The separate literal URL-equality field is preserved; canonical identity does **not** prove that a provider historically delivered the bytes.

The [original PRU raw numeric CI run 45019183473](https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/45019183473) passed with **6/9** fully SHA-rechecked, source-parsed numeric ratios and **3/9** blocked by the same outdated literal-URL policy before normalization. The next new CI run must be inspected before claiming 9/9 original byte replay.

New automated [seven-quarter ARCC source replay](../scripts/aics_arcc_seven_original_nonaccrual_replay.py) and [negative tests](../tests/test_aics_arcc_seven_original_nonaccrual_replay.py) inspect the **original SEC primary filing**, extract unique current-period non-accrual percentages for **amortized cost and fair value separately**, and compare against the original ledger. Independently inspecting the previously archived original bytes gave these descriptive values (not certified PIT):

| ARCC source quarter | Cost non-accrual % | Fair-value non-accrual % |
|---|---:|---:|
| 2024 Q3 | 1.3 | 0.6 |
| 2024 Q4 | 1.7 | 1.0 |
| 2025 Q1 | 1.5 | 0.9 |
| 2025 Q2 | 2.0 | 1.2 |
| 2025 Q3 | 1.8 | 1.0 |
| 2025 Q4 | 1.8 | 1.2 |
| 2026 Q1 | 2.1 | 1.2 |

These observed numbers match the existing retrospective source ledger and were found in the relevant exact original 10-Q/10-K/earnings exhibits; acceptance/filer filing date, first publication, issuer loan performance and full market predictive skill remain different evidentiary layers. Automated 7/7 source SHA/numeric replay is **not yet claimed until its workflow concludes**. BXSL/OBDC other 14 reports and six neocloud reports require their own exact source numeric controls.

**Strict readiness remains 22/66 and independently 0/11 nodes.** An additional test or verified issuer row is not an automatic audit milestone.
