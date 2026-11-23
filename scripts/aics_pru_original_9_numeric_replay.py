"""Independent PRU original 9-quarter SEC disclosure-to-research ratio replay.

For each exact, SHA-verified original SEC HTML: locate the contemporaneous
nonaccrual-without-ACL prose and the narrow commercial-mortgage-and-other-loans
NET portfolio row, explicitly validate the measurement period and scope,
then independently recompute the research percentage with Decimal.
If any fragment is absent, ambiguous, tampered or belongs to a different
period, report BLOCKED; do not copy numbers from the retrospective ledger.

This proves neither first historical feed delivery nor an AICS risk score.
"""
from __future__ import annotations
import argparse
import calendar
import gzip
import hashlib
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from html.parser import HTMLParser
from pathlib import Path

from scripts.aics_priority100_workbench import (
    ROOT, REPORTS, TARGETED, CROSSWALK, verify_gzip_original
)

PRU=Path("aics_data/research/pru_insurers_nonaccrual_original_quarters_2025_2026.json")
QUEUE=ROOT/"aics_priority100_evidence_queue.json"
OUT=ROOT/"aics_pru_nine_original_source_numeric_replay.json"
NARRATIVE=re.compile(
    r"loans on non[\s\-]*accrual status that did not have a related allowance "
    r"for credit losses (?:were|totaled|amounted to)\s*\$?\s*([\d,]+)\s*million",
    flags=re.I
)
NUMBER=re.compile(r"^\(?\d{1,3}(?:,\d{3})*\)?$|^\d+$")
LABEL="total commercial mortgage and other loans, net"


class FilingText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text=[]
        self.rows=[]
        self.in_row=False
        self.in_cell=False
        self.cells=[]
        self.cell=[]
        self.omit_depth=0

    def handle_starttag(self, tag, attrs):
        tag=tag.lower()
        if tag in ("script", "style"):
            self.omit_depth+=1
        if self.omit_depth:
            return
        if tag=="tr":
            self.in_row=True
            self.cells=[]
        elif tag in ("td","th") and self.in_row:
            self.in_cell=True
            self.cell=[]

    def handle_data(self, value):
        if self.omit_depth:
            return
        self.text.append(value)
        if self.in_cell:
            self.cell.append(value)

    def handle_endtag(self, tag):
        tag=tag.lower()
        if tag in ("script", "style") and self.omit_depth:
            self.omit_depth-=1
            return
        if self.omit_depth:
            return
        if tag in ("td","th") and self.in_cell:
            self.cells.append(" ".join(self.cell))
            self.in_cell=False
        elif tag=="tr" and self.in_row:
            self.rows.append(self.cells)
            self.in_row=False


def norm(s):
    return " ".join(s.replace("\xa0"," ").split())


def period_text(iso):
    y,m,d=(int(v) for v in iso.split("-"))
    return f"{calendar.month_name[m]} {d}, {y}"


def parse_original(raw,*,period_end):
    parser=FilingText()
    parser.feed(raw.decode("utf-8",errors="replace"))
    narrative=norm(" ".join(parser.text))
    target=period_text(period_end).lower()
    numerator_matches=[]
    for match in NARRATIVE.finditer(narrative):
        context=narrative[match.start():match.start()+420]
        if target in context.lower():
            numerator_matches.append((int(match.group(1).replace(",","")),context[:250]))
    # Exact unique current-period narrative value; adjacent prior-year
    # value in the same sentence is not substituted.
    nums={x[0] for x in numerator_matches}
    numerator=next(iter(nums)) if len(nums)==1 else None
    candidate_rows=[]
    for cells in parser.rows:
        cleaned=[norm(x) for x in cells if norm(x)]
        if not cleaned:
            continue
        labels=[i for i,x in enumerate(cleaned) if x.lower().strip(" :") == LABEL]
        for j in labels:
            values=[int(x.replace(",","")) for x in cleaned[j+1:]
                    if NUMBER.fullmatch(x) and not x.startswith("(")]
            if values:
                candidate_rows.append({"first_numeric_column":values[0],
                                       "numeric_columns":values[:4],
                                       "row":cleaned[:28]})
    first_values={x["first_numeric_column"] for x in candidate_rows}
    denominator=next(iter(first_values)) if len(first_values)==1 else None
    score=(Decimal(100)*Decimal(numerator)/Decimal(denominator)).quantize(
        Decimal("0.01"),rounding=ROUND_HALF_UP
    ) if numerator is not None and denominator is not None and denominator>0 else None
    return {
        "measurement_period_end":period_end,
        "numerator_without_related_acl_usd_m":numerator,
        "numerator_current_period_unique":len(nums)==1,
        "numerator_exact_original_prose_snippet":numerator_matches[0][1] if len(nums)==1 else None,
        "denominator_narrow_commercial_mortgage_other_loans_net_usd_m":denominator,
        "denominator_first_numeric_column_unique":len(first_values)==1,
        "denominator_original_table_row":candidate_rows[0]["row"] if len(first_values)==1 else None,
        "ratio_recomputed_pct_2dp":str(score) if score is not None else None,
        "source_narrative_candidates":len(numerator_matches),
        "source_table_row_candidates":len(candidate_rows),
    }


