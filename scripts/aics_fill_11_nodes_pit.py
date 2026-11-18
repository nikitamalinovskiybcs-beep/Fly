#!/usr/bin/env python3
"""Fail-closed 11-node PIT gap report; deliberately NEVER fills missing scores.

Audits real repo source receipts and SEC date gates, using unchanged 1050
weights. Refuses IPO-era reweighting, synthetic/backfilled values and
unattested historical publication dates. A 2018 observation in today's
provider history does not prove it was public in 2018.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(".")
STATUS = Path("aics_data/progress/status.json")
SEC_REGISTRY = Path("aics_data/source_registry/sec_spv_neoclouds_filings_2026-11-18.json")
NYFED = Path("aics_data/research/nyfed_repo_original_archive_independent_rehash_2026_11_18.json")
UNIVERSE = Path("aics_data/research/aics_extended_company_universe_omi_telegram_2026-11-18.json")
REPORT = Path("docs/audit/aics_11_node_free_source_pit_2026-11-18.json")
WEIGHTS = {
    "Private Credit": 150, "Insurers": 125, "UST 30Y": 125,
    "Neoclouds": 100, "AI Equities": 100, "Hyperscalers": 100,
    "SPV": 100, "Repo": 100, "Power/Data Centers": 50,
    "Semiconductors Supply": 50, "AI Demand": 50,
}
CANDIDATE_SOURCES = {
    "Private Credit": ["SEC BDC companyfacts and filings", "ALFRED HY credit spreads"],
    "Insurers": ["SEC MET/PRU 10-Q and companyfacts", "NAIC/reinsurance contract proof pending"],
    "UST 30Y": ["ALFRED DGS30 as-of snapshots", "Treasury term premium methodology pending"],
    "Neoclouds": ["SEC APLD/NBIS/CRWV filings", "private project contracts pending"],
    "AI Equities": ["Nasdaq original price current capture", "VIXCLS/VXNCLS PIT and constituents pending"],
    "Hyperscalers": ["SEC issuer filings and primary IR", "cash/lease and contract mapping pending"],
    "SPV": ["SEC leases and financing notes", "legal borrower and recourse mapping pending"],
    "Repo": ["NY Fed SOFR/BGCR/TGCR original capture", "ALFRED IORB as-of gate"],
    "Power/Data Centers": ["ALFRED WPU0543 industrial power PPI", "EIA/site price constraints pending"],
    "Semiconductors Supply": ["SEC and original issuer IR", "supply chain exposure mapping pending"],
    "AI Demand": ["SEC hyperscaler financials and original IR", "contract demand mapping pending"],
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return data


def audit(status_path: Path = STATUS, sec_path: Path = SEC_REGISTRY,
          nyfed_path: Path = NYFED, universe_path: Path = UNIVERSE) -> dict:
    status, sec, nyfed, universe = map(_load, (status_path, sec_path, nyfed_path, universe_path))
    as_of_str = "2026-11-18"
    as_of = dt.date.fromisoformat(as_of_str)
    if not (status.get("as_of") == as_of_str == sec.get("as_of")
            and universe.get("source_as_of") == as_of_str == nyfed.get("as_of")):
        raise ValueError("source as-of mismatch")
    if (set(WEIGHTS) != set(CANDIDATE_SOURCES)
            or len(WEIGHTS) != 11 or sum(WEIGHTS.values()) != 1050
            or status.get("total_weight") != 1050 or status.get("total_nodes") != 11):
        raise ValueError("AICS immutable weights violated")
    nodes = status.get("node_progress")
    if not isinstance(nodes, list) or len(nodes) != 11:
        raise ValueError("missing AICS nodes")
    if {node["node"] for node in nodes} != set(WEIGHTS):
        raise ValueError("duplicate or unknown AICS node")
    for node in nodes:
        if (node.get("weight") != WEIGHTS[node["node"]]
                or node.get("node_stress_score") is not None
                or node.get("independently_certified") is not False
                or any(node.get("gates", {}).get(step, None) is not False for step in (
                    "independently_attested_pit", "audited_node_scoring",
                    "untouched_24m_oos", "independent_certification"))):
            raise ValueError("unattested node promoted or reweighted")
    if (status.get("source_pit_attested_nodes") != 0
            or status.get("audited_scoring_nodes") != 0
            or status.get("untouched_24m_oos_nodes") != 0
            or status.get("independently_certified_nodes") != 0
            or status.get("index_aics") is not None
            or status.get("predictive_skill_score") is not None):
        raise ValueError("unverified model signal detected")
    if (status.get("milestones_completed") != sum(n["completed_milestones"] for n in nodes)
            or status.get("milestones_total") != 66):
        raise ValueError("milestone scorekeeping mismatch")

    docs = sec.get("documents", [])
    if len(docs) != 5 or not isinstance(docs, list):
        raise ValueError("missing SEC raw filing registry")
    seen, passed, barred = set(), 0, 0
    sec_gates = []
    for doc in docs:
        source_id = doc["source_id"]
        if source_id in seen:
            raise ValueError("duplicate SEC accession source")
        seen.add(source_id)
        filed = dt.date.fromisoformat(doc["filed_at"])
        available = dt.date.fromisoformat(doc["available_at"])
        if available != filed + dt.timedelta(days=14):
            raise ValueError("SEC 14-calendar-day embargo violated")
        allowed = available <= as_of
        passed += bool(allowed)
        barred += not allowed
        sec_gates.append({"source_id": source_id, "filed_at": filed.isoformat(),
                          "available_at": available.isoformat(),
                          "asof_date_eligible": allowed,
                          "original_release_pit_attested_here": False,
                          "model_eligible": False})
    if (passed != 4 or barred != 1 or
            next(x for x in sec_gates if x["source_id"] == "CRWV_10Q_20261112")
                ["available_at"] != "2026-11-26"):
        raise ValueError("SEC chronology mismatch")

    if (nyfed.get("independent_original_byte_rehash_passed") is not True
            or nyfed.get("total_raw_rows") != 2997
            or nyfed.get("progress_milestones_promoted") != 0
            or nyfed.get("rate_publication_pit_attested") is not False
            or nyfed.get("market_stress_score") is not None
            or nyfed.get("aics_index") is not None
            or nyfed.get("promotion") != "BLOCKED"):
        raise ValueError("NY Fed candidate illegally promoted")
    archives = nyfed.get("archive_files")
    if (not isinstance(archives, list) or len(archives) != 3
            or {x["rate_type"] for x in archives} != {"SOFR", "BGCR", "TGCR"}
            or sum(x["row_count"] for x in archives) != 2997
            or any(x["row_count"] != 999 or not SHA256.fullmatch(x["raw_sha256"])
                   for x in archives)):
        raise ValueError("NY Fed original archive integrity metadata incomplete")

    companies = universe.get("companies", [])
    if (len(companies) != 37 or len({x["name"] for x in companies}) != 37
            or any(x.get("model_eligible") is not False for x in companies)):
        raise ValueError("research company names masquerade as data")
    origin_count = {
        "OMI_PDF": sum(x["origin"] == "OMI_PDF" for x in companies),
        "TELEGRAM_SCREENSHOTS_NOT_IN_OMI_PDF":
            sum(x["origin"] == "TELEGRAM_SCREENSHOTS_NOT_IN_OMI_PDF" for x in companies),
    }
    if origin_count != {"OMI_PDF": 26, "TELEGRAM_SCREENSHOTS_NOT_IN_OMI_PDF": 11}:
        raise ValueError("company provenance altered")

    return {
        "schema_version": "aics-free-sources-11-node-pit-gate-v1",
        "as_of": as_of_str,
        "fixed_total_weight": 1050,
        "node_count": 11,
        "reweight_after_ipo_permitted": False,
        "unobserved_nodes_renormalized": False,
        "research_company_names": 37,
        "source_inventory": [
            {"node": name, "weight": weight,
             "candidate_sources": CANDIDATE_SOURCES[name],
             "independently_attested_historical_pit": False,
             "independent_oos_24m": False, "node_score": None,
             "certified": False}
            for name, weight in WEIGHTS.items()
        ],
        "sec_sources": {"registry_documents": 5, "date_eligible": passed,
                        "embargoed": barred, "documents": sec_gates},
        "nyfed_repo": {
            "independently_rehashed_source_archive": True,
            "source_rows": 2997,
            "raw_zip_sha256": nyfed["source_archive_zip_sha256"],
            "last_effective_date": nyfed["reference_date"],
            "historical_release_vintages_attested": False,
            "current_capture_not_2018_to_2026_pit": True,
            "model_stress_score": None,
        },
        "further_candidate_series": ["IORB", "WPU0543", "VIXCLS", "VXNCLS"],
        "numerai_api": "CONNECTED_READ_ONLY_PRIOR_ACTION_NOT_MARKET_PIT",
        "historical_alFred_monthly_vintage_coverage_from_2018_proven": False,
        "independently_verified_pit_nodes": 0,
        "independently_certified_nodes": 0,
        "node_scores": dict.fromkeys(WEIGHTS),
        "index_aics": None,
        "predictive_skill_score": None,
        "promotion": "BLOCKED",
        "trades_created": False,
        "committee_notes": [
            "Free provider endpoints do not establish 9 of 11 nodes certified.",
            "Issuer SEC companyfacts are retrospectively aggregated and do not by themselves prove dated original filings.",
            "Only SEC source dates at or before 2026-11-04 meet the Nov-18 +14 day gate.",
            "NY Fed secured-rate effectiveDate is not its historical publication timestamp.",
            "2018 observations from the current archive are not 2018 publication vintages.",
            "Industrial power PPI is not data center-specific negotiated electricity cost.",
            "Numerai Classic/Signals benchmark target eras cannot fill company financial disclosures.",
            "Do not retroactively reweight the fixed 1050 model after issuer IPOs.",
            "No score, look-ahead-adjusted OOS or trade may be published from candidate source coverage.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=REPORT)
    args = parser.parse_args()
    result = audit()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"nodes": 11, "weights": 1050, "nyfed_rows": 2997,
                      "sec_date_eligible": 4, "certified_nodes": 0,
                      "index_aics": None, "promotion": "BLOCKED"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
