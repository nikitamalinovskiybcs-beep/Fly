"""Targeted actual original SEC accession gap fill for AICS scoring events.

Instead of downloading 100 merely recent EDGAR reports again, fetch ONLY
the original issuer scoring-document accessions not matched by PIT100 sample.
For each: the originally referenced exact document (canonical SEC original
archive URL), plus SEC accession-specific original -index-headers.html.
Archive both raw bytes SHA256, extract verified original acceptance ET.
Never fabricate missing data, assert first data-feed delivery, compute
unverified accounting metric values, or promote 11-node index.
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
from urllib.parse import urlparse,unquote
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

from scripts.aics_pit100_sec_sgml_clock_audit import parse_sgml,SEC

ROOT=Path("aics_data/agent_runs/ten_real_collection_rounds")
CROSSWALK=ROOT/"aics_pit100_original_source_accession_to_node_lineage.json"
OUT=ROOT/"aics_pit100_targeted_missing_sec_original_score_docs.json"
RAW=ROOT/"pit100_targeted_missing_original_scoring_docs_raw"
ACCESSION=re.compile(r"^\d{10}-\d{2}-\d{6}$")
BASENAME=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,240}\.(?:htm|html|xml|txt)$",re.I)
MAX_DOC=48_000_000
MAX_HEADER=2_000_000
MAX_ARCHIVED_GZIP=100_000_000


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def canonical_original_urls(entry):
    acc=entry["accession"]
    cik=str(int(entry["CIK"]))
    if not ACCESSION.fullmatch(acc):
        raise ValueError("Not a real original SEC accession")
    url=entry["source_original_doc_url"]
    parsed=urlparse(url)
    if parsed.scheme!="https" or parsed.hostname not in (
            "www.sec.gov","sec.gov","investor.prudential.com"):
        raise ValueError("Original reference source domain is untrusted")
    if parsed.query or parsed.fragment:
        raise ValueError("Unsafe original source document URL")
    basename=unquote(parsed.path.rsplit("/",1)[-1])
    if not BASENAME.fullmatch(basename) or ".." in basename:
        raise ValueError("Unsafe SEC primary document filename")
    accession_no_dash=acc.replace("-","")
    prefix=f"{SEC}{cik}/{accession_no_dash}/"
    return prefix+basename,prefix+acc+"-index-headers.html"


def fetch(url,contact,max_bytes):
    if not url.startswith(SEC):
        raise ValueError("Official SEC original archive only")
    req=Request(url,headers={
        "User-Agent":contact,"Accept":"text/html,text/plain,application/xml",
    })
    with urlopen(req,timeout=16) as response:
        if response.geturl()!=url:
            raise ValueError("SEC original response redirected unexpectedly")
        data=response.read(max_bytes+1)
    if (len(data)<100 or len(data)>max_bytes
        or b"access denied" in data[:4096].lower()
        or b"request rate threshold" in data[:4096].lower()):
        raise ValueError("SEC source response invalid or blocked")
    return data


def collect(crosswalk,*,as_of,contact,out=OUT,rawdir=RAW,
            fetcher=None,sleeper=None):
    claims=crosswalk.get("source_claims",[])
    if (crosswalk.get("schema")!="aics-PIT100-original-scoring-accession-to-SEC-SGML-crosswalk-v1"
        or crosswalk.get("research_underlying_original_filing_references")!=36
        or crosswalk.get("research_source_cohorts")!=19
        or crosswalk.get("source_bytes_today_not_historical_first_delivery") is not True
        or crosswalk.get("underlying_accounting_metric_independently_parsed_from_exact_bytes")!=0
        or crosswalk.get("complete_11node_AICS") is not None
        or len(claims)!=36):
        raise ValueError("Expected 36 exact original SEC issuer source claims")
    if (not isinstance(contact,str) or len(contact)<15 or "@" not in contact):
        raise ValueError("SEC source identification required")
    if (not re.fullmatch(r"20\d\d-\d\d-\d\d",as_of)):
        raise ValueError("Explicit UTC research as-of date required")
    missing=[x for x in claims if not x["same_exact_CIK_accession_header_clock_verified"]]
    if len({(x["CIK"],x["accession"]) for x in missing})!=len(missing):
        raise ValueError("Duplicate original source accessions in target roster")
    matched=36-len(missing)
    if matched!=crosswalk["exact_original_filing_accession_in_100_primary_archive_and_header"]:
        raise ValueError("Original already matched source count inconsistent")
    fetcher=fetcher or fetch
    sleeper=sleeper or (lambda:time.sleep(.18))
    out=Path(out);rawdir=Path(rawdir)
    out.parent.mkdir(parents=True,exist_ok=True)
    rawdir.mkdir(parents=True,exist_ok=True)
    entries=[];total_gzip=0
    for original in missing:
        doc_url,header_url=canonical_original_urls(original)
        r={
            "node":original["node"],"cohort":original["cohort"],
            "issuer":original["issuer"],"CIK":original["CIK"],
            "accession":original["accession"],
            "referenced_original_source_document_url":original["source_original_doc_url"],
            "official_canonical_original_source_document_url":doc_url,
            "official_canonical_original_index_header_url":header_url,
            "requested_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "targeted_primary_original_download_attempted":True,
            "targeted_header_original_download_attempted":True,
            "success_exact_original_scoring_document_and_sgml":False,
            "original_source_metric_independently_extracted_from_raw":False,
            "historical_first_public_dissemination_attested":False,
            "historical_first_data_feed_receipt_attested":False,
            "source_eligible_without_14day_artificial_wait":True,
            "approved_node_score":None,
        }
        try:
            document=fetcher(doc_url,contact,MAX_DOC)
            header=fetcher(header_url,contact,MAX_HEADER)
            if (not isinstance(document,bytes) or len(document)<100 or len(document)>MAX_DOC
                or not isinstance(header,bytes) or len(header)<100 or len(header)>MAX_HEADER
                or b"access denied" in document[:4096].lower()):
                raise ValueError("Original SEC scoring document and header both required")
            accepted=parse_sgml(header,expected_accession=original["accession"])
            # SEC acceptance ET is NOT necessarily the EDGAR official filed
            # date. Submissions accepted after the filing cutoff (including
            # CoreWeave 2025Q1 and 2025Q2) legitimately receive NEXT-DAY
            # filing dates. Check the original SGML filed-as-of field.
            filed_match=re.search(rb"FILED AS OF DATE:\s*(\d{8})",header,re.I)
            if filed_match is None:
                raise ValueError("Original SEC SGML official filed-as-of date absent")
            header_filed=dt.datetime.strptime(
                filed_match.group(1).decode("ascii"),"%Y%m%d").date()
            if (original.get("source_original_filed_day") is not None
                and header_filed.isoformat()!=original["source_original_filed_day"]):
                raise ValueError("Original SEC official filing day contradicts signed source ledger")
            acceptance_to_filing_days=(header_filed-accepted.date()).days
            if not 0<=acceptance_to_filing_days<=4:
                raise ValueError("SEC acceptance to official file-day interval implausible")
            digest_doc=hashlib.sha256(document).hexdigest()
            digest_hdr=hashlib.sha256(header).hexdigest()
            packed_doc=gzip.compress(document,compresslevel=6,mtime=0)
            packed_hdr=gzip.compress(header,compresslevel=6,mtime=0)
            if total_gzip+len(packed_doc)+len(packed_hdr)>MAX_ARCHIVED_GZIP:
                raise ValueError("Targeted exact-original archive byte cap reached")
            p1=rawdir/(original["accession"]+"_"+digest_doc[:16]+".doc.gz")
            p2=rawdir/(original["accession"]+"_"+digest_hdr[:16]+".hdr.gz")
            p1.write_bytes(packed_doc)
            p2.write_bytes(packed_hdr)
            if (gzip.decompress(p1.read_bytes())!=document
                or gzip.decompress(p2.read_bytes())!=header):
                raise ValueError("Source-gzip original bytes not lossless")
            total_gzip+=len(packed_doc)+len(packed_hdr)
            r.update({
                "success_exact_original_scoring_document_and_sgml":True,
                "original_doc_raw_sha256":digest_doc,
                "original_header_raw_sha256":digest_hdr,
                "original_doc_raw_bytes":len(document),
                "original_header_raw_bytes":len(header),
                "original_doc_gzip_archived_path":str(p1),
                "original_header_gzip_archived_path":str(p2),
                "original_sgml_acceptance_ET":accepted.isoformat(),
                "original_sgml_official_FILED_AS_OF_DATE":header_filed.isoformat(),
                "acceptance_ET_calendar_day_differs_from_official_FILED_AS_OF_DATE":
                    acceptance_to_filing_days!=0,
                "official_filing_date_lag_after_acceptance_calendar_days":
                    acceptance_to_filing_days,
                "accepted_before_16_ET_not_public_delivery_evidence":
                    accepted.time()<dt.time(16,0),
                "exact_original_document_raw_hash_verified_current_capture":True,
            })
        except (HTTPError,URLError,OSError,TimeoutError,ValueError,TypeError) as exc:
            r.update({
                "failure_type":type(exc).__name__,
                "http_status":exc.code if isinstance(exc,HTTPError) else None,
                "safe_failure_reason":str(exc)[:130] if isinstance(exc,ValueError) else None,
            })
        entries.append(r)
        sleeper()
    successes=sum(x["success_exact_original_scoring_document_and_sgml"] for x in entries)
    if len(entries)!=len(missing):
        raise ValueError("Targeted missing original SEC accession attempt roster incomplete")
    report={
        "schema":"aics-PIT100-targeted-original-scoring-accession-SGML-fill-v1",
        "as_of":as_of,
        "original_research_filing_claims":36,
        "original_claims_already_matched_via_unrelated_100_sample":matched,
        "targeted_missing_exact_original_accession_attempts":len(entries),
        "targeted_original_primary_and_SGML_both_sha_archived":successes,
        "targeted_original_source_download_failures":len(entries)-successes,
        "exact_sources_with_SECGML_acceptance_day_different_from_filed_day":
            sum(x.get("acceptance_ET_calendar_day_differs_from_official_FILED_AS_OF_DATE",False)
                for x in entries),
        "combined_original_score_source_accessions_now_hashed_and_clock_matched":
            matched+successes,
        "still_missing_original_exact_source_accessions_after_targeted_fetch":
            len(entries)-successes,
        "targeted_original_bytes_gzip_total":total_gzip,
        "targeted_is_source_evidence_not_100_new_trained_ai_agents":True,
        "source_document_today_does_not_certify_historical_first_publisher_feed_delivery":True,
        "original_accounting_values_automatically_verified_from_source_bytes":0,
        "historically_PIT_certified_11node_scores":0,
        "full_11node_AICS":None,
        "trades_created":False,
        "targeted_source_results":entries,
    }
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="targeted_source_results"}))
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--crosswalk",type=Path,default=CROSSWALK)
    p.add_argument("--as-of",default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--rawdir",type=Path,default=RAW)
    args=p.parse_args()
    collect(read(args.crosswalk),as_of=args.as_of,
            contact=os.getenv("AICS_SEC_USER_AGENT",""),
            out=args.out,rawdir=args.rawdir)


if __name__=="__main__":
    main()
