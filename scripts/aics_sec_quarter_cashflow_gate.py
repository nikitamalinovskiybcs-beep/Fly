"""Strict, ex-post SEC numeric quarter matching from real companyfacts receipts.

Separates direct 3-month quarter cash flows from 6/9/12-month YTD/annual
facts. Never subtract YTD records automatically or claim SEC historical PIT.
No AICS scores, market predictions, company quarter fabricated values.

Input: actual_sec_xbrl_facts_unverified.json from ten real collection waves.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS

INPUT = Path("aics_data/agent_runs/ten_real_collection_rounds/actual_sec_xbrl_facts_unverified.json")
OUTPUT = Path("aics_data/agent_runs/ten_real_collection_rounds/sec_direct_quarter_cashflow_gate.json")
OCF = "NetCashProvidedByUsedInOperatingActivities"
CAPEX = "PaymentsToAcquirePropertyPlantAndEquipment"
ACC = re.compile(r"^\d{10}-\d{2}-\d{6}$")
HEX = re.compile(r"^[0-9a-f]{64}$")
THREE_MONTH_MIN_DAYS = 75
THREE_MONTH_MAX_DAYS = 110


def _calendar(value, field):
    if not isinstance(value, str):
        raise ValueError(f"Missing original calendar {field}")
    return dt.date.fromisoformat(value)


def _quantity(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("SEC raw numeric value expected")
    v = Decimal(str(value))
    if not v.is_finite():
        raise ValueError("Nonfinite SEC numeric record")
    return v


def _row(row, cutoff):
    if not isinstance(row, dict):
        raise ValueError("Non-object SEC companyfact row")
    if row.get("tag") not in (OCF,CAPEX):
        return None, "other_xbrl_tag"
    if not isinstance(row.get("source_id"), str) or not re.fullmatch(
            r"XBRL_SEC_[A-Z]{2,6}", row["source_id"]):
        raise ValueError("Unknown SEC original XBRL source label")
    if row.get("unit") != "USD":
        return None, "non_usd_cashflow_unit"
    if row.get("form") not in ("10-Q", "10-K", "10-Q/A", "10-K/A"):
        raise ValueError("Original quarterly or annual SEC form required")
    if not isinstance(row.get("original_sec_accession"), str) or not ACC.fullmatch(
            row["original_sec_accession"]):
        raise ValueError("Original SEC accession missing")
    if not isinstance(row.get("original_companyfacts_snapshot_sha256"), str) or not HEX.fullmatch(
            row["original_companyfacts_snapshot_sha256"]):
        raise ValueError("Original content SHA256 missing")
    if row.get("original_first_document_bytes_verified") is not False or (
            row.get("retrospective_provider_pit_certified") is not False):
        raise ValueError("Source wrongly asserts historical original first filing PIT")
    start = row.get("period_start")
    if start is None:
        return None, "no_flow_period_start"
    start, end = _calendar(start,"start"), _calendar(row.get("period_end"),"end")
    filed = _calendar(row.get("filed_at"), "filed")
    eligible = _calendar(row.get("research_eligible_date_only_proxy"),"research eligibility")
    if eligible != filed + dt.timedelta(days=1):
        raise ValueError("Invalid date-only SEC first research eligibility")
    if end > filed or end > cutoff:
        raise ValueError("Lookahead: SEC economic period after source filing or cutoff")
    if filed > cutoff or eligible > cutoff:
        return None, "not_yet_available_by_current_research_date"
    if end < start:
        raise ValueError("Invalid original financial period start/end")
    value = _quantity(row.get("value"))
    if row["tag"]==CAPEX and value < 0:
        raise ValueError("Capex cash payment must be nonnegative")
    if value.as_tuple().exponent < -9:
        raise ValueError("Unsupported original numeric precision")
    # Exactly 3-month original periods, not year-to-date or full-year values.
    duration=(end-start).days+1
    if not THREE_MONTH_MIN_DAYS <= duration <= THREE_MONTH_MAX_DAYS:
        return None, "long_ytd_or_nonquarter_duration"
    # Do not use tagged quarter without the original issuer accounting scope.
    return {
        "issuer_cik": str(int(row["cik"])),
        "source_id": row["source_id"],
        "form": row["form"], "accession": row["original_sec_accession"],
        "snapshot_sha256": row["original_companyfacts_snapshot_sha256"],
        "period_start": start.isoformat(), "period_end": end.isoformat(),
        "duration_days": duration, "filed_at": filed.isoformat(),
        "research_eligible_at_date_proxy": eligible.isoformat(),
        "unit": "USD", "tag": row["tag"], "value": value,
        "frame": row.get("frame"),
    }, "direct_3month_original_fact_candidate"


def audit(raw_rows, *, as_of):
    if isinstance(as_of, str):
        as_of = dt.date.fromisoformat(as_of)
    if not isinstance(as_of, dt.date) or isinstance(as_of, dt.datetime):
        raise ValueError("Explicit as-of day required")
    if not isinstance(raw_rows, list):
        raise ValueError("SEC companyfacts record array required")
    selections = defaultdict(list)
    counts = Counter()
    found = set()
    for row in raw_rows:
        item, status = _row(row, as_of)
        counts[status] += 1
        if item is None:
            continue
        key = (item["issuer_cik"], item["accession"], item["period_start"],
               item["period_end"], item["snapshot_sha256"],item["tag"],
               str(item["value"]),item["unit"])
        if key in found:
            counts["duplicate_identical_value_ignored"] += 1
            continue
        found.add(key)
        grouping = (item["issuer_cik"], item["accession"], item["period_start"],
                    item["period_end"], item["snapshot_sha256"],
                    item["filed_at"], item["form"])
        selections[grouping].append(item)
    paired = []
    blocked = []
    for group, records in sorted(selections.items()):
        tags = {tag: [x for x in records if x["tag"]==tag] for tag in (OCF,CAPEX)}
        source_ids = sorted(set(x["source_id"] for x in records))
        status = "missing_ocf_or_capex"
        if len(tags[OCF])==1 and len(tags[CAPEX])==1 and len(source_ids)==1:
            cfo, ppe = tags[OCF][0]["value"], tags[CAPEX][0]["value"]
            status = "direct_period_pair"
            paired.append({
                "issuer_cik": group[0], "source_id": source_ids[0],
                "original_sec_accession": group[1],
                "period_start": group[2], "period_end": group[3],
                "original_companyfacts_snapshot_sha256": group[4],
                "filed_at": group[5], "form": group[6],
                "research_eligible_at_date_proxy": tags[OCF][0]["research_eligible_at_date_proxy"],
                "ocf_usd": str(cfo), "cash_ppe_usd": str(ppe),
                "cash_gap_usd": str(cfo-ppe),
                "source_scope_consistency": "single_accession_same_period_same_issuer_original_snapshot",
                "accounting_period_3months": True,
                "original_first_document_bytes_verified": False,
                "historically_independent_pit_attested": False,
                "aics_node_score": None,
            })
        else:
            if len(tags[OCF])>1 or len(tags[CAPEX])>1 or len(source_ids)>1:
                status = "ambiguous_multiple_values_or_source"
            blocked.append({
                "issuer_cik": group[0], "accession": group[1],
                "period_end": group[3], "reason": status,
            })
        counts[status] += 1
    # Even a direct accounting pair from a current SEC API is NOT proof that
    # those exact bytes were in the first-filed document at historical as-of.
    return {
        "schema": "aics-sec-direct-three-month-cashflow-research-candidate-v1",
        "as_of": as_of.isoformat(), "original_numeric_rows_inspected": len(raw_rows),
        "reasons": dict(sorted(counts.items())),
        "direct_original_3month_pair_candidates": len(paired),
        "blocked_period_or_source_candidates": len(blocked),
        "candidate_quarter_pairs": paired, "blocked_quarter_groups": blocked,
        "no_ytd_subtraction_automatically": True,
        "no_mixed_issuer_scope_or_accession": True,
        "no_future_economic_period_or_filing": True,
        "source_bytes_historical_first_filing_verified": False,
        "independently_pit_attested": False,
        "node_scores_promoted": 0,
        "full_11_node_aics": None,
        "production_weights_changed": False,
        "trades_created": False,
        "weights_total": sum(WEIGHTS.values()),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path,default=INPUT)
    p.add_argument("--out",type=Path,default=OUTPUT)
    p.add_argument("--as-of",default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    args = p.parse_args()
    result=audit(json.loads(args.input.read_text()),as_of=args.as_of)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({
        "numeric_rows":result["original_numeric_rows_inspected"],
        "cashflow_quarter_pairs":result["direct_original_3month_pair_candidates"],
        "blocked_groups":result["blocked_period_or_source_candidates"],
        "long_ytd_not_used":result["reasons"].get("long_ytd_or_nonquarter_duration",0),
        "full_aics":None,
    }))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
