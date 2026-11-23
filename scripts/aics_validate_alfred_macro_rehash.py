#!/usr/bin/env python3
"""Audit rehashed ALFRED snapshot receipt without certifying historical PIT.

This verifies the *versioned receipt*, not the source API or provider vintage
archive itself. Original CSV/ZIP bytes must be rehashed separately. The two
licensed ICE series are represented by source digests/counts only, not values.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from decimal import Decimal
from pathlib import Path

DEFAULT = Path("aics_data/research/alfred_macro_archive_rehash_2026_11_18.json")
SHA = re.compile("[0-9a-f]{64}\\Z")
EXPECTED = {"DGS30": ("UST 30Y", 95246),
            "SOFR": ("Repo", 45655),
            "BAMLH0A0HYM2": ("Private Credit", 12506),
            "BAMLH0A3HYC": ("Private Credit", 12506)}
LICENSED = {"BAMLH0A0HYM2", "BAMLH0A3HYC"}


def require(cond: bool, reason: str) -> None:
    if not cond:
        raise ValueError(reason)


def check_receipt(data: dict) -> dict:
    require(isinstance(data, dict)
            and data.get("schema_version") == "aics-alfred-macro-research-recheck-v1",
            "unknown ALFRED macro receipt")
    as_of = dt.date.fromisoformat(data["checked_at"])
    latest = dt.date.fromisoformat(data["snapshot_as_of_latest"])
    require(latest <= as_of and data.get("scope") ==
            "REHASHED_ARCHIVED_ALFRED_SNAPSHOTS_NOT_PROVIDER_VINTAGE_ATTESTATION",
            "historical provider vintage not independently attested")
    require(data.get("series_count") == 4
            and data.get("monthly_vintages_per_series") == 24
            and data.get("source_rows_total") == 165913
            and data.get("total_weights") == 1050
            and data.get("additional_project_milestones") == 0
            and data.get("historical_pit_certified") is False
            and data.get("independent_provider_vintage_attestation") is False
            and data.get("source_license_cleared_for_all_series") is False
            and data.get("approved_investment_signal") is False
            and data.get("score_eligible") is False
            and data.get("index_aics") is None
            and data.get("predictive_skill_score") is None
            and data.get("promotion") == "BLOCKED"
            and data.get("trades_created") is False,
            "ALFRED receipt cannot be promoted to AICS")
    require(isinstance(data.get("artifact_id"), int)
            and data["artifact_id"] == 14432003774
            and data.get("github_artifact_run_url") ==
            "https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44313687138"
            and data.get("artifact_zip_sha256") ==
            "03d06b287dc591d6830223bd181db401d19ce618a785b40c25a999ab1ddd5cc3",
            "ALFRED original archive identity changed")
    require(dt.datetime.fromisoformat(data["artifact_expires_at"].replace("Z","+00:00")).date() > as_of,
            "missing retained ALFRED artifact")
    rows = data.get("series")
    require(isinstance(rows, list) and len(rows) == len(EXPECTED),
            "incomplete primary macro series")
    seen, count = set(), 0
    described = []
    for r in rows:
        require(isinstance(r, dict), "bad series receipt row")
        sid = r.get("series_id")
        require(sid in EXPECTED and sid not in seen
                and r.get("candidate_node") == EXPECTED[sid][0]
                and r.get("source_rows") == EXPECTED[sid][1]
                and r.get("snapshot_count") == 24
                and r.get("unit") == "percent"
                and isinstance(r.get("csv_sha256"), str)
                and SHA.fullmatch(r["csv_sha256"]) is not None
                and r.get("provider_vintage_independently_attested") is False
                and r.get("node_stress_score") is None,
                "invalid macro source count, hash or score")
        seen.add(sid)
        count += r["source_rows"]
        if sid in LICENSED:
            require(r.get("source_license_public_redistribution_cleared") is False
                    and r.get("numeric_observations_publicly_republished") is False
                    and r.get("proxy_not_direct_private_credit") is True
                    and "sept_snapshot" not in r and "oct_snapshot" not in r
                    and "month_end_asof_change_basis_points" not in r,
                    "ICE licensed values are not permitted in this public receipt")
        else:
            sep = r["sept_snapshot"]
            oct_ = r["oct_snapshot"]
            require(sep.get("as_of") == "2026-09-30"
                    and oct_.get("as_of") == "2026-10-31"
                    and dt.date.fromisoformat(sep["observation_date"]) <=
                    dt.date.fromisoformat(sep["as_of"])
                    and dt.date.fromisoformat(oct_["observation_date"]) <=
                    dt.date.fromisoformat(oct_["as_of"]),
                    "future observed macro input")
            difference = (Decimal(str(oct_["value_percent"])) -
                          Decimal(str(sep["value_percent"]))) * 100
            require(difference == Decimal(str(r["month_end_asof_change_basis_points"])),
                    "reported as-of macro basis point difference is incorrect")
            described.append({"series_id": sid, "latest_as_of": oct_["as_of"],
                              "latest_observation": oct_["observation_date"],
                              "monthly_change_basis_points": str(difference)})
    require(seen == set(EXPECTED) and count == data["source_rows_total"],
            "ALFRED source coverage differs from archived evidence")
    return {
        "metadata_audit": "PASS_RESEARCH_ONLY",
        "source_zip_independently_rehashed_in_this_script": False,
        "sources": len(seen), "vintage_months_per_series": 24,
        "archived_rows": count, "public_macro_changes": described,
        "historical_provider_pit_certified": False, "index_aics": None,
        "promotion": "BLOCKED",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=DEFAULT)
    args = parser.parse_args()
    print(json.dumps(check_receipt(json.loads(args.receipt.read_text(encoding="utf-8"))),
                     indent=2))


if __name__ == "__main__":
    main()
