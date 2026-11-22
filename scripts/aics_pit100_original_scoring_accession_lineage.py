"""AICS targeted SEC accession lineage: source events vs 100 real original filings.

Map exact underlying original source documents for 9 Prudential insurer
quarters, 7*3 private-credit BDC reports, 3*2 neocloud SEC issuer filings.
Only an exact (CIK, accession) match in the 100 original reports plus the
same verified original SEC SGML header can establish an acceptance clock for
the specified AICS source accession, NEVER first public dissemination/PIT.
A match to a primary SEC doc is NOT proof that a referenced exhibit's
accounting metric has been independently extracted from its bytes.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from scripts.aics_pit100_rebuild_24m_research import OVERLAY,CREDIT,read_bytes,date,num
from scripts.aics_pit100_sec_sgml_clock_audit import REPORTS as REPORTS_DEFAULT,OUT as HEADERS_DEFAULT

ROOT=Path("aics_data/agent_runs/ten_real_collection_rounds")
PRU=Path("aics_data/research/pru_insurers_nonaccrual_original_quarters_2025_2026.json")
NEO=Path("aics_data/research/neoclouds_2025_q1_q3_sec_cashflow_research_2026-11-21.json")
OUT=ROOT/"aics_pit100_original_source_accession_to_node_lineage.json"
SEC_URL=re.compile(r"^https://www.sec.gov/Archives/edgar/data/(\d+)/(\d{18})/[A-Za-z0-9_.-]+$")
ACCESSION=re.compile(r"^\d{10}-\d{2}-\d{6}$")



def canonical_primary_doc_url(url, *, cik, accession):
    """Strict SEC original identity across EDGAR and Prudential's official mirror.

    SEC archive CIK/accession/filename must match exactly. Only an explicit
    Prudential accession-based investor-hosted mirror is recognized, never a
    generic cross-host path or arbitrary URL basename.
    """
    if not ACCESSION.fullmatch(accession):
        return None
    p=urlsplit(url)
    if (p.scheme!="https" or p.username is not None or p.password is not None
        or p.port is not None or p.query or p.fragment):
        return None
    norm_cik=str(int(cik))
    undashed=accession.replace("-","")
    if p.hostname in ("www.sec.gov","sec.gov"):
        match=re.fullmatch(
            r"/Archives/edgar/data/(\\d+)/(\\d{18})/([A-Za-z0-9][A-Za-z0-9_.-]*)",
            p.path,
        )
        if not match or str(int(match.group(1)))!=norm_cik or match.group(2)!=undashed:
            return None
        basename=match.group(3)
    elif p.hostname=="investor.prudential.com" and norm_cik=="1137774":
        match=re.fullmatch(
            r"/financials/sec-filings/content/(\\d{10}-\\d{2}-\\d{6})/([A-Za-z0-9][A-Za-z0-9_.-]*)",
            p.path,
        )
        if not match or match.group(1)!=accession:
            return None
        basename=match.group(2)
    else:
        return None
    if ".." in basename:
        return None
    return f"https://www.sec.gov/Archives/edgar/data/{norm_cik}/{undashed}/{basename}".lower()


def accession_from_sec_url(url):
    m=SEC_URL.fullmatch(url)
    if not m:raise ValueError("No exact original SEC archive document identity")
    acc=m.group(2)
    return (str(int(m.group(1))),f"{acc[:10]}-{acc[10:12]}-{acc[12:]}")


def extract(overlay,credit,pru,neo):
    if (overlay.get("schema")!="aics-24m-multi-node-first-public-date-research-overlay-v1"
        or credit.get("schema")!="aics-v18-24m-private-credit-original-sec-expost-research-overlay-v1"
        or pru.get("schema")!="aics-pru-insurers-noacl-nonaccrual-quarterly-original-filing-v1"
        or neo.get("schema")!="aics-neocloud-2025-q1-q3-original-sec-research-v1"
        or pru.get("periods")!=9
        or len(pru["events"])!=9
        or len(neo["sources"])!=6
        or len(credit["source_events"])!=7):
        raise ValueError("Original source identities or cohort altered")
    originals=overlay["source_events"]
    rows=[]
    cohorts={}
    for e in pru["events"]:
        issuer="PRU"
        acc=e["accession"]
        filed=e["filed_at"]
        if not ACCESSION.fullmatch(acc) or len(str(e["cik"]))<5:
            raise ValueError("Malformed original Prudential SEC accession")
        matches=[(i,r) for i,r in enumerate(originals)
                 if r["node"]=="Insurers" and r["available_at"]==e["available_at"]
                 and num(r["score"])==num(e["score_pct"])]
        if len(matches)!=1:
            raise ValueError("PRU source score and original source date not reconciled")
        i,source=matches[0]
        cohort=f"INSURERS:{e['quarter']}"
        rows.append({
            "node":"Insurers","cohort":cohort,"issuer":issuer,
            "CIK":str(int(e["cik"])),"accession":acc,
            "source_original_doc_url":e["source_url"],
            "source_original_filed_day":filed,
            "source_research_date_only_event_id":f"V17:{i:02d}",
            "source_research_eligible_filing_day":filed,
            "metric_original_bytes_independently_parsed":False,
            "source_provider_first_delivery_attested":False,
        })
        cohorts[cohort]={"node":"Insurers","original_event_id":f"V17:{i:02d}",
                        "necessary_exact_original_filing_accessions":1}
    for e in credit["source_events"]:
        cohort=f"PRIVATE_CREDIT:{e['quarter']}"
        cohort_filed=(date(e["legacy_sec_plus14_available_at"])
                      -dt.timedelta(days=14)).isoformat()
        if cohort_filed!=(date(e["research_available_at_proxy"])-dt.timedelta(days=1)).isoformat():
            raise ValueError("Original three BDC last filing cohort day mismatch")
        cohorts[cohort]={"node":"Private Credit",
                         "original_event_id":f"V18_BDC:{credit['source_events'].index(e):02d}",
                         "necessary_exact_original_filing_accessions":3,
                         "original_date_only_max_filed_cohort_proxy":cohort_filed}
        for issuer,url in sorted(e["issuer_source_provenance"].items()):
            if issuer not in {"ARCC","BXSL","OBDC"}:
                raise ValueError("Unknown original three-BDC issuer")
            cik,acc=accession_from_sec_url(url)
            rows.append({
                "node":"Private Credit","cohort":cohort,"issuer":issuer,
                "CIK":cik,"accession":acc,"source_original_doc_url":url,
                "source_original_filed_day":None,
                "source_research_date_only_event_id":cohorts[cohort]["original_event_id"],
                "source_research_eligible_filing_day":cohort_filed,
                "metric_original_bytes_independently_parsed":False,
                "source_provider_first_delivery_attested":False,
            })
    periods={
        "2025-Q1":["crwv_q1","nbis_q1"],
        "2025-Q2":["crwv_h1","nbis_q2"],
        "2025-Q3":["crwv_9m","nbis_9m"],
    }
    for period,keys in periods.items():
        sources=[neo["sources"][k] for k in keys]
        max_file=max(x["filed_at"] for x in sources)
        matches=[(i,r) for i,r in enumerate(originals)
                 if r["node"]=="Neoclouds"
                 and r["measurement"].startswith(period+" original 2025 SEC")
                 and r["available_at"]==
                     (date(max_file)+dt.timedelta(days=14)).isoformat()]
        if len(matches)!=1:
            raise ValueError("Historical neocloud source cohort origination mismatch")
        i,_=matches[0]
        cohort=f"NEOCLOUDS:{period}"
        cohorts[cohort]={"node":"Neoclouds","original_event_id":f"V17:{i:02d}",
                         "necessary_exact_original_filing_accessions":2}
        for record in sources:
            if record["issuer"] not in ("CoreWeave","Nebius"):
                raise ValueError("Unexpected issuer scope in two-source neocloud quarter")
            url=record["source_page"]
            cik,acc=accession_from_sec_url(url)
            if acc!=record["accession"]:
                raise ValueError("Neocloud SEC original accession inconsistent with URL")
            rows.append({
                "node":"Neoclouds","cohort":cohort,"issuer":record["issuer"],
                "CIK":cik,"accession":acc,"source_original_doc_url":url,
                "source_original_filed_day":record["filed_at"],
                "source_research_date_only_event_id":f"V17:{i:02d}",
                "source_research_eligible_filing_day":max_file,
                "metric_original_bytes_independently_parsed":False,
                "source_provider_first_delivery_attested":False,
            })
    if (len(rows)!=36 or len(cohorts)!=19
        or len({(r["CIK"],r["accession"]) for r in rows})!=36
        or len({r["source_research_date_only_event_id"] for r in rows})!=19):
        raise ValueError("Exactly 36 original SEC filings support 19 distinct research events")
    return rows,cohorts


def build(overlay,credit,pru,neo,reports,headers):
    rows,cohorts=extract(overlay,credit,pru,neo)
    if (reports.get("schema")!="aics-PIT100-distinct-original-SEC-primary-report-downloads-v1"
        or len(reports.get("tasks",[]))!=100
        or reports.get("original_public_historical_feed_receipt_attested") is not False
        or headers.get("schema")!="aics-PIT100-first-original-SEC-SGML-timezone-clocks-audit-v1"
        or len(headers.get("source_headers",[]))!=100
        or headers.get("public_dissemination_PIT_certified") is not False):
        raise ValueError("Source research crosswalk requires the 100 original report and header ledgers")
    d={(str(int(t["CIK"])),t["accession"]):t for t in reports["tasks"]}
    h={(str(int(t["CIK"])),t["accession"]):t for t in headers["source_headers"]}
    if len(d)!=100 or len(h)!=100 or set(d)!=set(h):
        raise ValueError("The 100 SEC report and SGML accession identities diverge")
    issuer_matches=[]
    for row in rows:
        e={**row}
        key=(row["CIK"],row["accession"])
        t=d.get(key)
        original=h.get(key)
        matched=(t is not None and t.get("success") is True and
                 original is not None and
                 original.get("original_sec_acceptance_clock_verified_from_sgml") is True)
        e["same_exact_CIK_accession_in_100_download_sample"]=t is not None
        e["same_exact_CIK_accession_header_clock_verified"]=matched
        literal_url_equal=(bool(t) and
            row["source_original_doc_url"].lower()==t["source_url"].lower())
        canonical_expected=canonical_primary_doc_url(
            row["source_original_doc_url"],cik=row["CIK"],accession=row["accession"])
        canonical_actual=(canonical_primary_doc_url(
            t["source_url"],cik=row["CIK"],accession=row["accession"]) if t else None)
        e["literal_reference_URL_equals_archived_primary_doc_URL"]=literal_url_equal
        e["same_exact_primary_document_url_matched_to_source"]=(
            canonical_expected is not None and canonical_expected==canonical_actual)
        e["original_reference_canonical_SEC_URL"]=canonical_expected
        e["source_url_mirror_normalized_for_same_CIK_accession_filename"]=(
            e["same_exact_primary_document_url_matched_to_source"] and not literal_url_equal)
        e["verified_original_sec_acceptance_ET"]=original.get("acceptance_et_wall_clock") if matched else None
        e["original_sec_header_source_sha256"]=original.get("original_sec_header_raw_SHA256") if matched else None
        e["SGML_accepted_before_16_ET"]=original.get("accepted_before_16_et") if matched else None
        e["report_raw_sha256"]=t.get("raw_SHA256") if t and t.get("success") else None
        e["historical_public_dissemination_before_market_close_attested"]=False
        e["current_archive_original_bytes_not_historical_first_delivery"]=True
        e["original_input_metric_independently_verified_against_original_bytes"]=False
        if matched and e["source_original_filed_day"] is not None:
            if original["original_filing_date"]!=e["source_original_filed_day"]:
                raise ValueError("Exact issuer/source filing date diverges from independently archived SGML accession")
        issuer_matches.append(e)
    groups=[]
    for cohort,meta in sorted(cohorts.items()):
        items=[r for r in issuer_matches if r["cohort"]==cohort]
        needed=meta["necessary_exact_original_filing_accessions"]
        matched=sum(r["same_exact_CIK_accession_header_clock_verified"] for r in items)
        if len(items)!=needed:
            raise ValueError("Cohort issuer count changed in original source")
        groups.append({
            "cohort_id":cohort,"source_node":meta["node"],
            "source_event_id":meta["original_event_id"],
            "original_underlying_issuer_reports_needed":needed,
            "original_underlying_issuer_acceptance_headers_found":matched,
            "all_original_source_filing_headers_in_100_downloads":matched==needed,
            "historical_first_provider_delivery_all_sources_attested":False,
            "historical_pit_node_certified":False,
        })
    matched=sum(r["same_exact_CIK_accession_header_clock_verified"] for r in issuer_matches)
    exact=sum(r["literal_reference_URL_equals_archived_primary_doc_URL"] for r in issuer_matches)
    canonical=sum(r["same_exact_primary_document_url_matched_to_source"] for r in issuer_matches)
    mirrors=sum(r["source_url_mirror_normalized_for_same_CIK_accession_filename"] for r in issuer_matches)
    return {
        "schema":"aics-PIT100-original-scoring-accession-to-SEC-SGML-crosswalk-v1",
        "research_underlying_original_filing_references":36,
        "research_source_cohorts":19,
        "original_document_family_counts":{"Insurers":9,"Private Credit":21,"Neoclouds":6},
        "exact_original_filing_accession_in_100_primary_archive_and_header":matched,
        "exact_original_reference_URL_equals_archived_primary_doc_URL":exact,
        "exact_original_reference_canonical_SEC_doc_identity_matches":canonical,
        "explicit_PRU_official_mirror_URL_normalizations":mirrors,
        "source_event_cohorts_with_all_header_accessions":
            sum(x["all_original_source_filing_headers_in_100_downloads"] for x in groups),
        "original_source_filing_claims_not_in_100_sample":36-matched,
        "never_promote_unrelated_SEC_filing_to_node_source":True,
        "source_bytes_today_not_historical_first_delivery":True,
        "exact_header_acceptance_not_public_dissemination":True,
        "underlying_accounting_metric_independently_parsed_from_exact_bytes":0,
        "historically_pit_certified_node_count":0,
        "complete_11node_AICS":None,
        "trades_created":False,
        "source_claims":issuer_matches,
        "source_cohorts":groups,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reports",type=Path,default=REPORTS_DEFAULT)
    p.add_argument("--headers",type=Path,default=HEADERS_DEFAULT)
    p.add_argument("--out",type=Path,default=OUT)
    a=p.parse_args()
    paths=(OVERLAY,CREDIT,PRU,NEO,a.reports,a.headers)
    report=build(*(read_bytes(path) for path in paths))
    report["input_SHA256"]={
        str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "source_issuer_filing_claims":report["research_underlying_original_filing_references"],
        "source_cohorts":report["research_source_cohorts"],
        "original_header_matches":report["exact_original_filing_accession_in_100_primary_archive_and_header"],
        "complete_source_cohorts_with_original_header":report["source_event_cohorts_with_all_header_accessions"],
        "original_metric_bytes_independently_verified":0,
        "historical_pit_certified_nodes":0,
        "index":None,"trades":False,
    }))
if __name__=="__main__":
    main()
