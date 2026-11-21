"""AICS V31: dual-clock interest burden, repo proxy and matched-loan repricing gate.

The issuer's 2026 Q3 investor-relations release is accessible research, but
its corresponding SEC 10-Q is not eligible for AICS until filed_at + 14
calendar days (November 26). Even then historical publication/PIT and a
same-instrument repricing pair are not independently established.

No invented same-loan rates, issuer-specific repo loan, coverage ratio,
probability, production score, or trade.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_v30_cashflow_financing_bridge import build as funding_build, FUNDING, CASH, SEC, read

ROOT=Path("aics_data/research")
INTEREST=ROOT/"coreweave_q3_ir_interest_burden_2026-11-18.json"
REPO=ROOT/"repo_24_month_observed_research_2026-11-18.json"
OUTPUT=ROOT/"aics_v31_interest_repo_dual_clock_research_2026-11-22.json"
SEC_Q3_FILED="2026-11-12"
SEC_Q3_AVAILABLE="2026-11-26"
IR_FIRST_RELEASE="2026-11-10"


def d(value):
    if isinstance(value, bool):
        raise ValueError("Cannot treat Boolean as numeric evidence")
    n=Decimal(str(value))
    if not n.is_finite():
        raise ValueError("Invalid numeric value")
    return n


def day(date):
    return dt.date.fromisoformat(date)


def build(ir,repo,funding,*,as_of):
    if isinstance(as_of,str):as_of=day(as_of)
    if not isinstance(as_of,dt.date) or isinstance(as_of,dt.datetime):
        raise ValueError("Calendar date cutoff required")
    if sum(WEIGHTS.values())!=1050:
        raise ValueError("Frozen 11-node weights altered")
    if (
        ir.get("schema_version")!="aics-neocloud-ir-descriptive-research-v1"
        or ir.get("issuer")!="CoreWeave"
        or ir.get("source_id")!="CRWV_2026Q3"
        or ir.get("quarter_end")!="2026-09-30"
        or ir.get("source_release_date")!=IR_FIRST_RELEASE
        or ir.get("sec_10q_filed_at")!=SEC_Q3_FILED
        or ir.get("sec_10q_aics_available_at")!=SEC_Q3_AVAILABLE
        or day(ir["sec_10q_aics_available_at"])!=day(ir["sec_10q_filed_at"])+dt.timedelta(days=14)
        or ir.get("source_url")!="https://investors.coreweave.com/news/news-details/2026/CoreWeave-Reports-Strong-Third-Quarter-2026-Results/"
        or ir.get("source_bytes_independently_hash_checked") is not True
        or len(ir.get("original_ir_html_sha256",""))!=64
        or ir.get("quarter_revenue_usd_millions")!=3661
        or ir.get("quarter_net_interest_expense_usd_millions")!=846
        or ir.get("original_sec_filing_pit_certified") is not False
        or ir.get("independent_source_vintage_certified") is not False
        or ir.get("index_aics") is not None
        or ir.get("neocloud_stress_score") is not None
        or ir.get("trades_created") is not False):
        raise ValueError("IR Q3 interest data have wrong date, source or PIT claim")
    ratio=(d(ir["quarter_net_interest_expense_usd_millions"])/
           d(ir["quarter_revenue_usd_millions"])*100)
    if (
        ratio.quantize(Decimal("0.1"),rounding=ROUND_HALF_UP)!=d(ir["descriptive_net_interest_expense_divided_by_revenue_pct"])
        or abs(float(ratio)-float(ir["arithmetic_unrounded_pct"]))>0.000001
    ):
        raise ValueError("Net interest-to-revenue descriptive arithmetic inconsistent")
    if (
        funding.get("schema")!="aics-v30-issuer-cashflow-financing-identity-source-gated-research-v1"
        or funding.get("as_of")!=as_of.isoformat()
        or funding.get("historically_comparable_matched_borrower_pricing_event_count")!=0
        or funding.get("credit_spread_repricing_on_matched_instrument_bps") is not None
        or funding.get("full_aics") is not None
        or funding.get("crisis_probability") is not None
        or funding.get("trades_created") is not False
    ):
        raise ValueError("Noncomparable Q2 financing data cannot price Q3 lender cost")
    q2=[x for x in funding["issuer_quarter_observations"]
        if x.get("issuer")=="CoreWeave" and x.get("period")=="2026-Q2"]
    if (len(q2) not in (0,1)
        or (len(q2)==1 and (
            q2[0]["source_eligible_at"]!="2026-08-26"
            or q2[0]["ocf_less_purchases_usd_m"]!="-5743"
            or q2[0]["net_financing_cash_usd_m"]!="10071"
        ))):
        raise ValueError("Q2 cashflow provenance broken")
    if (
        repo.get("schema_version")!="aics-repo-24-matched-source-observed-rates-v2"
        or repo.get("fixed_node")!="Repo"
        or repo.get("fixed_node_weight")!=100
        or repo.get("observed_months")!=24
        or repo.get("missing_months")!=0
        or repo.get("synthetic_market_rows")!=0
        or repo.get("date_range")!=["2024-11-30","2026-10-31"]
        or repo.get("source_release_timestamp_pit_attested") is not False
        or repo.get("contemporaneous_alfred_snapshots_attested") is not False
        or repo.get("independent_24_month_oos") is not False
        or repo.get("stress_score") is not None
        or repo.get("index_aics") is not None
        or repo.get("promotion")!="BLOCKED"
    ):
        raise ValueError("Retrospective repo proxy wrongly advertised as issuer credit rate or vintage")
    rows=repo.get("monthly_observations",[])
    if len(rows)!=24 or len({r["as_of"] for r in rows})!=24:
        raise ValueError("Repo history must have 24 unique actual months")
    latest=None
    for row in rows:
        if not (day(row["market_effective_date"])<=day(row["publication_proxy_date"])<=
                day(row["as_of"])):
            raise ValueError("Repo market effective date must precede publication proxy")
        if (d(row["sofr_pct"])-d(row["iorb_pct"]))*100!=d(row["sofr_minus_iorb_bps"]):
            raise ValueError("Repo SOFR-IORB spread wrong")
        if (d(row["sofr_pct"])-d(row["bgcr_pct"]))*100!=d(row["sofr_minus_bgcr_bps"]):
            raise ValueError("Repo SOFR-BGCR spread wrong")
        if day(row["publication_proxy_date"])<=as_of:
            if latest is None or row["as_of"]>latest["as_of"]:
                latest=row
    if rows[-2]["as_of"]!="2026-09-30" or rows[-1]["as_of"]!="2026-10-31":
        raise ValueError("Repo October 2026 tail mismatched")
    if (
        rows[-2]["sofr_minus_iorb_bps"]!=-2
        or rows[-1]["sofr_minus_iorb_bps"]!=4
        or rows[-1]["sofr_minus_bgcr_bps"]!=2
        or rows[-1]["publication_proxy_date"]!="2026-10-30"
    ):
        raise ValueError("Original retrospectively observed October repo series changed")
    ir_visible=as_of>=day(IR_FIRST_RELEASE)
    sec_date_eligible=as_of>=day(SEC_Q3_AVAILABLE)
    ir_panel=({
        "issuer":"CoreWeave",
        "quarter":"2026-Q3",
        "source":"2026-11-10 issuer IR original release with hashed bytes",
        "issuer_IR_publication_date":IR_FIRST_RELEASE,
        "SEC_10Q_file_date":SEC_Q3_FILED,
        "AICS_SEC_plus14_available_at":SEC_Q3_AVAILABLE,
        "quarter_revenue_usd_m":3661,
        "quarter_net_interest_expense_usd_m":846,
        "net_interest_expense_divided_by_revenue_pct":"23.1",
        "ratio_is_not_interest_coverage_or_covenant_DSCR":True,
        "issuer_research_release_visible":True,
        "SEC_date_gate_passed":sec_date_eligible,
        "SEC_first_delivery_historical_PIT_attested":False,
        "AICS_model_eligible":False,
    } if ir_visible else None)
    return {
        "schema":"aics-v31-dual-clock-interest-repo-matched-loan-research-v1",
        "as_of":as_of.isoformat(),
        "issuer_IR_Q3_research":ir_panel,
        "interest_research_visible_as_of":ir_visible,
        "Q3_SEC_10Q_date_gate_passed_as_of":sec_date_eligible,
        "original_2026_Q3_SEC_eligible_at":SEC_Q3_AVAILABLE,
        "Q3_public_IR_does_not_override_AICS_SEC_rule":True,
        "Q3_SEC_date_gate_alone_is_not_historical_PIT_certification":True,
        "asof_source_status":(
            "NOT_YET_RELEASED" if not ir_visible else
            "IR_RESEARCH_ONLY_SEC_DATE_EMBARGO" if not sec_date_eligible else
            "SEC_DATE_PASSED_BUT_HISTORICAL_PIT_UNATTESTED"
        ),
        "coreweave_source_reconciled_Q2_cash_gap_usd_m":
            q2[0]["ocf_less_purchases_usd_m"] if q2 else None,
        "coreweave_source_reconciled_Q2_net_financing_usd_m":
            q2[0]["net_financing_cash_usd_m"] if q2 else None,
        "repo_retrospective_latest_observed_month":latest["as_of"] if latest else None,
        "repo_latest_month_sofr_minus_iorb_bps":
            latest["sofr_minus_iorb_bps"] if latest else None,
        "repo_latest_month_sofr_minus_bgcr_bps":
            latest["sofr_minus_bgcr_bps"] if latest else None,
        "repo_october_minus_september_sofr_iorb_bps":
            (rows[-1]["sofr_minus_iorb_bps"]-rows[-2]["sofr_minus_iorb_bps"])
            if latest and latest["as_of"]>="2026-10-31" else None,
        "repo_series_is_issuer_specific_funding_spread":False,
        "repo_historical_vintage_independently_certified":False,
        "matched_same_loan_spread_repricing_events_verified":0,
        "matched_same_loan_repricing_bps":None,
        "coreweave_actual_coupon_paid":None,
        "bank_by_bank_exposure":None,
        "2000_similarity_percent":None,
        "2008_similarity_percent":None,
        "early_warning_skill":None,
        "crisis_probability":None,
        "full_11node_aics":None,
        "aics_node_scores_approved":0,
        "weights_total_unchanged":1050,
        "production_weights_changed":False,
        "trades_created":False,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of",default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    parser.add_argument("--out",type=Path,default=OUTPUT)
    a=parser.parse_args()
    fund=funding_build(read(FUNDING),read(CASH),read(SEC),as_of=a.as_of)
    report=build(read(INTEREST),read(REPO),fund,as_of=a.as_of)
    report["source_file_sha256"]={
        str(p):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (INTEREST,REPO,FUNDING,CASH,SEC)
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({
        "interest_visible":report["interest_research_visible_as_of"],
        "sec_eligible_asof":report["Q3_SEC_10Q_date_gate_passed_as_of"],
        "ratio_pct":report["issuer_IR_Q3_research"]["net_interest_expense_divided_by_revenue_pct"]
                    if report["issuer_IR_Q3_research"] else None,
        "matched_loan_repricing_events":0,
        "production_index":None,
    }))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