def key(row):
    return (str(int(row["CIK"])),row["accession"])


def replay(pru,queue,crosswalk,reports,targeted,*,extractor=parse_original):
    if (pru.get("schema")!="aics-pru-insurers-noacl-nonaccrual-quarterly-original-filing-v1"
        or len(pru.get("events",[]))!=9
        or queue.get("schema")!="aics-priority100-evidence-workbench-v1"
        or queue.get("full_11node_AICS") is not None
        or queue.get("independently_certified_nodes")!=0
        or crosswalk.get("schema")!="aics-PIT100-original-scoring-accession-to-SEC-SGML-crosswalk-v1"
        or len(crosswalk.get("source_claims",[]))!=36):
        raise ValueError("Original PRU source or Priority100 evidence contract invalid")
    tasks={key(t):t for t in queue["priority_queue"] if t["workstream"]=="exact_SEC_source_bytes_and_numeric_replay"}
    base={key(x):x for x in reports["tasks"]}
    new={key(x):x for x in targeted["targeted_source_results"]}
    if len(tasks)!=36:
        raise ValueError("Missing priority SEC document tasks")
    out=[]
    for event in pru["events"]:
        accession=event["accession"]
        k=(str(int(event["cik"])),accession)
        task=tasks.get(k)
        if task is None or task["source_node"]!="Insurers":
            raise ValueError("PRU event missing exact original SEC source claim")
        record={
            "issuer":"PRU","quarter":event["quarter"],"period_end":event["period_end"],
            "CIK":k[0],"accession":accession,
            "original_source_url":event["source_url"],
            "source_numeric_replay_from_current_original_bytes":False,
            "original_report_hash_rechecked":False,
            "historic_first_public_delivery_attested":False,
            "full_insurer_sector_node_certified":False,
            "state":"BLOCKED_SOURCE_OR_ACCOUNTING_DISCREPANCY",
        }
        if task["exact_referenced_document_and_sgml_bytes_rehashed"]:
            if task["archive_origin"]=="targeted_exact_original":
                source=new.get(k)
                path=source.get("original_doc_gzip_archived_path") if source else None
                sha=source.get("original_doc_raw_sha256") if source else None
            else:
                source=base.get(k)
                path=source.get("compressed_archive_path") if source else None
                sha=source.get("raw_SHA256") if source else None
            if path and verify_gzip_original(path,sha):
                record["original_report_hash_rechecked"]=True
                with gzip.open(path,"rb") as f:
                    raw=f.read(48_000_001)
                if len(raw)>48_000_000:
                    raise ValueError("Original source exceeds 48MB")
                original=extractor(raw,period_end=event["period_end"])
                expected_num=int(event["nonaccrual_no_related_acl_usd_m"])
                expected_den=int(event["commercial_mortgage_and_other_loans_net_usd_m"])
                expected_score=Decimal(event["score_pct"])
                matched=(original["numerator_without_related_acl_usd_m"]==expected_num
                         and original["denominator_narrow_commercial_mortgage_other_loans_net_usd_m"]==expected_den
                         and original["ratio_recomputed_pct_2dp"] is not None
                         and Decimal(original["ratio_recomputed_pct_2dp"])==expected_score)
                record.update({
                    "original_parser_result":original,
                    "retrospective_ledger_values_match_original_disclosures":bool(matched),
                    "source_numeric_replay_from_current_original_bytes":bool(matched),
                    "state":"ORIGINAL_ISSUER_NUMERIC_REPLAY_VERIFIED_NOT_PIT"
                        if matched else "BLOCKED_SOURCE_OR_ACCOUNTING_DISCREPANCY",
                    "source_raw_sha256":sha,
                })
        out.append(record)
    if len(out)!=9 or len({x["accession"] for x in out})!=9:
        raise ValueError("PRU original source replay lost quarters")
    return {
        "schema":"aics-pru-9-SEC-original-disclosure-numeric-replay-v1",
        "as_of":queue["as_of"],
        "original_prudential_filing_count":9,
        "original_source_hashes_reverified":sum(x["original_report_hash_rechecked"] for x in out),
        "independently_reproduced_scoped_issuer_research_ratios":
            sum(x["source_numeric_replay_from_current_original_bytes"] for x in out),
        "missing_or_ambiguous_research_ratios":
            sum(not x["source_numeric_replay_from_current_original_bytes"] for x in out),
        "note":"Original issuer disclosure replay is not historical first delivery, AI exposure or insurer sector stress certification",
        "independent_historical_first_delivery":False,
        "independent_24month_oos":False,
        "certified_AICS_nodes":0,
        "production_AICS":None,
        "trades_created":False,
        "events":out,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pru",type=Path,default=PRU)
    p.add_argument("--queue",type=Path,default=QUEUE)
    p.add_argument("--crosswalk",type=Path,default=CROSSWALK)
    p.add_argument("--reports",type=Path,default=REPORTS)
    p.add_argument("--targeted",type=Path,default=TARGETED)
    p.add_argument("--out",type=Path,default=OUT)
    a=p.parse_args()
    files=[a.pru,a.queue,a.crosswalk,a.reports,a.targeted]
    report=replay(*(json.loads(x.read_text(encoding="utf-8")) for x in files))
    report["input_sha256"]={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in files}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="events"}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
