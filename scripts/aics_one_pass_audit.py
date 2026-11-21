"""One-command evidence audit: execute local independent audit with explicit inputs.

Requires externally downloaded real GitHub Actions ZIP and original reconciliation JSON.
Never fetches, backfills or synthesizes missing data.
"""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import zipfile
from collections import Counter
from pathlib import Path

SERIES={"DGS30","SOFR","BAMLH0A0HYM2","BAMLH0A3HYC"}
WEIGHTS={"private_credit":150,"insurers":125,"ust_30y":125,"neoclouds":100,"ai_equities":100,"hyperscalers":100,"spv":100,"repo":100,"power_dc":50,"semis_supply":50,"ai_demand":50}

def audit(artifact,reconciliation):
    gates={}; series={}
    def check(name,condition): gates[name]=bool(condition)
    check("01_fixed_weights",len(WEIGHTS)==11 and sum(WEIGHTS.values())==1050)
    with zipfile.ZipFile(artifact) as z:
        manifest=json.loads(z.read("manifest.json")); quality=json.loads(z.read("quality_report.json")); coverage=json.loads(z.read("coverage_report.json")); items=manifest.get("results",[])
        check("02_four_distinct_alfred_series",len(items)==4 and {r.get("series_id") for r in items}==SERIES)
        check("03_manifest_fail_closed",manifest.get("verified_pit") is False and manifest.get("publishable") is False and manifest.get("index_aics") is None)
        check("04_quality_fail_closed",quality.get("structurally_valid") is True and not quality.get("errors") and quality.get("independently_verified_pit") is False)
        check("05_coverage_fail_closed",coverage.get("historical_snapshot_coverage_complete") is True and coverage.get("promotion")=="BLOCKED" and coverage.get("independently_verified_pit") is False)
        ok_hash=ok_dates=ok_rows=ok_unique=ok_chronology=True
        for item in items:
            sid=item["series_id"]; raw=z.read(f"alfred_asof_{sid}.csv"); rows=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
            ok_hash &= hashlib.sha256(raw).hexdigest()==item.get("sha256")
            ok_rows &= len(rows)==item.get("rows")
            snapshots=item.get("snapshots",[]); counts=Counter(r["as_of"] for r in rows)
            ok_dates &= len(snapshots)==24 and len(counts)==24 and all(s.get("status")=="downloaded_unverified" and counts[s["as_of"]]==s["rows"] for s in snapshots)
            seen=set()
            for row in rows:
                key=(row["as_of"],row["observation_date"])
                if key in seen: ok_unique=False
                seen.add(key)
                try:
                    a=dt.date.fromisoformat(row["as_of"]); observed=dt.date.fromisoformat(row["observation_date"]); start=dt.date.fromisoformat(row["realtime_start"]); end=dt.date.fromisoformat(row["realtime_end"]); value=float(row["value"])
                    ok_chronology &= observed<=a and start<=a<=end and math.isfinite(value) and row["series_id"]==sid and row["source"]=="ALFRED_AS_OF" and row["verified_pit"].lower()=="false"
                except (KeyError,ValueError): ok_chronology=False
            series[sid]={"rows":len(rows),"snapshots":len(counts),"sha256":hashlib.sha256(raw).hexdigest()}
        check("06_csv_sha256_match",ok_hash);check("07_monthly_snapshot_coverage",ok_dates);check("08_manifest_row_counts",ok_rows);check("09_no_duplicate_observations",ok_unique);check("10_asof_chronology",ok_chronology)
    rec=json.loads(Path(reconciliation).read_text(encoding="utf-8"));nodes={n["node"]:n for n in rec.get("nodes",[])}
    check("11_original_weight_coverage",rec.get("total_weight")==1050 and rec.get("covered_weight")==250 and len(nodes)==11 and all(nodes[k]["weight"]==w for k,w in WEIGHTS.items()))
    check("12_original_proxy_only",sum(n["observations"] for n in nodes.values())==rec.get("eligible_rows")==6 and {k for k,n in nodes.items() if n["observations"]>0}=={"private_credit","neoclouds"} and all(n["status"]=="PROXY_UNVERIFIED" for n in nodes.values() if n["observations"]>0))
    check("13_sec_future_exclusion",len(rec.get("excluded_future",[]))==3 and all(dt.date.fromisoformat(x["available_at"])>dt.date.fromisoformat(rec["as_of"]) for x in rec["excluded_future"]))
    check("14_no_index_from_partial_coverage",rec.get("index_aics") is None and rec.get("predictive_model_score") is None and rec.get("publishable") is False)
    check("15_external_verification_not_claimed",rec.get("external_verification",{}).get("fred_alfred_vintages")=="not_verified" and rec.get("external_verification",{}).get("sec_edgar_filings")=="not_verified")
    return {"gates":gates,"passed":sum(gates.values()),"total":len(gates),"failed":[k for k,v in gates.items() if not v],"series":series,"original_weight_coverage_pct":rec.get("weighted_coverage_pct"),"original_eligible_rows":rec.get("eligible_rows"),"artifact_sha256":hashlib.sha256(Path(artifact).read_bytes()).hexdigest(),"claimed_646_3":"UNREPRODUCED","claimed_650_7":"UNREPRODUCED","independent_source_verification":False,"index_aics":None,"model_score":None,"promotion":"BLOCKED","trades_created":False}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--artifact",required=True);p.add_argument("--reconciliation",required=True);p.add_argument("--out",required=True);a=p.parse_args();result=audit(a.artifact,a.reconciliation);Path(a.out).write_text(json.dumps(result,indent=2)+"\n");print(json.dumps({"passed":result["passed"],"total":result["total"],"failed":result["failed"]}));raise SystemExit(bool(result["failed"]))
