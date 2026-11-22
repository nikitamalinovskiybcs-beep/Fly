"""AICS PIT100: ONE HUNDRED DISTINCT genuine SEC first-filed report fetches.

Allocates 100 specific EDGAR primary filings across verified SEC issuer
submissions already archived by the 10 source-wave agents. Each successful
download is independently byte-hashed, gzip archived, dated and linked to
the original accession. Any failed/oversized URL is recorded as failure.

These are 100 autonomous download TASKS, not 100 independently trained LLMs
or 100 historical contemporaneous first-receipt proofs. SEC API acceptance
timestamps retrieved TODAY are historical metadata, not old provider bytes.
No fabricated records, synthetic time series, scoring or trades.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen

from scripts.aics_ten_node_agents import SEC_CIK
from scripts.aics_score_reproducibility_gate import WEIGHTS

RUN=Path("aics_data/agent_runs/ten_real_collection_rounds")
INPUT=RUN/"ten_rounds_manifest.json"
OUT=RUN/"aics_pit100_100_original_sec_reports_manifest.json"
RAW=RUN/"pit100_original_sec_reports_raw"
N=100
DATE_MIN="2024-10-01"
MAX_DOC_BYTES=8_000_000
MAX_ARCHIVED_GZIP_BYTES=85_000_000
ACCESSION=re.compile(r"^\d{10}-\d{2}-\d{6}$")
PRIMARY=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,200}\.(?:htm|html|txt|xml)$",re.I)
ACCEPTANCE=re.compile(r"^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)?$")
FORMS={"10-K","10-Q","8-K","6-K","S-1","S-1/A","20-F","10-K/A","10-Q/A"}
SEC_HEADER="https://www.sec.gov/Archives/edgar/data/"


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def is_valid_doc(name):
    return (isinstance(name,str) and PRIMARY.fullmatch(name)
            and "/" not in name and "\\" not in name and ".." not in name)


def parse_submissions(raw,*,source_id,cik,as_of):
    if not isinstance(raw,bytes) or not 100<len(raw)<=16_000_000:
        raise ValueError("No valid original current SEC submissions bytes")
    j=json.loads(raw)
    if int(j.get("cik",-1))!=int(cik):
        raise ValueError("SEC original CIK does not match requested issuer")
    f=j.get("filings",{}).get("recent",{})
    keys=("accessionNumber","primaryDocument","filingDate","form","acceptanceDateTime")
    if not all(isinstance(f.get(k),list) for k in keys):
        raise ValueError("SEC submissions recent filing tables missing")
    lengths=[len(f[k]) for k in keys]
    if len(set(lengths))!=1:raise ValueError("SEC fields misaligned across filings")
    out=[]
    for acc,doc,filing,form,accept in zip(*(f[k] for k in keys)):
        if (form not in FORMS or not isinstance(filing,str)
            or not DATE_MIN<=filing<=as_of
            or not isinstance(acc,str) or not ACCESSION.fullmatch(acc)
            or not is_valid_doc(doc)):
            continue
        if not isinstance(accept,str) or not ACCEPTANCE.fullmatch(accept):
            # Cannot invent acceptance times for SEC records with missing data.
            accept=None
        url=SEC_HEADER+f"{int(cik)}/{acc.replace('-','')}/{doc}"
        out.append({
            "source_id":source_id,
            "CIK":str(int(cik)),
            "accession":acc,
            "report_primary_document":doc,
            "form":form,
            "filed_at":filing,
            "edgar_acceptance_time_current_registry_field":accept,
            "source_url":url,
        })
    periodic=sorted((x for x in out if x["form"] in ("10-Q","10-K","10-Q/A","10-K/A")),
                    key=lambda x:(x["filed_at"],x["accession"]),reverse=True)
    other=sorted((x for x in out if x["form"] not in ("10-Q","10-K","10-Q/A","10-K/A")),
                 key=lambda x:(x["filed_at"],x["accession"]),reverse=True)
    # Include quarterly/annual primary filings AND event-driven 8-K or 6-K
    # to avoid a redundant 100-report selection dominated by one form.
    return periodic[:4]+other[:3]+periodic[4:]+other[3:]


def submissions_from_archived_waves(waves):
    if (waves.get("schema")!="aics-ten-real-source-acquisition-waves-with-companyfacts-v1"
        or waves.get("source_agents")!=10
        or waves.get("fixed_weights_total")!=1050
        or waves.get("complete_index") is not None
        or waves.get("independently_pit_verified_node_count")!=0
        or sum(WEIGHTS.values())!=1050):
        raise ValueError("Live source wave provenance not valid")
    items={}
    for wave in waves["rounds_report"]:
        for op in wave["operations"]:
            key=op["source_id"]
            if key not in SEC_CIK or op["status"]!="original_archived_no_pit":
                continue
            if key in items:continue
            p=Path(op["raw_path"])
            if not p.exists() or p.stat().st_size!=op["original_bytes"]:
                raise ValueError("Archived EDGAR submissions response not found")
            raw=p.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=op["raw_sha256"]:
                raise ValueError("SEC submissions bytes changed after original archive")
            records=parse_submissions(raw,source_id=key,cik=SEC_CIK[key],
                                      as_of=waves["captured_at_utc"][:10])
            items[key]=records
    if len(items)<12:
        raise ValueError("Insufficient genuinely captured SEC issuers for 100 distinct filings")
    return items


def select_targets(by_source,*,count=N):
    if count!=100:raise ValueError("Exactly 100 source acquisition assignments are required")
    by={k:list(v) for k,v in by_source.items()}
    chosen=[];seen=set()
    for i in range(250):
        progressed=False
        for key in sorted(by):
            if not by[key]:continue
            rec=by[key].pop(0)
            if rec["source_id"]!=key or not rec["source_url"].startswith(SEC_HEADER):
                raise ValueError("Official SEC accession chain not validated")
            acckey=(rec["CIK"],rec["accession"])
            if acckey in seen:continue
            if not is_valid_doc(rec["report_primary_document"]):
                raise ValueError("Unsafe SEC document basename")
            seen.add(acckey)
            chosen.append(rec)
            progressed=True
            if len(chosen)==count:
                return [{**x,"download_worker_id":f"SECOriginalPITWorker_{n:03d}",
                         "download_task_no":n}
                        for n,x in enumerate(chosen,1)]
        if not progressed:break
    raise ValueError(f"Only {len(chosen)} distinct real SEC reports available; required 100")


def request_original(url,contact):
    if not isinstance(url,str) or not url.startswith(SEC_HEADER):
        raise ValueError("Original SEC archive domain required")
    req=Request(url,headers={"User-Agent":contact,"Accept":"text/html,text/plain,application/xml"})
    with urlopen(req,timeout=11) as res:
        if res.geturl()!=url:
            raise ValueError("Unexpected SEC original redirect")
        raw=res.read(MAX_DOC_BYTES+1)
    if len(raw)<100 or len(raw)>MAX_DOC_BYTES:
        raise ValueError("Original primary SEC report empty or exceeds byte guard")
    if b"access denied" in raw[:4096].lower() or b"request rate threshold" in raw[:4096].lower():
        raise ValueError("SEC request blocked, not a real report")
    return raw


def collect(*,waves,as_of,contact,out=OUT,rawdir=RAW,fetcher=None,sleeper=None):
    if isinstance(as_of,dt.date):as_of=as_of.isoformat()
    if not re.fullmatch(r"20\d\d-\d\d-\d\d",as_of):
        raise ValueError("Explicit as-of YYYY-MM-DD required")
    if not isinstance(contact,str) or "@" not in contact or len(contact)<15:
        raise ValueError("SEC identity is required for 100 original SEC report requests")
    captured=waves["captured_at_utc"][:10]
    if as_of<captured:
        raise ValueError("Cannot use new SEC source captures before their capture day")
    by_source=submissions_from_archived_waves(waves)
    targets=select_targets(by_source)
    fetcher=fetcher or request_original
    sleeper=sleeper or (lambda:time.sleep(0.18))
    out=Path(out);rawdir=Path(rawdir)
    out.parent.mkdir(parents=True,exist_ok=True)
    rawdir.mkdir(parents=True,exist_ok=True)
    attempts=[];used_gzip_bytes=0
    for target in targets:
        now=dt.datetime.now(dt.timezone.utc).isoformat()
        rec={**target,"retrieved_at_utc":now,
             "historical_actual_first_provider_receipt_certified":False,
             "filer_acceptance_metadata_not_first_data_feed_receipt":True,
             "current_original_source_retrieval_only":True,
             "success":False,"raw_bytes":None,"raw_SHA256":None,
             "compressed_archive_path":None}
        try:
            raw=fetcher(target["source_url"],contact)
            if (not isinstance(raw,bytes) or not 100<len(raw)<=MAX_DOC_BYTES
                or b"access denied" in raw[:4096].lower()):
                raise ValueError("Not a complete original SEC report payload")
            compressed=gzip.compress(raw,compresslevel=6,mtime=0)
            if used_gzip_bytes+len(compressed)>MAX_ARCHIVED_GZIP_BYTES:
                raise ValueError("Compressed SEC archive overall resource budget reached")
            sha=hashlib.sha256(raw).hexdigest()
            stored=rawdir/(target["download_worker_id"]+"_"+sha[:16]+".html.gz")
            stored.write_bytes(compressed)
            if gzip.decompress(stored.read_bytes())!=raw:
                raise ValueError("Compressed original SEC artifact not lossless")
            used_gzip_bytes+=len(compressed)
            rec.update({"success":True,"status":"original_report_bytes_archived_current",
                        "raw_bytes":len(raw),"raw_SHA256":sha,
                        "gzip_bytes":len(compressed),
                        "compressed_archive_path":str(stored)})
        except (HTTPError,URLError,OSError,TimeoutError,ValueError,TypeError) as exc:
            rec.update({"status":"original_SEC_primary_doc_fetch_failed_not_promoted",
                        "failure_type":type(exc).__name__,
                        "http_status":exc.code if isinstance(exc,HTTPError) else None})
        attempts.append(rec)
        sleeper()
    if (len(attempts)!=100 or len({x["source_url"] for x in attempts})!=100
        or len({x["download_worker_id"] for x in attempts})!=100):
        raise ValueError("Original EDGAR 100 unique report request experiment incomplete")
    success=sum(x["success"] for x in attempts)
    report={
        "schema":"aics-PIT100-distinct-original-SEC-primary-report-downloads-v1",
        "research_as_of":as_of,
        "original_SEC_issuers_sourced_from_current_archived_submissions":len(by_source),
        "unique_distinct_original_filing_documents_requested":100,
        "distinct_acquisition_worker_tasks_executed":100,
        "genuine_original_sec_http_attempts":100,
        "source_document_bytes_archived_successfully":success,
        "source_document_failures_recorded_without_fabrication":100-success,
        "successful_original_report_bytes_total":sum(x["raw_bytes"] or 0 for x in attempts),
        "losslessly_gzipped_report_archives_bytes":used_gzip_bytes,
        "dated_EDGAR_acceptance_metadata_records":sum(x["edgar_acceptance_time_current_registry_field"] is not None for x in attempts),
        "original_public_historical_feed_receipt_attested":False,
        "SEC_14day_wait_policy_active":False,
        "extra_neural_models_trained":0,
        "independent_PIT_certified_nodes":0,
        "approved_AICS_index":None,
        "trades_created":False,
        "tasks":attempts,
    }
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in ("tasks",)}))
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of",default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    p.add_argument("--waves",type=Path,default=INPUT)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--rawdir",type=Path,default=RAW)
    args=p.parse_args()
    collect(waves=read(args.waves),as_of=args.as_of,
            contact=os.getenv("AICS_SEC_USER_AGENT",""),
            out=args.out,rawdir=args.rawdir)


if __name__=="__main__":
    main()
