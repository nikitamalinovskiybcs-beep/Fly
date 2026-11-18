#!/usr/bin/env python3
"""Collect actual SEC companyfacts with filing-time embargo; research-only."""
import datetime as dt
import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

OUT = Path("aics_data/xbrl")
OUT.mkdir(parents=True, exist_ok=True)
AS_OF = dt.date.today()
CIKS = {"NVDA":"0001045810","MSFT":"0000789019","AMZN":"0001018724",
        "GOOGL":"0001652044","META":"0001326801","ORCL":"0001341439"}
TAGS = ("Revenues","RevenueFromContractWithCustomerExcludingAssessedTax",
        "NetIncomeLoss","OperatingIncomeLoss",
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "CashAndCashEquivalentsAtCarryingValue","LongTermDebtNoncurrent")
identity = os.getenv("EDGAR_IDENTITY","").strip()
results = []
for ticker,cik in CIKS.items():
    if not identity:
        results.append({"ticker":ticker,"status":"missing_secret"})
        continue
    try:
        request=Request(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                        headers={"User-Agent":identity,"Accept":"application/json"})
        for attempt in range(3):
            try:
                with urlopen(request,timeout=60) as response:
                    payload=json.load(response)
                break
            except HTTPError as exc:
                if exc.code != 429 or attempt == 2:
                    raise
                time.sleep((attempt + 1) * 10)
        if str(payload.get("cik","")).lstrip("0") != str(int(cik)):
            raise ValueError("SEC companyfacts CIK does not match requested company")
        facts=[]
        for tag in TAGS:
            item=payload.get("facts",{}).get("us-gaap",{}).get(tag,{})
            for unit,observations in item.get("units",{}).items():
                for o in observations:
                    if o.get("form") not in ("10-K","10-Q") or not o.get("filed"):
                        continue
                    filed=dt.date.fromisoformat(o["filed"])
                    available=filed+dt.timedelta(days=14)
                    if available>AS_OF:
                        continue
                    if not o.get("accn") or not o.get("end"):
                        continue
                    facts.append({"ticker":ticker,"cik":cik,"taxonomy":"us-gaap",
                                  "xbrl_tag":tag,"unit":unit,"value":o["val"],
                                  "period_start":o.get("start"),"period_end":o.get("end"),
                                  "filed_at":filed.isoformat(),
                                  "available_at":available.isoformat(),
                                  "accession_number":o.get("accn"),"form":o["form"],
                                  "frame":o.get("frame"),"verified_pit":False})
        path=OUT/f"sec_xbrl_{ticker}.json"
        path.write_text(json.dumps(facts,ensure_ascii=False),encoding="utf-8")
        results.append({"ticker":ticker,"status":"downloaded_unverified",
                        "facts":len(facts),"tags":len(TAGS),
                        "matched_tags":len({f["xbrl_tag"] for f in facts})})
    except (HTTPError,URLError,TimeoutError,ValueError,KeyError) as e:
        results.append({"ticker":ticker,"status":"error","error":type(e).__name__,
                        "http_status":e.code if isinstance(e,HTTPError) else None})
manifest={"as_of":AS_OF.isoformat(),"source":"SEC companyfacts","results":results,
          "verified_pit":False,"index_aics":None,"model_score":None,
          "publishable":False,"note":"Facts retain filing-date embargo but require independent PIT validation."}
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print(json.dumps(manifest,indent=2))
if any(r["status"]!="downloaded_unverified" for r in results):
    raise SystemExit("SEC XBRL collection incomplete")
