#!/usr/bin/env python3
"""Original SEC 10-Q: PRU credit-quality research at frozen 2026-11-19.

Protect the mixed SEC information set: PRU September 10-Q filed 2026-11-04
becomes eligible 2026-11-18; MET September 10-Q filed 2026-11-06 becomes
eligible only 2026-11-20 and MUST NOT be used on November 19. This replay
does not retrospectively certify SEC provider-delivery timestamps.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_observed_source_review import (
    REGISTRY, checked_original, dollars, filing_document, read_original, words,
)

AS_OF = dt.date(2026, 11, 19)
MET_Q3 = {
    "issuer": "MET", "cik": "1099219",
    "accession": "0001099219-26-000062", "form": "10-Q",
    "filed_at": "2026-11-06", "period_end": "2026-09-30",
    "sec_filing_index_url":
        "https://www.sec.gov/Archives/edgar/data/1099219/000109921926000062/"
        "0001099219-26-000062-index.htm",
}
NONACCRUAL = re.compile(
    r"Loans on non-accrual status that did not have a related allowance for "
    r"credit losses were [$] ([0-9,]+) million and [$] ([0-9,]+) million "
    r"as of September 30, 2026 and December 31, 2025, respectively",
    flags=re.IGNORECASE,
)


def safe_dates(as_of: dt.date = AS_OF) -> tuple[dict, dict]:
    """Freeze eligible PRU source; MET quarterly filing remains under embargo."""
    if as_of != AS_OF:
        raise ValueError("Frozen insurer Q3 analysis is only 2026-11-19")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    pru = registry["sources"]["pru"]
    if (pru["cik"] != "1137774"
            or pru["accession"] != "0001137774-26-000221"
            or pru["form"] != "10-Q"
            or pru["filed_at"] != "2026-11-04"
            or pru["available_at"] != "2026-11-18"
            or pru["source_page"] !=
                "https://www.sec.gov/Archives/edgar/data/1137774/"
                "000113777426000221/pru-20260930.htm"):
        raise ValueError("PRU original issuer/accession/date changed")
    if (dt.date.fromisoformat(pru["filed_at"]) + dt.timedelta(days=14)
            != dt.date.fromisoformat(pru["available_at"])):
        raise ValueError("PRU SEC +14 mismatch")
    met_eligible = dt.date.fromisoformat(MET_Q3["filed_at"]) + dt.timedelta(days=14)
    if met_eligible <= as_of or dt.date.fromisoformat(pru["available_at"]) > as_of:
        raise ValueError("SEC +14 eligibility chronology changed")
    return pru, {**MET_Q3, "available_at": met_eligible.isoformat(),
                 "eligible_at_frozen_cutoff": False,
                 "sept_2026_q3_balance_sheet_values_used": False,
                 "net_mortgage_loans_usd": None,
                 "credit_allowance_usd": None,
                 "reason": "FORM_10Q_UNAVAILABLE_UNDER_SEC_14_DAY_EMBARGO"}


def million(value: Decimal) -> int:
    if value != value.to_integral_value() or value < 0 or value % 1_000_000:
        raise ValueError("Unexpected non-million or negative SEC monetary unit")
    return int(value / 1_000_000)


def percent(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        raise ValueError("Cannot divide by nonpositive source amount")
    return str((Decimal(numerator) * 100 / Decimal(denominator)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP))


def parse_pru_credit(original_xml: bytes) -> dict:
    """Recompute balance-sheet and separately scoped nonaccrual original facts."""
    root = ET.fromstring(original_xml)
    loan, assets, allowances = {}, {}, {}
    for day in ("2025-12-31", "2026-09-30"):
        loan[day] = million(dollars(root, "pru:Commercialmortgageandotherloans",
                                  "1137774", (day,)))
        assets[day] = million(dollars(root, "us-gaap:Assets", "1137774", (day,)))
        allowances[day] = million(dollars(
            root, "us-gaap:FinancingReceivableAllowanceForCreditLosses",
            "1137774", (day,)))
    # Anchored original note, not all nonaccruals: these *lack* a related ACL.
    narrative = words(original_xml)
    matches = {m.groups() for m in NONACCRUAL.finditer(narrative)}
    if len(matches) != 1:
        raise ValueError("Missing/ambiguous nonaccrual WITHOUT allowance footnote")
    now, previous = (int(v.replace(",", "")) for v in next(iter(matches)))
    if now < 0 or previous < 0:
        raise ValueError("Negative nonaccrual subset is impossible")
    current, prior = "2026-09-30", "2025-12-31"
    delta_loan = loan[current] - loan[prior]
    return {
        "units": "USD millions unless percentage is indicated",
        "observation_dates": [prior, current],
        "net_commercial_mortgage_and_other_loans_millions": {
            prior: loan[prior], current: loan[current]},
        "total_assets_millions": {prior: assets[prior], current: assets[current]},
        "loan_credit_loss_allowance_millions": {
            prior: allowances[prior], current: allowances[current]},
        "nonaccrual_loans_without_related_acl_millions": {
            prior: previous, current: now},
        "loan_net_change_millions": delta_loan,
        "loan_net_change_pct": percent(delta_loan, loan[prior]),
        "loan_pct_total_assets": {
            prior: percent(loan[prior], assets[prior]),
            current: percent(loan[current], assets[current])},
        "allowance_change_millions": allowances[current] - allowances[prior],
        "allowance_over_net_loan_plus_allowance_pct_proxy": {
            prior: percent(allowances[prior], loan[prior] + allowances[prior]),
            current: percent(allowances[current], loan[current] + allowances[current])},
        "nonaccrual_no_related_allowance_change_millions": now - previous,
        "nonaccrual_no_related_allowance_change_pct": percent(
            now - previous, previous),
        "all_nonaccrual_loans_total_millions": None,
        "private_credit_exposure_millions": None,
        "ai_related_loan_exposure_millions": None,
        "risk_based_capital_ratio": None,
        "naic_risk_classification_attested": False,
        "caveats": [
            "Commercial mortgage and other loans includes non-AI assets and fair-value-option loans.",
            "ACL/(reported net loan balance+ACL) is a mechanical descriptive proxy, NOT an audited coverage ratio for only amortized-cost loans.",
            "Nonaccrual loans WITHOUT an associated ACL are a subset, not total nonperforming loans and not realized defaults.",
            "Comparative December 2025 balance appears in a 2026 November filing; it is NOT an independently captured December 2025 vintage.",
            "Nine-month change (Dec 2025 to Sep 2026) is NOT a year-over-year or quarter-over-quarter rate.",
        ],
    }


def build(directory: Path, *, fetch: bool = False, as_of: dt.date = AS_OF) -> dict:
    pru, met = safe_dates(as_of)
    raw = read_original(directory, "pru", pru["original"], fetch)
    checked_original(raw, pru["original"])
    primary = filing_document(raw, pru, "pru-20260930.htm")
    metrics = parse_pru_credit(primary)
    if (metrics["net_commercial_mortgage_and_other_loans_millions"]["2026-09-30"] * 1_000_000
            != 67_004_000_000
            or metrics["total_assets_millions"]["2026-09-30"] * 1_000_000
            != 771_378_000_000):
        # Reconcile an *independent existing primary-source observed review*
        # without substituting old price/candidate data into a new history.
        raise ValueError("PRU balance no longer matches independently reviewed 10-Q facts")
    return {
        "schema_version": "aics-insurers-pru-credit-original-asof-2026-11-19-v1",
        "node": "Insurers",
        "as_of": as_of.isoformat(),
        "source_count_used_for_numeric_metrics": 1,
        "pru": {
            "issuer": "Prudential Financial, Inc.",
            "sec_filed_at": pru["filed_at"],
            "sec_available_at": pru["available_at"],
            "original_sec_url": pru["original"]["url"],
            "original_sec_bytes_rehashed": len(raw),
            "original_sec_sha256": hashlib.sha256(raw).hexdigest(),
            "embedded_primary_document_sha256": pru["document_text_sha256"],
            "facts": metrics,
        },
        "met_september_10q": met,
        "met_q3_sec_metrics_eligible": False,
        "independently_captured_historical_pit": False,
        "historical_as_of_snapshot_reconstituted": False,
        "non_pit_delayed_original_capture": True,
        "untouched_24_month_oos": False,
        "insurers_node_score": None,
        "index_aics": None,
        "promotion": "BLOCKED",
        "trades_created": False,
        "limitations": [
            "This is a strict SEC-date eligible original filing research slice, not independent historical delivery-time attestation.",
            "MetLife Q3 2026 10-Q filed November 6 and may enter AICS only on November 20; no MetLife Q3 numbers are used.",
            "Prudential Q3 10-Q filed November 4 and first passes the 14 calendar day rule on November 18.",
            "No NAIC statutory capital, reinsurance credit-risk attribution, contract-specific AI private loan exposure or certified score.",
            "Original source bytes remain in a temporary GitHub Actions artifact; source SHA persists in the research receipt.",
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--directory", type=Path,
                   default=Path("aics_data/source_evidence/insurers_pru_credit_original"))
    p.add_argument("--out", type=Path,
                   default=Path("aics_data/source_evidence/insurers_pru_credit_original/research.json"))
    p.add_argument("--fetch", action="store_true")
    p.add_argument("--as-of", type=dt.date.fromisoformat, default=AS_OF)
    args = p.parse_args()
    try:
        result = build(args.directory, fetch=args.fetch, as_of=args.as_of)
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": type(exc).__name__}))
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(json.dumps({
        "pru_net_credit_2026_09_millions": result["pru"]["facts"]["net_commercial_mortgage_and_other_loans_millions"]["2026-09-30"],
        "pru_nonaccrual_without_allowance_millions": result["pru"]["facts"]["nonaccrual_loans_without_related_acl_millions"]["2026-09-30"],
        "met_q3_10q_available_at": result["met_september_10q"]["available_at"],
        "met_q3_10q_eligible": False,
        "index_aics": None, "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
