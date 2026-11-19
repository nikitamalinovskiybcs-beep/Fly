#!/usr/bin/env python3
"""Replay distinct MET Q2 and PRU Q3 real SEC credit facts at November 19 cutoff.

This is not a synchronized two-insurer September panel. Both issuers'
December 2025 comparisons were *reported again in later eligible filings*
and must not be relabeled as December-2025 historical PIT deliveries.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_insurers_met_june_original import (
    AS_OF as FROZEN,
    PINNED_FULL_ORIGINAL_SHA256 as MET_SOURCE_SHA,
    PINNED_PRIMARY_DOCUMENT_SHA256 as MET_PRIMARY_SHA,
    build as met_build,
)
from scripts.aics_insurers_pru_credit_asof import build as pru_build

MET_ROOT = Path("aics_data/source_evidence/insurers_met_june_original")
PRU_ROOT = Path("aics_data/source_evidence/insurers_pru_credit_original")
OUTPUT = Path("aics_data/source_evidence/insurers_mixed_original_credit_research.json")
PRU_SOURCE_SHA = "49947c62bc026ff11df94e2c157ac67c18a073c7ec2f4e87f95f7c1645d59b41"
PRU_SOURCE_BYTES = 56_649_032


def pct_change(new: int, old: int) -> str:
    if not (isinstance(new, int) and isinstance(old, int)) or old <= 0:
        raise ValueError("Invalid true-source percentage inputs")
    return str((Decimal(new - old) * 100 / Decimal(old)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP))


def replay(pru_directory: Path, met_directory: Path,
           as_of: dt.date = FROZEN) -> dict:
    if as_of != FROZEN:
        raise ValueError("Only frozen 2026-11-19 SEC +14 research cutoff supported")
    pru = pru_build(pru_directory, fetch=False, as_of=as_of)
    met = met_build((met_directory / "met_q2_original_full_submission.txt").read_bytes(),as_of)
    p = pru["pru"]; pf = p["facts"]; mf = met["facts"]
    if (p["original_sec_bytes_rehashed"] != PRU_SOURCE_BYTES
        or p["original_sec_sha256"] != PRU_SOURCE_SHA
        or met["original_full_submission_sha256"] != MET_SOURCE_SHA
        or met["embedded_primary_10q_sha256"] != MET_PRIMARY_SHA
        or met["period_end"] != "2026-06-30"
        or p["sec_filed_at"] != "2026-11-04"
        or p["sec_available_at"] != "2026-11-18"
        or met["filed_at"] != "2026-08-06"
        or met["sec_available_at"] != "2026-08-20"
        or met["met_september_q3_available_at"] != "2026-11-20"
        or not pru["met_september_10q"]["eligible_at_frozen_cutoff"] is False
        or pru["met_q3_sec_metrics_eligible"] is not False):
        raise ValueError("Unexpected source original, cutoff or historical eligibility")
    before, pru_date, met_date = "2025-12-31", "2026-09-30", "2026-06-30"
    p_loans, p_acl, p_nonaccrual = (
        pf["net_commercial_mortgage_and_other_loans_millions"],
        pf["loan_credit_loss_allowance_millions"],
        pf["nonaccrual_loans_without_related_acl_millions"],
    )
    m_loans, m_acl = mf["mortgage_loans_net_millions"], mf["mortgage_loan_acl_millions"]
    if (p_loans != {before: 64715, pru_date: 67004}
        or p_acl != {before: 469, pru_date: 449}
        or p_nonaccrual != {before: 442, pru_date: 610}
        or m_loans != {before: 84593, met_date: 82856}
        or m_acl != {before: 1193, met_date: 1358}
        or mf["acl_segment_end_millions"] != {
            "commercial": 1016, "agricultural": 107, "residential": 235,
            "total": 1358}):
        raise ValueError("Insurer SEC debt, ACL or nonaccrual numbers no longer match originals")
    if (p_loans[pru_date] - p_loans[before] != pf["loan_net_change_millions"]
        or m_loans[met_date] - m_loans[before] != mf["mortgage_loans_net_change_millions"]
        or m_acl[met_date] - m_acl[before] != mf["mortgage_acl_change_millions"]
        or p_nonaccrual[pru_date] - p_nonaccrual[before]
             != pf["nonaccrual_no_related_allowance_change_millions"]
        or pct_change(p_loans[pru_date],p_loans[before]) != pf["loan_net_change_pct"]
        or pct_change(m_loans[met_date],m_loans[before]) != mf["mortgage_loans_net_change_pct"]
        or pct_change(m_acl[met_date],m_acl[before]) != mf["mortgage_acl_change_pct"]
        or pct_change(p_nonaccrual[pru_date],p_nonaccrual[before])
             != pf["nonaccrual_no_related_allowance_change_pct"]):
        raise ValueError("Original insurer credit arithmetic inconsistent")
    if (mf["acl_segment_six_month_provision_millions"]["total"] != 316
        or mf["net_six_month_chargeoffs_millions"] != 151
        or m_acl[before]+316-151 != m_acl[met_date]):
        raise ValueError("Original MET ACL reconciliation failed")
    return {
        "schema_version": "aics-insurers-asymmetric-two-original-sec-replay-v1",
        "node": "Insurers", "frozen_information_cutoff": as_of.isoformat(),
        "units": "USD millions unless indicated",
        "december_comparatives_available_only_in_later_sec_originals": True,
        "pru_q3": {
            "issuer": "Prudential Financial, Inc.",
            "period_end": pru_date, "sec_filed_at": p["sec_filed_at"],
            "sec_available_at": p["sec_available_at"],
            "original_sha256": p["original_sec_sha256"],
            "source_url": p["original_sec_url"],
            "portfolio_scope": "commercial mortgage and other loans",
            "loans_net_millions": p_loans,
            "loan_change_millions": p_loans[pru_date]-p_loans[before],
            "loan_change_pct": pct_change(p_loans[pru_date],p_loans[before]),
            "credit_loss_allowance_millions": p_acl,
            "acl_change_millions": p_acl[pru_date]-p_acl[before],
            "acl_change_pct": pct_change(p_acl[pru_date],p_acl[before]),
            "nonaccrual_without_related_acl_millions": p_nonaccrual,
            "nonaccrual_subset_change_millions":
                p_nonaccrual[pru_date]-p_nonaccrual[before],
            "nonaccrual_subset_change_pct":
                pct_change(p_nonaccrual[pru_date],p_nonaccrual[before]),
            "all_nonaccrual_loans_millions": None,
        },
        "met_q2": {
            "issuer": "MetLife, Inc.",
            "period_end": met_date, "sec_filed_at": met["filed_at"],
            "sec_available_at": met["sec_available_at"],
            "original_sha256": met["original_full_submission_sha256"],
            "source_url": met["original_sec_url"],
            "portfolio_scope": "mortgage loans (commercial, agricultural, residential)",
            "loans_net_millions": m_loans,
            "loan_change_millions": m_loans[met_date]-m_loans[before],
            "loan_change_pct": pct_change(m_loans[met_date],m_loans[before]),
            "credit_loss_allowance_millions": m_acl,
            "acl_change_millions": m_acl[met_date]-m_acl[before],
            "acl_change_pct": pct_change(m_acl[met_date],m_acl[before]),
            "acl_six_month_provision_millions": 316,
            "acl_six_month_net_chargeoffs_millions": 151,
            "acl_end_commercial_millions": 1016,
        },
        "met_q3": {
            "issuer": "MetLife, Inc.", "period_end": "2026-09-30",
            "sec_filed_at": "2026-11-06", "sec_available_at": "2026-11-20",
            "eligible_at_frozen_cutoff": False,
            "loan_balance_millions": None, "allowance_millions": None,
        },
        "simultaneous_september_2026_coverage_for_both_issuers": False,
        "directly_comparable_portfolio_risk_ratios": False,
        "issuer_risk_ranking_supported": False,
        "historic_release_time_independently_attested": False,
        "statutory_naic_rbc_verified": False,
        "ai_specific_private_credit_exposure": None,
        "synthetic_rows": 0,
        "untouched_24_month_oos": False,
        "insurers_node_score": None, "index_aics": None,
        "promotion": "BLOCKED", "trades_created": False,
        "limitations": [
            "The older MetLife Q2 and newer Prudential Q3 are intentionally different as-of quarterly reporting periods.",
            "PRU no-ACL nonaccrual subset excludes loans with separate credit allowances; not total nonaccrual.",
            "MET gross loan ACL and PRU allowance scopes cannot be mechanically compared as risk rankings.",
            "Dec 2025 comparative numbers are in later filings and do not establish Dec 2025 PIT.",
            "The originals were recaptured retrospectively and do not attest historical release delivery.",
            "NAIC regulatory capital, reinsurance, AI attribution and untouched 24-month OOS missing.",
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pru-directory", type=Path, default=PRU_ROOT)
    p.add_argument("--met-directory", type=Path, default=MET_ROOT)
    p.add_argument("--as-of", type=dt.date.fromisoformat, default=FROZEN)
    p.add_argument("--out", type=Path, default=OUTPUT)
    args = p.parse_args()
    try:
        report = replay(args.pru_directory,args.met_directory,args.as_of)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": type(exc).__name__}))
        return 2
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",
                        encoding="utf-8")
    print(json.dumps({
        "pru_nonaccrual_no_acl_pct_change": report["pru_q3"]["nonaccrual_subset_change_pct"],
        "met_mortgage_acl_change_pct": report["met_q2"]["acl_change_pct"],
        "met_q3_eligible": False,
        "index_aics": None, "promotion": "BLOCKED"}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
