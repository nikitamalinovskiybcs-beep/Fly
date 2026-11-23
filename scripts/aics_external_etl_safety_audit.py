#!/usr/bin/env python3
"""Safety validation for externally supplied 11-node ETL. No score certification."""
import ast
import argparse
from pathlib import Path

REQUIRED=("SEC_USER_AGENT","FRED_API_KEY","EIA_API_KEY")
def audit_source(path):
    source=Path(path).read_text(encoding="utf-8")
    ast.parse(source)
    issues=[]
    if '"realtime_start": start_date' in source and '"realtime_end": as_of_date' in source:
        issues.append("ALFRED_RANGE_NOT_SINGLE_ASOF_VINTAGE")
    if 'obs_dt + timedelta(days=60)' in source:
        issues.append("EIA_ASSUMED_PUBLICATION_DATE")
    if 'groupby("observation_date")["value"].mean()' in source:
        issues.append("MIXED_UNIT_NODE_NORMALIZATION")
    if 'node_scores[node_name] = compute_node_score_pit(' in source:
        issues.append("UNVERIFIED_SOURCE_AUTO_PROMOTED_TO_NODE_SCORE")
    if 'lines.startswith(' in source:
        issues.append("STOOQ_CSV_HEADER_TYPE_BUG")
    if 'QuantRiskHub Research audit@quantriskhub.local' in source:
        issues.append("PLACEHOLDER_SEC_USER_AGENT")
    return issues

def main():
    p=argparse.ArgumentParser()
    p.add_argument("source",help="Path to supplied ETL script")
    args=p.parse_args()
    issues=audit_source(args.source)
    for issue in issues:print("BLOCKED:",issue)
    print("PIT_SCORE_PROMOTION:", "BLOCKED" if issues else "REQUIRES_INDEPENDENT_VERIFICATION")
    raise SystemExit(2 if issues else 0)

if __name__=="__main__":main()
