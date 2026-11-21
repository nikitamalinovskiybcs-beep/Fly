"""Check as-of 20-Nov AICS source eligibilities without upgrading research to PIT.

Keeps the full eleven-node reproduction in aics_close_20261120 and audits
new official source candidates that cannot change existing model definitions.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from scripts.aics_close_20261120 import calculate
from scripts.aics_score_reproducibility_gate import WEIGHTS

LEDGER = Path("aics_data/research/aics_asof_2026_11_20_source_eligibility_overlay.json")
CLOSE = dt.date(2026, 11, 20)
OFFICIAL = {
    "UST 30Y": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value_month=202611&type=daily_treasury_yield_curve",
    "Insurers": "https://www.sec.gov/Archives/edgar/data/1099219/000109921926000062/0001099219-26-000062-index.htm",
    "Semiconductors Supply": "https://www.federalreserve.gov/releases/G17/20261117/table2_sup.htm",
    "Neoclouds": "https://www.sec.gov/Archives/edgar/data/1769628/000176962826000465/0001769628-26-000465-index.htm",
    "SPV": "https://www.sec.gov/Archives/edgar/data/1769628/000176962826000465/0001769628-26-000465-index.htm",
}


def validate(record=None, rollover=None):
    record = record if record is not None else json.loads(LEDGER.read_text(encoding="utf-8"))
    rollover = rollover if rollover is not None else calculate()
    if (record.get("schema") != "aics-asof-close-source-eligibility-review-v1"
            or record.get("market_close_date") != CLOSE.isoformat()
            or record.get("research_only") is not True
            or record.get("provider_retrieval_attested") is not False
            or record.get("production_verdict_changed") is not False
            or record.get("trades_created") is not False
            or record.get("certified_aics") is not None
            or record.get("independent_pit_attested_nodes") != 0
            or record.get("independent_oos_nodes") != 0
            or record.get("total_weight") != 1050
            or record.get("score_changes") != []):
        raise ValueError("As-of source overlay attempted unsupported promotion")
    rows = record["nodes"]
    if len(rows) != len(WEIGHTS) or {r["node"] for r in rows} != set(WEIGHTS):
        raise ValueError("Eleven-node source review incomplete or duplicated")
    original = {x["node"]: x for x in rollover["nodes"]}
    if rollover["certified_aics"] is not None or rollover["promotion"] != "RESEARCH_ONLY_UNCERTIFIED":
        raise ValueError("Research close invalidly certified")
    for row in rows:
        node = row["node"]
        if row["score"] != original[node]["score"] or not row.get("status") or not row.get("note"):
            raise ValueError(f"Score mutated without eligible same-definition source: {node}")
    sources = record["newly_checked_official_evidence"]
    if len(sources) != len(OFFICIAL) or {r["node"] for r in sources} != set(OFFICIAL):
        raise ValueError("Missing original primary-source checks")
    for source in sources:
        node = source["node"]
        if source["source_url"] != OFFICIAL[node] or source["score_recalibration_allowed"] is not False:
            raise ValueError("Official source mismatch or unjustified scoring")
        if "filed_at" in source:
            filed = dt.date.fromisoformat(source["filed_at"])
            available = dt.date.fromisoformat(source["available_at"])
            if filed + dt.timedelta(days=14) != available:
                raise ValueError("SEC +14 calendar-day invariant failed")
            if node in ("Neoclouds", "SPV") and available <= CLOSE:
                raise ValueError("Future CoreWeave Q3 SEC access improperly backdated")
            if node == "Insurers":
                if available != CLOSE or source["issuer"] != "MetLife":
                    raise ValueError("MetLife eligibility date or issuer changed")
                if source["original_byte_hash"] is not None or source["independent_rehash"] is not False:
                    raise ValueError("Original SEC byte replay not attested")
                if (source["mortgage_acl_usd_m"] != 1521 or
                        source["net_mortgage_loans_usd_m"] != 83839 or
                        source["prior_q2_mortgage_acl_usd_m"] != 1358):
                    raise ValueError("MET credit accounting operands altered")
        elif node == "UST 30Y":
            if (source["observation_date"] != CLOSE.isoformat()
                    or source["previous_date"] != "2026-11-19"
                    or source["source_release_timestamp_attested"] is not False
                    or int(source["change_bp"]) !=
                    round(100 * (float(source["current_30y_pct"]) - float(source["previous_30y_pct"])))):
                raise ValueError("Treasury daily observation inconsistent")
        elif node == "Semiconductors Supply":
            if (source["published_on"] != "2026-11-17"
                    or source["period"] != "2026-10"
                    or source["naics"] != "3344"
                    or float(source["preliminary_capacity_utilization_pct"]) != original[node]["score"]):
                raise ValueError("Fed release inconsistent with frozen October score")
    if str(rollover["research_aics"]) != record["new_research_aics"]:
        raise ValueError("Overlay and 11-node level do not reconcile")
    return {
        "session": CLOSE.isoformat(),
        "11_nodes_source_eligibility_checked": len(rows),
        "new_official_evidence_checks": len(sources),
        "score_changes": 0,
        "research_aics_rollover": str(rollover["research_aics"]),
        "certified_aics": None,
        "admissibility": "NOT FULLY REFRESHED, NO INVESTMENT GRADE CERTIFICATION",
        "next_sec_eligibility_coreweave_q3": "2026-11-26",
    }


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
