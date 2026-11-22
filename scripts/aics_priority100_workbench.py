"""AICS Priority100: evidence-first dispatch for exactly 100 distinct audit work units.

36 exact SEC original accessions + 19 scoring cohorts + 24 reconstructed months
+ 11 weighted nodes + 10 prediction/governance controls = 100 actual checks.

These are deterministic evidence agents, NOT 100 trained LLMs. A source archive
passes a checksum gate but NEVER certifies an original accounting value, first
historical feed availability, forecast accuracy, or a production AICS signal.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS

ROOT = Path("aics_data/agent_runs/ten_real_collection_rounds")
CROSSWALK = ROOT / "aics_pit100_original_source_accession_to_node_lineage.json"
TARGETED = ROOT / "aics_pit100_targeted_missing_sec_original_score_docs.json"
REPORTS = ROOT / "aics_pit100_100_original_sec_reports_manifest.json"
HEADERS = ROOT / "aics_pit100_100_sec_sgml_header_clock_audit.json"
RECONCILED = ROOT / "aics_pit100_reconciled_24m_sp500_monthly.json"
LEAD = ROOT / "aics_pit100_24m_expost_leadlag_falsification.json"
STATUS = Path("aics_data/progress/status.json")
OUT = ROOT / "aics_priority100_evidence_queue.json"


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _key(entry):
    return (str(int(entry["CIK"])), entry["accession"])


def verify_gzip_original(path, expected_sha):
    """Rehash actual decompressed source bytes. Missing originals fail closed."""
    if not path or not expected_sha or len(expected_sha) != 64:
        return False
    p = Path(path)
    if p.suffix != ".gz" or not p.is_file():
        return False
    if p.stat().st_size > 100_000_000:
        raise ValueError("Source gzip archive exceeds safety cap")
    try:
        with gzip.open(p, "rb") as f:
            sha = hashlib.sha256()
            count = 0
            while chunk := f.read(1024 * 1024):
                count += len(chunk)
                if count > 48_000_000:
                    raise ValueError("Decompressed original SEC source too large")
                sha.update(chunk)
        return count >= 100 and sha.hexdigest() == expected_sha
    except (OSError, EOFError):
        return False


def build(crosswalk, targeted, reports, headers, reconciled, lead, status,
          *, verifier=verify_gzip_original):
    if (crosswalk.get("schema") != "aics-PIT100-original-scoring-accession-to-SEC-SGML-crosswalk-v1"
        or targeted.get("schema") != "aics-PIT100-targeted-original-scoring-accession-SGML-fill-v1"
        or reports.get("schema") != "aics-PIT100-distinct-original-SEC-primary-report-downloads-v1"
        or headers.get("schema") != "aics-PIT100-first-original-SEC-SGML-timezone-clocks-audit-v1"
        or reconciled.get("schema") != "aics-pit100-two-independent-24month-replays-reconciled-v1"
        or lead.get("schema") != "aics-PIT100-24m-EXPOST-fixed-first-month-cohort-leadlag-v1"
        or status.get("independently_certified_nodes") != 0
        or status.get("index_aics") is not None
        or sum(WEIGHTS.values()) != 1050):
        raise ValueError("Unverified AICS inputs or schema: cannot schedule priority tasks")
    claims = crosswalk["source_claims"]
    cohorts = crosswalk["source_cohorts"]
    months = reconciled["monthly_aligned_research_panel"]
    diagnostics = lead["monthly_diagnostics"]
    node_rows = status["node_progress"]
    if (len(claims) != 36 or len(cohorts) != 19 or len(months) != 24
        or len(diagnostics) != 24 or len(node_rows) != 11
        or len(reports["tasks"]) != 100 or len(headers["source_headers"]) != 100
        or crosswalk["research_underlying_original_filing_references"] != 36
        or targeted["original_research_filing_claims"] != 36
        or len({_key(x) for x in claims}) != 36
        or len({x["cohort_id"] for x in cohorts}) != 19
        or len({x["month"] for x in months}) != 24
        or {x["node"] for x in node_rows} != set(WEIGHTS)
        or [x["month"] for x in months] != [x["month"] for x in diagnostics]):
        raise ValueError("Missing or duplicated real tasks, nodes, sources, or months")

    base = {_key(x): x for x in reports["tasks"]}
    sgml = {_key(x): x for x in headers["source_headers"]}
    newly = {_key(x): x for x in targeted["targeted_source_results"]}
    if len(base) != 100 or len(sgml) != 100 or len(newly) != len(targeted["targeted_source_results"]):
        raise ValueError("SEC task or accession duplicate")
    if set(newly) != {_key(x) for x in claims
                         if not x["same_exact_CIK_accession_header_clock_verified"]}:
        raise ValueError("Targeted source receipts do not cover precisely missing accessions")

    tasks = []
    source_status = {}
    for row in sorted(claims, key=lambda x: (x["node"], x["cohort"], x["issuer"])):
        key = _key(row)
        in_sample = bool(row["same_exact_CIK_accession_header_clock_verified"])
        exact_doc = bool(row["same_exact_primary_document_url_matched_to_source"])
        if in_sample:
            doc = base.get(key)
            hdr = sgml.get(key)
            if doc is None or hdr is None:
                raise ValueError("Original accession claims matched but not in archive")
            # A matching accession alone does not mean matching original
            # document filename. Preserve this separate critical gate.
            doc_ok = (exact_doc and doc.get("success") is True
                      and verifier(doc.get("compressed_archive_path"), doc.get("raw_SHA256")))
            hdr_ok = (hdr.get("original_sec_acceptance_clock_verified_from_sgml") is True
                      and verifier(hdr.get("original_header_archive_gz_path"),
                                   hdr.get("original_sec_header_raw_SHA256")))
            archive_type = "original_100_document_sample"
        else:
            doc = newly.get(key)
            if doc is None:
                raise ValueError("Missing source-targeting receipt")
            doc_ok = (doc.get("success_exact_original_scoring_document_and_sgml") is True
                      and verifier(doc.get("original_doc_gzip_archived_path"),
                                   doc.get("original_doc_raw_sha256")))
            hdr_ok = (doc.get("success_exact_original_scoring_document_and_sgml") is True
                      and verifier(doc.get("original_header_gzip_archived_path"),
                                   doc.get("original_header_raw_sha256")))
            archive_type = "targeted_exact_original"
        original_verified = bool(doc_ok and hdr_ok)
        source_status[key] = original_verified
        tasks.append({
            "task_id": f"SEC-{len(tasks)+1:03d}", "priority": "P0",
            "workstream": "exact_SEC_source_bytes_and_numeric_replay",
            "source_node": row["node"], "cohort": row["cohort"],
            "issuer": row["issuer"], "CIK": key[0], "accession": key[1],
            "original_document_url": row["source_original_doc_url"],
            "archive_origin": archive_type,
            "exact_referenced_document_and_sgml_bytes_rehashed": original_verified,
            "original_accounting_metric_independently_recomputed": False,
            "historic_first_market_delivery_attested": False,
            "state": "BLOCKED_NUMERIC_REPLAY" if original_verified else "BLOCKED_ORIGINAL_SOURCE",
            "next_action": ("extract original accounting XBRL/footnote value with units, period and accession"
                            if original_verified else
                            "archive exact referenced original SEC document and SGML header; rehash both"),
        })

    for cohort in sorted(cohorts, key=lambda x: x["cohort_id"]):
        component = [x for x in claims if x["cohort"] == cohort["cohort_id"]]
        if len(component) != cohort["original_underlying_issuer_reports_needed"]:
            raise ValueError("Cohort issuer dependency count changed")
        all_hashed = all(source_status[_key(x)] for x in component)
        tasks.append({
            "task_id": f"COHORT-{len(tasks)-35:03d}", "priority": "P0",
            "workstream": "reproduce_19_original_accounting_source_event_scores",
            "cohort": cohort["cohort_id"], "source_node": cohort["source_node"],
            "dependencies": [f"{x['CIK']}:{x['accession']}" for x in component],
            "all_exact_original_bytes_verified": all_hashed,
            "numeric_source_to_score_proven": False,
            "state": "BLOCKED_ORIGINAL_NUMERIC_SCORE" if all_hashed else "BLOCKED_UPSTREAM_DOCUMENT",
            "next_action": ("independently replay accounting XBRL facts and published event formula"
                            if all_hashed else "complete upstream original source byte evidence"),
        })

    for row, diag in zip(months, diagnostics):
        # Reconciler's *_source_nodes_research_only fields are node COUNTS,
        # not iterable rosters. Recover exact node names from missing_nodes.
        # Verify the complement, count, and frozen weights independently.
        market_missing = row["market_missing_nodes"]
        calendar_missing = row["calendar_missing_nodes"]
        if (not isinstance(market_missing, list)
            or not isinstance(calendar_missing, list)
            or len(market_missing) != len(set(market_missing))
            or len(calendar_missing) != len(set(calendar_missing))
            or not set(market_missing).issubset(WEIGHTS)
            or not set(calendar_missing).issubset(WEIGHTS)):
            raise ValueError("Missing-node lists invalid or duplicate")
        market_nodes = set(WEIGHTS) - set(market_missing)
        calendar_nodes = set(WEIGHTS) - set(calendar_missing)
        if (row["full_11node_AICS"] is not None or row["AICS_SP500_spread"] is not None
            or row["market_cutoff_date"] != diag["market_cutoff_date"]
            or not 0 <= row["market_known_weight_research_only"] <= 1050
            or not 0 <= row["calendar_known_weight_research_only"] <= 1050
            or type(row["market_source_nodes_research_only"]) is not int
            or type(row["calendar_source_nodes_research_only"]) is not int
            or row["market_source_nodes_research_only"] != len(market_nodes)
            or row["calendar_source_nodes_research_only"] != len(calendar_nodes)
            or sum(WEIGHTS[n] for n in market_nodes) !=
               row["market_known_weight_research_only"]
            or sum(WEIGHTS[n] for n in calendar_nodes) !=
               row["calendar_known_weight_research_only"]):
            raise ValueError("Incomplete monthly evidence was incorrectly promoted or distorted")
        tasks.append({
            "task_id": f"MONTH-{len(tasks)-54:03d}", "priority": "P1",
            "workstream": "24_month_PIT_coverage_and_SP500_falsification",
            "month": row["month"], "market_cutoff": row["market_cutoff_date"],
            "research_weight_seen_market": row["market_known_weight_research_only"],
            "research_weight_missing_market": 1050-row["market_known_weight_research_only"],
            "missing_market_nodes": row["market_missing_nodes"],
            "reproduced_partial_research_score_NOT_AICS":
                row["market_partial_weighted_points_NOT_AICS"],
            "SP500_close_observed_expost": row["sp500_close_retrieved_expost"],
            "historic_independent_full_11node_PIT": False,
            "state": "CHECKED_PARTIAL_NOT_CERTIFIED",
            "next_action": "recover missing historically delivered source vintages and freeze formula before OOS",
        })

    for node in sorted(node_rows, key=lambda x: -x["weight"]):
        name = node["node"]
        if (node["weight"] != WEIGHTS[name]
            or node["independently_certified"] is not False
            or node["node_stress_score"] is not None
            or node["completed_milestones"] != 2):
            raise ValueError("Research scoring incorrectly upgraded node certification")
        tasks.append({
            "task_id": f"NODE-{len(tasks)-78:03d}", "priority": "P1",
            "workstream": "frozen_11_node_score_mapping_and_untouched_OOS",
            "node": name, "weight": WEIGHTS[name],
            "verified_historic_node_score": None,
            "independent_24month_OOS": False,
            "state": "BLOCKED_HISTORICAL_PIT_AND_OOS",
            "next_action": "audit source-to-score map; recover valid historical vintages; preregister untouched walk-forward",
        })

    control_conditions = [
        ("100_source_archive_tasks", len(reports["tasks"]) == 100),
        ("36_exact_original_accessions", len(claims) == 36),
        ("19_distinct_scoring_cohorts", len(cohorts) == 19),
        ("two_monthly_methods_no_disagreement",
         reconciled["independent_replay_methods_compared"] == 2
         and reconciled["month_node_disagreements_remaining"] == 0),
        ("24_fixed_month_reconstructions", len(months) == 24),
        ("following_month_targets_expost_only",
         lead["SP500_following_month_returns_used_only_as_targets"] is True),
        ("first_month_source_cohort_frozen",
         lead["cohort_selected_in_2024_11_then_preserved_without_future_selection"] is True),
        ("no_independent_24month_OOS",
         lead["independent_24m_out_of_sample_forecast_labels"] == 0),
        ("no_2000_2008_early_warning_certification",
         lead["2000_2008_crisis_onset_lead_time_certified"] is False),
        ("no_auto_trading_or_production_index",
         lead["production_trades_created"] is False
         and targeted["trades_created"] is False
         and reconciled["full_11node_AICS"] is None),
    ]
    for i, (name, passed) in enumerate(control_conditions, 1):
        if not passed:
            raise ValueError(f"Priority100 negative control failed: {name}")
        tasks.append({
            "task_id": f"CONTROL-{i:03d}", "priority": "P2",
            "workstream": "forecast_governance_negative_controls",
            "check": name, "control_verified": True,
            "state": "GUARD_VERIFIED_NOT_PREDICTIVE_SKILL",
            "next_action": "retain as regression protection; do not infer forecasting quality",
        })

    if (len(tasks) != 100 or len({t["task_id"] for t in tasks}) != 100
        or Counter(t["workstream"] for t in tasks) != {
            "exact_SEC_source_bytes_and_numeric_replay": 36,
            "reproduce_19_original_accounting_source_event_scores": 19,
            "24_month_PIT_coverage_and_SP500_falsification": 24,
            "frozen_11_node_score_mapping_and_untouched_OOS": 11,
            "forecast_governance_negative_controls": 10,
        }):
        raise ValueError("Priority100 must run exactly 100 different grounded audit tasks")
    corr = lead["descriptive_correlation_risk_vs_following_month_SP500_return_pearson"]
    if corr is not None and (not math.isfinite(float(corr)) or abs(float(corr)) > 1):
        raise ValueError("Invalid next-month descriptive correlation")
    return {
        "schema": "aics-priority100-evidence-workbench-v1",
        "as_of": reconciled["as_of"],
        "deterministic_specialized_audit_tasks_executed": 100,
        "independently_trained_agents_added": 0,
        "priority_0_original_document_tasks": 36,
        "priority_0_original_event_cohort_tasks": 19,
        "priority_1_monthly_source_tasks": 24,
        "priority_1_node_score_tasks": 11,
        "priority_2_safety_control_tasks": 10,
        "exact_referenced_SEC_source_and_SGML_bytes_currently_verified":
            sum(source_status.values()),
        "original_accounting_values_independently_recomputed": 0,
        "original_scoring_cohorts_independently_recomputed": 0,
        "24_month_expost_research_coverage_checked": 24,
        "next_month_SP500_correlation_expost_only": corr,
        "independent_untouched_24m_OOS": None,
        "full_11node_AICS": None,
        "independently_certified_nodes": 0,
        "trades_created": False,
        "priority_queue": tasks,
        "next_highest_value": "SEC original bytes -> published original accounting numbers -> dated 11-node scores -> historical first delivery -> preregistered OOS",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--crosswalk", type=Path, default=CROSSWALK)
    p.add_argument("--targeted", type=Path, default=TARGETED)
    p.add_argument("--reports", type=Path, default=REPORTS)
    p.add_argument("--headers", type=Path, default=HEADERS)
    p.add_argument("--reconciled", type=Path, default=RECONCILED)
    p.add_argument("--lead", type=Path, default=LEAD)
    p.add_argument("--status", type=Path, default=STATUS)
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args()
    paths = [args.crosswalk, args.targeted, args.reports, args.headers,
             args.reconciled, args.lead, args.status]
    out = build(*(_read(x) for x in paths))
    out["input_sha256"] = {str(x): hashlib.sha256(x.read_bytes()).hexdigest() for x in paths}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "priority_queue"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
