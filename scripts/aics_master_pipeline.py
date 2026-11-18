#!/usr/bin/env python3
"""Master CI orchestrator for the *frozen* AICS 2026-11-18 research audit.

The user-supplied v1.2.0 workflow named this script but did not supply it.
This implementation runs an 11-node, existing-source PIT gap reconciliation
instead of filling unpublished 0-100 stress scores or falsely backdating
new API responses to a historical cutoff. Source downloads run in dedicated
SEC/ALFRED/NY Fed workflows with their own SHA, release and rights gates.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from scripts.aics_fill_11_nodes_pit import audit

FROZEN_AS_OF = "2026-11-18"
REPORT_DIR = Path("docs/audit")
SOURCE_AUDIT_FILE = "aics_11_node_free_source_pit_2026-11-18.json"
MASTER_REPORT_FILE = "aics_master_ci_report_2026-11-18.json"


def run_master(as_of: str, *, output_dir: Path = REPORT_DIR) -> dict:
    """Audit already archived sources; cannot replay history at invented dates."""
    try:
        cutoff = dt.date.fromisoformat(as_of)
    except (TypeError, ValueError):
        raise ValueError("as_of must be an ISO calendar date") from None
    if cutoff > dt.datetime.now(dt.timezone.utc).date():
        raise ValueError("future as_of cutoff forbidden")
    if as_of != FROZEN_AS_OF:
        raise ValueError("frozen-source report cannot be relabeled as another PIT date")
    evidence = audit()
    if not (
        evidence["as_of"] == as_of
        and evidence["fixed_total_weight"] == 1050
        and evidence["node_count"] == 11
        and evidence["independently_verified_pit_nodes"] == 0
        and evidence["independently_certified_nodes"] == 0
        and evidence["index_aics"] is None
        and evidence["predictive_skill_score"] is None
        and evidence["promotion"] == "BLOCKED"
        and evidence["reweight_after_ipo_permitted"] is False
        and len(evidence["source_inventory"]) == 11
        and all(node["node_score"] is None for node in evidence["source_inventory"])
    ):
        raise ValueError("AICS source audit attempts unsupported model promotion")

    current_utc = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    result = {
        "schema_version": "aics-master-ci-research-audit-v1",
        "as_of": FROZEN_AS_OF,
        "executed_at_utc": current_utc,
        "source_audit_report": SOURCE_AUDIT_FILE,
        "source_audit_as_of_relabeling_allowed": False,
        "scope": "FROZEN_EXISTING_EVIDENCE_ONLY",
        "collection_performed_by_master": False,
        "live_market_data_as_of_2026_11_18_claimed": False,
        "required_primary_source_collection_workflows": [
            "aics-alfred-pit.yml",
            "aics-alfred-iorb-power.yml",
            "aics-spv-neocloud-sec-evidence.yml",
            "aics-insurers-sec-evidence.yml",
            "aics-nyfed-repo-source.yml",
        ],
        "source_sec_docs_date_eligible": evidence["sec_sources"]["date_eligible"],
        "source_sec_docs_embargoed": evidence["sec_sources"]["embargoed"],
        "nyfed_original_archived_rows": evidence["nyfed_repo"]["source_rows"],
        "weights_fixed": 1050,
        "total_nodes": 11,
        "independently_attested_pit_nodes": 0,
        "independently_certified_nodes": 0,
        "untouched_24_month_oos": False,
        "index_aics": None,
        "predictive_skill_score": None,
        "promotion": "BLOCKED",
        "trades_created": False,
        "notes": [
            "No synthetic or interpolated financial observations were generated.",
            "A current API response does not certify a provider's historical release vintage.",
            "SEC available_at is filing date plus exactly 14 calendar days.",
            "AICS never reweights its fixed 1050 denominator after a company IPO.",
            "Uploaded 12-observation percentile example is illustrative; not approved scoring methodology.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / SOURCE_AUDIT_FILE).write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / MASTER_REPORT_FILE).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=FROZEN_AS_OF)
    parser.add_argument("--out-dir", type=Path, default=REPORT_DIR)
    args = parser.parse_args()
    try:
        result = run_master(args.as_of, output_dir=args.out_dir)
    except (ValueError, FileNotFoundError, KeyError) as exc:
        # No accidental index; do not leak external API keys or account data.
        print("AICS master audit BLOCKED:", type(exc).__name__)
        return 1
    print(json.dumps({
        "as_of": result["as_of"],
        "research_evidence_only": True,
        "nodes": result["total_nodes"],
        "weight": result["weights_fixed"],
        "independent_pit_nodes": result["independently_attested_pit_nodes"],
        "certified_nodes": result["independently_certified_nodes"],
        "index_aics": None,
        "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
