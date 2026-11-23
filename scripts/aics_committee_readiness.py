#!/usr/bin/env python3
"""Fail-closed AICS committee readiness gate. Never calculates scores or trades."""
import argparse
import datetime as dt
import json
from pathlib import Path

WEIGHTS = {
    "Private Credit": 150, "Insurers": 125, "UST 30Y": 125,
    "Neoclouds": 100, "AI Equities": 100, "Hyperscalers": 100,
    "SPV": 100, "Repo": 100, "Power/Data Centers": 50,
    "Semiconductors Supply": 50, "AI Demand": 50,
}
assert len(WEIGHTS) == 11 and sum(WEIGHTS.values()) == 1050

def read_json(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pit-dir", default="aics_data/pit")
    parser.add_argument("--out", default="aics_data/pit/committee_readiness.json")
    args = parser.parse_args()
    root = Path(args.pit_dir)
    quality = read_json(root / "quality_report.json")
    coverage = read_json(root / "coverage_report.json")
    series = coverage.get("series", [])
    required = {"DGS30", "SOFR", "BAMLH0A0HYM2", "BAMLH0A3HYC"}
    series_by_id = {s.get("series_id"): s for s in series if isinstance(s, dict)}
    alfred_structure = (
        quality.get("structurally_valid") is True
        and quality.get("errors") == []
        and coverage.get("historical_snapshot_coverage_complete") is True
        and set(series_by_id) == required
        and all(series_by_id[k].get("snapshots_downloaded_unverified") == 24
                and series_by_id[k].get("structurally_valid") is True for k in required)
    )
    gates = {
        "fixed_11_node_weights": True,
        "alfred_96_snapshot_structural_integrity": alfred_structure,
        "independent_alfred_source_verification": False,
        "sec_filed_at_plus_14_days_verified": False,
        "all_11_nodes_point_in_time_coverage": False,
        "independent_24_month_out_of_sample_validation": False,
        "committee_approval": False,
    }
    result = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "policy": "research_only_fail_closed",
        "weights": WEIGHTS,
        "weights_total": sum(WEIGHTS.values()),
        "gates": gates,
        "blocking_gates": [name for name, passed in gates.items() if not passed],
        "promotion": "BLOCKED",
        "index_aics": None,
        "model_score": None,
        "trades_created": False,
        "note": "External gates are false until independently attested evidence is supplied; this script cannot approve them.",
    }
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"promotion": result["promotion"], "blocking_gates": result["blocking_gates"]}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
