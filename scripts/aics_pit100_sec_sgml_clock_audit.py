"""Audit 100 original SEC EDGAR SGML acceptance headers against JSON timestamps.

SEC submissions acceptanceDateTime may not have consistent timezone encoding
across issuers, even with trailing Z. Never assume its instant. Fetch *each*
original accession's -index-headers.html, parse SEC <ACCEPTANCE-DATETIME>
Eastern clock, store its original bytes + SHA256 and compare source clocks.

A SEC EDGAR acceptance timestamp is NOT independent proof of first public
dissemination, first feed delivery or 16:00 ET tradeability. No active +14 day
delay, no production scores and no retroactive PIT certification.
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
from collections import Counter
from html import unescape
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from zoneinfo import ZoneInfo

ROOT=Path("aics_data/agent_runs/ten_real_collection_rounds")
REPORTS=ROOT/"aics_pit100_100_original_sec_reports_manifest.json"
OUT=ROOT/"aics_pit100_100_sec_sgml_header_clock_audit.json"
RAW=ROOT/"pit100_sec_sgml_header_raw"
SEC="https://www.sec.gov/Archives/edgar/data/"
ACCESSION=re.compile(r"^\d{10}-\d{2}-\d{6}$")
HEADER_TIME=re.compile(r"<ACCEPTANCE-DATETIME>\s*(\d{14})",re.I)
ACC_FIELD=re.compile(r"ACCESSION\s+NUMBER:\s*(\d{10}-\d{2}-\d{6})",re.I)
ISO_CLOCK=re.compile(r"^(20\d\d-\d\d-\d\d)T(\d\d):(\d\d):(\d\d)")
EASTERN=ZoneInfo("America/New_York")
MAX_BYTES=2_000_000
MAX_ARCHIVED=24_000_000


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def header_url(task):
    acc=task["accession"]
    cik=str(int(task["CIK"]))
    if not ACCESSION.fullmatch(acc) or not cik.isdigit():
        raise ValueError("Unsafe original SEC accession")
    if not task["source_url"].startswith(SEC+f"{cik}/{acc.replace('-','')}/"):
        raise ValueError("SEC CIK/accession URL mismatch")
    return SEC+f"{cik}/{acc.replace('-','')}/{acc}-index-headers.html"


def parse_sgml(raw,*,expected_accession):
    if not isinstance(raw,bytes) or len(raw)<90 or len(raw)>MAX_BYTES:
        raise ValueError("No complete genuine SEC index-header bytes")
    unescaped=unescape(raw.decode("utf-8",errors="replace"))
    stamp=HEADER_TIME.search(unescaped)
    accession=ACC_FIELD.search(unescaped)
    if not stamp or not accession:
        raise ValueError("SEC index header missing original accession or clock")
    if accession.group(1)!=expected_accession:
        raise ValueError("Header belongs to a different original SEC accession")
    try:
        local=dt.datetime.strptime(stamp.group(1),"%Y%m%d%H%M%S").replace(tzinfo=EASTERN)
        if local.astimezone(dt.timezone.utc).astimezone(EASTERN).replace(fold=local.fold)!=local:
            raise ValueError("SEC original Eastern time doesn't round-trip")
    except (ValueError,OverflowError) as e:
        raise ValueError("Unusable SEC original acceptance clock") from e
    return local


def compare_clocks(original_json_clock,header_et):
    """Diagnostic ONLY: never promote JSON to trusted timezone conversion."""
    if not isinstance(original_json_clock,str):
        return "JSON_UNAVAILABLE"
    m=ISO_CLOCK.search(original_json_clock)
    if not m:
        return "JSON_UNPARSEABLE"
    try:
        displayed=dt.datetime.fromisoformat(m.group(0))
    except ValueError:
        return "JSON_UNPARSEABLE"
    sec_wall=header_et.replace(tzinfo=None)
    sec_utc=header_et.astimezone(dt.timezone.utc).replace(tzinfo=None)
    if displayed==sec_wall:
        return "JSON_EASTERN_WALL_CLOCK_MATCH"
    if displayed==sec_utc:
        return "JSON_UTC_WALL_CLOCK_MATCH"
    return "JSON_DISAGREES_WITH_ORIGINAL_SGML"


def fetch(url,identity):
    if not url.startswith(SEC) or not url.endswith("-index-headers.html"):
        raise ValueError("Only original SEC index headers supported")
    r=Request(url,headers={"User-Agent":identity,"Accept":"text/html"})
    with urlopen(r,timeout=15) as response:
        if response.geturl()!=url:
            raise ValueError("Unexpected SEC header redirect")
        return response.read(MAX_BYTES+1)


def collect(reports,*,contact,as_of,out=OUT,rawdir=RAW,fetcher=None,sleeper=None):
    if (reports.get("schema")!="aics-PIT100-distinct-original-SEC-primary-report-downloads-v1"
        or reports.get("unique_distinct_original_filing_documents_requested")!=100
        or reports.get("genuine_original_sec_http_attempts")!=100
        or len(reports.get("tasks",[]))!=100
        or reports.get("original_public_historical_feed_receipt_attested") is not False
        or reports.get("SEC_14day_wait_policy_active") is not False
        or reports.get("approved_AICS_index") is not None):
        raise ValueError("The 100 original EDGAR report audit is not properly archived")
    if (not isinstance(contact,str) or "@" not in contact or len(contact)<15):
        raise ValueError("SEC identity required")
    if (not re.fullmatch(r"20\d\d-\d\d-\d\d",as_of)
        or reports["research_as_of"]>as_of):
        raise ValueError("Invalid audit as-of date")
    rawdir=Path(rawdir);out=Path(out)
    rawdir.mkdir(parents=True,exist_ok=True)
    out.parent.mkdir(parents=True,exist_ok=True)
    fetcher=fetcher or fetch
    sleeper=sleeper or (lambda:time.sleep(.18))
    results=[];compressed_total=0
    for task in reports["tasks"]:
        if (not task.get("success")
            or not task.get("raw_SHA256")
            or not task.get("compressed_archive_path")):
            # An unsuccessful original report never establishes SGML source completeness.
            results.append({
                "accession":task["accession"],"header_http_attempted":False,
                "status":"ORIGINAL_REPORT_NOT_ARCHIVED",
                "original_sec_acceptance_clock_verified_from_sgml":False,
            })
            continue
        url=header_url(task)
        rec={
            "accession":task["accession"],"CIK":task["CIK"],
            "original_filing_date":task["filed_at"],
            "primary_document_original_SHA256":task["raw_SHA256"],
            "header_source_url":url,"header_http_attempted":True,
            "header_captured_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "original_sec_acceptance_clock_verified_from_sgml":False,
            "independent_historical_first_feed_delivery_attested":False,
            "independent_public_dissemination_before_market_close_attested":False,
            "SEC_14day_wait_active":False,
        }
        try:
            raw=fetcher(url,contact)
            local=parse_sgml(raw,expected_accession=task["accession"])
            if local.date().isoformat()!=task["filed_at"]:
                rec["header_acceptance_calendar_date_disagrees_with_filed_date"]=True
            else:
                rec["header_acceptance_calendar_date_disagrees_with_filed_date"]=False
            stored=gzip.compress(raw,compresslevel=6,mtime=0)
            if compressed_total+len(stored)>MAX_ARCHIVED:
                raise ValueError("Header archive resource limit")
            path=rawdir/(task["accession"]+"-"+hashlib.sha256(raw).hexdigest()[:16]+".html.gz")
            path.write_bytes(stored)
            if gzip.decompress(path.read_bytes())!=raw:
                raise ValueError("SGML header compressed bytes did not roundtrip")
            compressed_total+=len(stored)
            wall=local.strftime("%Y-%m-%d %H:%M:%S")
            rec.update({
                "status":"ORIGINAL_SEC_SGML_HEADER_SHA256_ARCHIVED",
                "original_sec_acceptance_clock_verified_from_sgml":True,
                "acceptance_et_wall_clock":wall,
                "acceptance_utc_from_sgml":local.astimezone(dt.timezone.utc).isoformat(),
                "accepted_before_16_et":local.time()<dt.time(16,0),
                "accepted_at_or_after_16_et":local.time()>=dt.time(16,0),
                "SEC_submission_JSON_timestamp_diagnostic_only":
                    compare_clocks(task.get("edgar_acceptance_time_current_registry_field"),local),
                "original_sec_header_raw_SHA256":hashlib.sha256(raw).hexdigest(),
                "original_sec_header_bytes":len(raw),
                "original_header_archive_gz_path":str(path),
            })
        except (HTTPError,URLError,OSError,TimeoutError,ValueError,TypeError) as exc:
            rec.update({
                "status":"SGML_HEADER_UNAVAILABLE_OR_UNTRUSTED",
                "failure_type":type(exc).__name__,
                "http_status":exc.code if isinstance(exc,HTTPError) else None,
            })
        results.append(rec)
        sleeper()
    requested=sum(x.get("header_http_attempted",False) for x in results)
    good=[x for x in results if x.get("original_sec_acceptance_clock_verified_from_sgml") is True]
    counts=Counter(x["SEC_submission_JSON_timestamp_diagnostic_only"] for x in good)
    if len(results)!=100 or len({x["accession"] for x in results})!=100:
        raise ValueError("100 original SEC header identities expected")
    report={
        "schema":"aics-PIT100-first-original-SEC-SGML-timezone-clocks-audit-v1",
        "research_as_of":as_of,
        "distinct_original_SEC_report_tasks_referenced":100,
        "original_SEC_header_http_attempts":requested,
        "original_SEC_header_SHA256_archives_successful":len(good),
        "original_SEC_header_failures":requested-len(good),
        "original_SEC_header_same_day_pre16_ET_candidates":
            sum(x["accepted_before_16_et"] for x in good),
        "original_SEC_header_at_or_after16_ET":
            sum(x["accepted_at_or_after_16_et"] for x in good),
        "json_raw_timestamp_against_SGML_diagnostics":dict(sorted(counts.items())),
        "source_original_report_identity_from_parent_manifest":True,
        "SGML_header_downloads_are_current_not_historical_first_delivery":True,
        "accepted_before_16_ET_does_not_prove_public_before_market_close":True,
        "JSON_mixed_timezone_formats_must_not_be_used_without_SGML":True,
        "calendar_day_release_research_gate_no_SEC_plus14":True,
        "public_dissemination_PIT_certified":False,
        "historical_provider_first_byte_PIT_certified":False,
        "production_11node_AICS":None,
        "approved_AICS_SP500_spread":None,
        "trades_created":False,
        "source_headers":results,
    }
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="source_headers"}))
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of",default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    p.add_argument("--reports",type=Path,default=REPORTS)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--rawdir",type=Path,default=RAW)
    args=p.parse_args()
    collect(read(args.reports),contact=os.getenv("AICS_SEC_USER_AGENT",""),
            as_of=args.as_of,out=args.out,rawdir=args.rawdir)


if __name__=="__main__":
    main()
