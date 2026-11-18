#!/usr/bin/env python3
"""Retain the actual OMI/AFREF policy PDF bytes with a SHA-256 evidence receipt.

The publication is SECONDARY policy research: downloading it never validates
underlying market claims or a historical AICS node.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen

SOURCE_URLS=(
 "https://www.openmarketsinstitute.org/s/Brace-for-Impact-Scherer-Jenkins-OMI-October2026-WEB-1.pdf",
 "https://ourfinancialsecurity.org/wp-content/uploads/2026/10/Brace-for-Impact-Scherer-Jenkins-OMI-October2026-WEB.pdf",
)
TRUSTED_FINAL_HOSTS={"www.openmarketsinstitute.org","ourfinancialsecurity.org",
                     "static1.squarespace.com"}
MAX_BYTES=40_000_000


def fetch_pdf(url:str,opener=urlopen):
    if url not in SOURCE_URLS:
        raise ValueError("Unapproved research source URL")
    req=Request(url,headers={"User-Agent":"AICS Research PDF archival","Accept":"application/pdf"})
    with opener(req,timeout=50) as r:
        final=r.geturl()
        split=urlsplit(final)
        if (split.scheme!="https" or split.hostname not in TRUSTED_FINAL_HOSTS
                or split.username or split.password):
            raise ValueError("Unapproved publisher PDF redirect")
        raw=r.read(MAX_BYTES+1)
    if not raw.startswith(b"%PDF-") or len(raw)<100 or len(raw)>MAX_BYTES:
        raise ValueError("Invalid or truncated PDF source")
    if b"%%EOF" not in raw[-4096:]:
        raise ValueError("PDF final trailer missing")
    return raw,final


def capture(output:Path,opener=urlopen):
    output.mkdir(parents=True,exist_ok=True)
    results=[]
    for uri in SOURCE_URLS:
        row={"requested_url":uri,"status":"not_fetched"}
        try:
            raw,final=fetch_pdf(uri,opener)
            sha=hashlib.sha256(raw).hexdigest()
            path=output/(sha+".pdf")
            if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
                raise ValueError("Existing source PDF SHA256 disagreement")
            if not path.exists():
                path.write_bytes(raw)
            row.update(status="archived_raw_pdf_not_primary_data",
                       response_url=final,source_sha256=sha,bytes=len(raw),
                       raw_path=str(path))
        except Exception as e:
            row.update(status="fetch_failed",error=type(e).__name__)
        results.append(row)
    files=[r for r in results if r["status"]=="archived_raw_pdf_not_primary_data"]
    result={"schema_version":"aics-secondary-pdf-archive-v1",
            "captured_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "source_title":"Brace for Impact: Protecting People and the Economy When the AI Bubble Bursts",
            "source_kind":"SECONDARY_POLICY_RESEARCH_NOT_MARKET_DATA",
            "source_candidates":results,
            "archive_count":len(files),
            "same_bytes_across_publisher_hosts":(len({x["source_sha256"] for x in files})==1)
                if len(files)>1 else None,
            "original_primary_financial_claims_verified":False,
            "historical_pit_independently_verified":False,
            "candidate_node_scores":None,"index_aics":None,
            "prediction_skill":None,"promotion":"BLOCKED"}
    (output/"receipt.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,default=Path("aics_data/source_evidence/omi_brace_impact_pdf"))
    o=p.parse_args()
    receipt=capture(o.output)
    print(json.dumps({"pdf_archive_count":receipt["archive_count"],"promotion":"BLOCKED",
                      "sources":[x["status"] for x in receipt["source_candidates"]]}))
    return 0 if receipt["archive_count"]>0 else 2

if __name__=="__main__":
    raise SystemExit(main())
