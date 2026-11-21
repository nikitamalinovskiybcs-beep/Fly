"""Reconstruct 24 first-available G.17 NAICS 3344 releases (not current revised FRED).

Every value comes from a dated original Federal Reserve G.17 HTML release,
with the observation month strictly separate from public-release month.
2025 autumn shutdown delays prevent Oct/Nov lookahead. Research-only; no
original-byte rehash or independent historical source-capture certificate.
"""
import calendar
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path

INPUT = Path("aics_data/research/fed_g17_naics3344_24_month_original_release_2026-11-21.json")
LATE = {"2025-09":"2025-12-03","2025-10":"2025-12-23","2025-11":"2025-12-23"}
NAICS = "3344"


def previous_month(x):
    y, m = map(int,x.split("-"))
    return f"{y if m>1 else y-1}-{m-1 if m>1 else 12:02d}"


def month_end(month):
    y,m=map(int,month.split("-"))
    return dt.date(y,m,calendar.monthrange(y,m)[1])


def read(data=None):
    data=data if data is not None else json.loads(INPUT.read_text(encoding="utf-8"))
    if (data.get("schema")!="aics-g17-naics3344-first-release-monthly-24-v1"
            or data.get("node")!="Semiconductors Supply"
            or data.get("node_weight")!=50
            or data.get("observed_months")!=24
            or data.get("hot_node_multiplier_applied") is not False
            or data.get("independent_historical_pit_certified") is not False
            or data.get("independent_oos_24m") is not False
            or data.get("official_index_rule_modified") is not False
            or data.get("certified_aics") is not None
            or data.get("trades_created") is not False):
        raise ValueError("Research source improperly promoted or incomplete")
    records=data["observations"]
    if len(records)!=24:
        raise ValueError("Expected 24 source-month events")
    result=[]
    for i,row in enumerate(records):
        month=row.get("observation_month")
        expected=month_end("2024-11")
        # Validate an unbroken month sequence without ever manufacturing a value.
        yy=2024+(10+i)//12
        mm=(10+i)%12+1
        if month!=f"{yy}-{mm:02d}":
            raise ValueError("G17 observation date sequence mismatched")
        released=dt.date.fromisoformat(row["official_release_date"])
        obs_end=month_end(month)
        if (released<=obs_end or
                row.get("asof_eligible_from")!=released.isoformat() or
                row.get("naics_code")!=NAICS):
            raise ValueError("Source released before observation end or chronology mismatch")
        if month in LATE:
            if row["official_release_date"]!=LATE[month]:
                raise ValueError("Government shutdown releases cannot be backdated")
        elif previous_month(released.strftime("%Y-%m"))!=month:
            raise ValueError("Non-first-month release without original exception")
        table="table7" if month in ("2025-10","2025-11") else "table2_sup"
        url=("https://www.federalreserve.gov/releases/g17/"+
             released.strftime("%Y%m%d")+"/"+table+".htm")
        if (row.get("source_url")!=url
                or row.get("original_bytes_sha256") is not None
                or row.get("independent_historical_pit_attested") is not False
                or (table=="table7")!=("Table 7" in row.get("source_table",""))):
            raise ValueError("Original date-specific Fed source receipt invalid")
        score=Decimal(row["initially_observed_utilization_pct"])
        if not score.is_finite() or not 0<=score<=100:
            raise ValueError("Fed observation out of range")
        result.append({
            "observation_month":month,"available_at":released.isoformat(),
            "score":f"{score:.2f}","source_url":url,
            "source_receipt":str(INPUT),
            "historically_pit_certified":False,
            "observation_first_published":True
        })
    if (result[0]["observation_month"]!="2024-11"
            or result[-1]["observation_month"]!="2026-10"
            or result[-1]["score"]!="74.40"):
        raise ValueError("G17 24-month history ended incorrectly")
    return result


if __name__=="__main__":
    print(json.dumps(read(),ensure_ascii=False,indent=2))
