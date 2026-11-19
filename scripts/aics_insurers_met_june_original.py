#!/usr/bin/env python3
"""AICS Insurers: original MET June 2026 10-Q and its real mortgage ACL rollforward.

Research as-of 2026-11-19. MET September Q3 is still under SEC filed+14 embargo.
This is *not* a source-vintage attestation, independent PIT or 0-100 stress score.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from urllib.request import Request, urlopen

from scripts.aics_observed_source_review import words

AS_OF = dt.date(2026, 11, 19)
CIK = "1099219"
ACCESSION = "0001099219-26-000050"
FILED = dt.date(2026, 8, 6)
DOC = "met-20260630.htm"
URL = ("https://www.sec.gov/Archives/edgar/data/1099219/"
       "000109921926000050/0001099219-26-000050.txt")
MAX_BYTES = 50_000_000
OUTPUT = Path("aics_data/source_evidence/insurers_met_june_original")

BALANCE = re.compile(
    r"Mortgage loans \(net of allowance for credit loss of \$\s*([\d,]+)\s+"
    r"and \$\s*([\d,]+)\s*,\s*respectively; includes \$\s*([\d,]+)\s+"
    r"and \$\s*([\d,]+)\s*,\s*respectively, of mortgage loans held-for-sale\)"
    r"\s*\$?\s*([\d,]+)\s*\$?\s*([\d,]+)", re.I
)
# Real SEC iXBRL text presents parenthesized negatives as '( 33 )'.
ROW = re.compile(r"\(\s*\d[\d,]*\s*\)|-?\d[\d,]*")

def check_cutoff(as_of: dt.date):
    if as_of != AS_OF:
        raise ValueError("Only exact frozen 2026-11-19 research as-of permitted")
    if FILED + dt.timedelta(days=14) > as_of:
        raise ValueError("MET June filing violates SEC+14")
    if dt.date(2026, 11, 6) + dt.timedelta(days=14) <= as_of:
        raise ValueError("MET September Q3 embargo accidentally lifted")

def source_metadata(raw: bytes) -> tuple[bytes,str]:
    if not isinstance(raw,bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Missing or oversized original MET complete SEC submission")
    header,delimiter,_ = raw.partition(b"<DOCUMENT>")
    if not delimiter or not header.startswith(b"<SEC-DOCUMENT>"):
        raise ValueError("Original SEC envelope absent")
    def metadata(key):
        m=re.findall(rb"(?m)^\s*"+re.escape(key.encode())+rb":\s*([^\r\n]+)",header)
        if len(m)!=1:
            raise ValueError("Missing or conflicting SEC filing identity: "+key)
        return m[0].decode("ascii",errors="replace").strip()
    if (metadata("ACCESSION NUMBER") != ACCESSION
        or metadata("CONFORMED SUBMISSION TYPE") != "10-Q"
        or metadata("FILED AS OF DATE") != "20260806"
        or int(metadata("CENTRAL INDEX KEY")) != int(CIK)):
        raise ValueError("Original MET issuer/date/accession/form mismatch")
    selected=[]
    for segment in raw.split(b"<DOCUMENT>")[1:]:
        info,sep,rest=segment.partition(b"<TEXT>")
        if not sep or (b"<FILENAME>"+DOC.encode()) not in info.splitlines():
            continue
        if b"<TYPE>10-Q" not in info.splitlines():
            raise ValueError("Selected MET primary filing document wrong form")
        body,end,_=rest.partition(b"</TEXT>")
        if not end:
            raise ValueError("Incomplete original MET document")
        selected.append(body)
    if len(selected)!=1:
        raise ValueError("Duplicate or missing MET primary filing document")
    return selected[0],hashlib.sha256(selected[0]).hexdigest()

def number(v:str)->int:
    v=v.strip()
    if v.startswith("(") and v.endswith(")"):
        return -int(v[1:-1].replace(",","").strip())
    return int(v.replace(",",""))

def pct(a:int,b:int)->str:
    if b <= 0: raise ValueError("Nonpositive financial base")
    return str((Decimal(a)*100/Decimal(b)).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))

def parse_met_primary(primary:bytes)->dict:
    text=words(primary)
    matches=list(BALANCE.finditer(text))
    if len(matches)!=1:
        raise ValueError("Missing/ambiguous MET mortgage balance-sheet and ACL disclosure")
    acl,prev_acl,hfs,prev_hfs,net,prev_net=map(number,matches[0].groups())
    if (acl,prev_acl,hfs,prev_hfs,net,prev_net)!=(1358,1193,0,35,82856,84593):
        raise ValueError("Original MET mortgage amounts differ from source-reviewed 10-Q")
    # Rollforward is a distinct note, not inferred from the balance-sheet line.
    heading="Rollforward of ACL for Mortgage Loans by Portfolio Segment"
    positions=[m.start() for m in re.finditer(re.escape(heading),text)]
    if len(positions)!=1: raise ValueError("Missing/duplicate MET rollforward heading")
    snippet=text[positions[0]:positions[0]+4000]
    def row_between(start,end):
        a=snippet.find(start)
        bb=snippet.find(end,a+len(start))
        if a<0 or bb<0 or bb<=a:
            raise ValueError("Missing MET separate credit allowance rollforward row")
        vals=[number(m.group()) for m in ROW.finditer(snippet[a+len(start):bb])]
        if len(vals)<4: raise ValueError("Truncated MET credit allowance rollforward")
        return vals[:4]
    start=row_between("Balance, beginning of period","Provision (release)")
    provision=row_between("Provision (release)","Charge-offs, net of recoveries")
    end=row_between("Balance, end of period","The gross charge-offs")
    if (start,provision,end)!=([807,115,271,1193],[348,1,-33,316],
                               [1016,107,235,1358]):
        raise ValueError("MET segment balance or allowance movements changed")
    if (sum(start[:3])!=start[3] or sum(provision[:3])!=provision[3]
            or sum(end[:3])!=end[3]
            or start[3]+provision[3]-151!=end[3]):
        raise ValueError("MET ACL rollforward does not reconcile")
    return {
        "observation_dates":["2025-12-31","2026-06-30"],
        "units":"USD millions, except percentages",
        "mortgage_loans_net_millions":{"2025-12-31":prev_net,"2026-06-30":net},
        "mortgage_loans_held_for_sale_included_millions":
            {"2025-12-31":prev_hfs,"2026-06-30":hfs},
        "mortgage_loan_acl_millions":{"2025-12-31":prev_acl,"2026-06-30":acl},
        "mortgage_loans_net_change_millions":net-prev_net,
        "mortgage_loans_net_change_pct":pct(net-prev_net,prev_net),
        "mortgage_acl_change_millions":acl-prev_acl,
        "mortgage_acl_change_pct":pct(acl-prev_acl,prev_acl),
        "acl_over_net_loans_plus_acl_proxy_pct":
            {"2025-12-31":pct(prev_acl,prev_net+prev_acl),
             "2026-06-30":pct(acl,net+acl)},
        "acl_segment_begin_millions":{
            "commercial":start[0],"agricultural":start[1],
            "residential":start[2],"total":start[3]},
        "acl_segment_six_month_provision_millions":{
            "commercial":provision[0],"agricultural":provision[1],
            "residential":provision[2],"total":provision[3]},
        "acl_segment_end_millions":{
            "commercial":end[0],"agricultural":end[1],
            "residential":end[2],"total":end[3]},
        "net_six_month_chargeoffs_millions":151,
        "commercial_acl_share_of_total_pct":pct(end[0],end[3]),
        "private_credit_or_ai_exposure_usd":None,
        "naic_rbc_ratio":None,"historical_pit_verified":False,
        "caveat":"MET mortgage loans include multiple segments and some held-for-sale assets; ACL/net-plus-ACL is an arithmetic proxy, not a comparable PRU reserve-risk ratio.",
    }

def build(raw:bytes,as_of:dt.date=AS_OF)->dict:
    check_cutoff(as_of)
    primary,primary_sha=source_metadata(raw)
    facts=parse_met_primary(primary)
    return {
        "schema_version":"aics-met-2026q2-original-mortgage-credit-v1",
        "node":"Insurers","as_of":as_of.isoformat(),
        "issuer":"MetLife, Inc.","cik":CIK,"form":"10-Q",
        "sec_accession":ACCESSION,"original_sec_url":URL,
        "filed_at":FILED.isoformat(),"sec_available_at":"2026-08-20",
        "period_end":"2026-06-30","original_full_submission_bytes":len(raw),
        "original_full_submission_sha256":hashlib.sha256(raw).hexdigest(),
        "embedded_primary_10q_sha256":primary_sha,
        "facts":facts,
        "met_september_q3_filed_at":"2026-11-06",
        "met_september_q3_available_at":"2026-11-20",
        "met_september_q3_metrics_used":False,
        "met_september_q3_balance_usd":None,
        "observed_pru_june_balances_added_or_directly_compared":False,
        "retrospective_archive_not_historical_delivery_proof":True,
        "independent_historical_pit_attested":False,
        "untouched_24_month_oos":False,
        "insurers_node_score":None,"index_aics":None,
        "promotion":"BLOCKED","trades_created":False,
    }

def fetch(contact:str,opener=urlopen)->bytes:
    if not contact or len(contact)<15 or "@" not in contact or "example." in contact.lower():
        raise ValueError("Accountable SEC User-Agent contact required")
    request=Request(URL,headers={"User-Agent":contact,"Accept":"text/plain"})
    with opener(request,timeout=70) as response:
        if response.geturl()!=URL:
            raise ValueError("Unexpected source redirect")
        raw=response.read(MAX_BYTES+1)
    if not raw or len(raw)>MAX_BYTES:
        raise ValueError("SEC original payload missing or oversized")
    return raw

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,default=OUTPUT)
    ap.add_argument("--as-of",type=dt.date.fromisoformat,default=AS_OF)
    ap.add_argument("--verify-existing",action="store_true")
    x=ap.parse_args()
    try:
        if x.verify_existing:
            raw=(x.out/"met_q2_original_full_submission.txt").read_bytes()
        else:
            raw=fetch(os.getenv("AICS_SEC_USER_AGENT") or os.getenv("EDGAR_IDENTITY")
                      or os.getenv("SEC_USER_AGENT") or "")
        # Preserve original SEC bytes even if the strict extraction fails.
        # An unsuccessful parse must not destroy the primary audit evidence.
        x.out.mkdir(parents=True,exist_ok=True)
        if not x.verify_existing:
            (x.out/"met_q2_original_full_submission.txt").write_bytes(raw)
        result=build(raw,x.as_of)
        (x.out/"research.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print(json.dumps({"promotion":"BLOCKED","reason":type(exc).__name__,
                          "detail":str(exc)[:140]}))
        return 2
    print(json.dumps({"met_mortgage_loans_net_june_millions":result["facts"]["mortgage_loans_net_millions"]["2026-06-30"],
                      "met_mortgage_acl_june_millions":result["facts"]["mortgage_loan_acl_millions"]["2026-06-30"],
                      "met_september_q3_blocked":not result["met_september_q3_metrics_used"],
                      "node_score":None,"index_aics":None,"promotion":"BLOCKED"}))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
