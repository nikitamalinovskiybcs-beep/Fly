"""Compute observed 24-month market spreads next to incomplete research AICS.

This does NOT produce 24 monthly AICS levels. It computes two distinct
SPX/NDX relative-price spreads and the genuine repo SOFR-IORB spread.
Missing 11-node AICS and AICS-SPX spread remain null, never zero-filled.
Run from repository root: python -m scripts.aics_24m_market_spreads
"""
import json
from decimal import Decimal
from pathlib import Path

ROOT = Path("aics_data/research")
NDX = ROOT / "nasdaq100_24_month_closes_2026-11-21.json"
SPX = ROOT / "sp500_24_month_closes_2026-11-21.json"
COVERAGE = ROOT / "aics_24_month_no_multiplier_coverage_2026-11-21.json"
OUTPUT = ROOT / "aics_24m_benchmark_spreads_2026-11-21.json"

def load(p):
    return json.loads(p.read_text(encoding="utf-8"))

def dec(x):
    if isinstance(x, bool):
        raise ValueError("Boolean input is not a price")
    value = Decimal(str(x))
    if not value.is_finite():
        raise ValueError("Nonfinite observed value")
    return value

def num(x):
    return float(round(dec(x),4))

def calculate(ndx=None, spx=None, coverage=None):
    ndx=ndx if ndx is not None else load(NDX)
    spx=spx if spx is not None else load(SPX)
    coverage=coverage if coverage is not None else load(COVERAGE)
    if (ndx.get("schema")!="aics-ndx24-observed-monthly-benchmark-v1"
            or ndx.get("independently_contemporaneous_pit_attested") is not False
            or spx.get("schema")!="aics-sp500-24-month-observed-price-source-v1"
            or spx.get("independent_pit_verified") is not False
            or coverage.get("node_weights_total")!=1050
            or coverage.get("new_11_node_full_aics_months")!=0
            or coverage.get("new_11_node_sp500_spread_months")!=0
            or len(ndx["points"])!=24 or len(spx["points"])!=24 or len(coverage["monthly"])!=24):
        raise ValueError("Invalid source or independent-PIT claim")
    names=[row["month"] for row in ndx["points"]]
    if (names[0]!="2024-11" or names[-1]!="2026-10"
            or len(names)!=len(set(names))
            or names!=[r["month"] for r in spx["points"]]
            or names!=[r["month"] for r in coverage["monthly"]]):
        raise ValueError("Historical benchmark months misaligned")
    nd=[dec(x["ndx_month_end_close"]) for x in ndx["points"]]
    sp=[dec(x["sp500_month_end_close"]) for x in spx["points"]]
    if min(nd)<=0 or min(sp)<=0:
        raise ValueError("Non-positive benchmark close")
    output=[]
    for i,(name,a) in enumerate(zip(names,coverage["monthly"])):
        if (a["full_11_node_aics_no_multiplier"] is not None
                or a["aics_sp500_normalized_spread"] is not None):
            raise ValueError("Complete AICS incorrectly promoted from missing nodes")
        if a["known_node_count_research_only"]>11 or a["known_node_count_research_only"]<0:
            raise ValueError("Invalid score coverage")
        monthly_nd=(100*(nd[i]/nd[i-1]-1) if i else None)
        monthly_sp=(100*(sp[i]/sp[i-1]-1) if i else None)
        monthly_spread=(monthly_nd-monthly_sp if i else None)
        cum_spread=100*(nd[i]/nd[0]-sp[i]/sp[0])
        output.append({
            "month":name,
            "nasdaq100_close":num(nd[i]),"sp500_close":num(sp[i]),
            "ndx_base100":num(100*nd[i]/nd[0]),
            "spx_base100":num(100*sp[i]/sp[0]),
            "ndx_month_return_pct":num(monthly_nd) if i else None,
            "spx_month_return_pct":num(monthly_sp) if i else None,
            "ndx_minus_spx_monthly_return_pp":num(monthly_spread) if i else None,
            "ndx_minus_spx_cumulative_base100_pp":num(cum_spread),
            "repo_sofr_minus_iorb_bp":a["repo_sofr_minus_iorb_bp"],
            "ust30_volatility_bp":num(a["ust30_20_change_volatility_bp"]),
            "research_only_eligible_node_count":a["known_node_count_research_only"],
            "research_only_partial_weighted_points_not_aics":(
                num(a["partial_known_weighted_points_not_aics"])
                if a["partial_known_weighted_points_not_aics"] is not None else None),
            "full_historical_aics_no_multiplier":None,
            "full_historical_aics_sp500_spread":None,
            "certified_historical_pit":False
        })
    return output

def main():
    expected=load(OUTPUT)
    actual=calculate()
    if len(actual)!=len(expected["rows"]):
        raise ValueError("Dated benchmark receipt row count changed")
    for i,(a,b) in enumerate(zip(actual,expected["rows"])):
        for k,val in a.items():
            rhs=b[k]
            if (isinstance(val,(float,int)) and not isinstance(val,bool)
                    and isinstance(rhs,(float,int)) and not isinstance(rhs,bool)):
                if abs(float(val)-float(rhs))>0.00011:
                    raise ValueError(f"Mismatch {i} {k}")
            elif val!=rhs:
                raise ValueError(f"Mismatch {i} {k}")
    print(json.dumps({"months":24,"oct2026":actual[-1],"full_aics":None,
                      "historical_aics_sp500_spread":None},indent=2))

if __name__ == "__main__":
    main()
