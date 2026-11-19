"""Replay CoreWeave and Nebius cash investment coverage from original SEC filings."""
from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple

from scripts.aics_observed_source_review import (
    dollars,
    filing_document,
    percent,
    read_original,
    words,
)

REGISTRY = Path("aics_data/source_registry/neocloud_cash_h1_sec.json")
REPORT = Path("aics_data/research/neocloud_cash_coverage_2026_h1.json")
CUTOFF = date(2026, 11, 18)
CASH_SOURCES = ("crwv_25_h1", "crwv_26_q1", "crwv_26_release", "crwv_26_h1",
                "nbis_25_h1", "nbis_26_q1", "nbis_26_release", "nbis_26_h1")


class Cash(NamedTuple):
    operations: Decimal
    purchases: Decimal  # Positive outflow
    deferred: Decimal | None


def core_cash(doc, end):
    root = ET.fromstring(doc)
    period = (end[:4] + "-01-01", end)
    return Cash(*(dollars(root, "us-gaap:" + tag, "1769628", period) / 1_000_000
                  for tag in ("NetCashProvidedByUsedInOperatingActivities",
                              "PaymentsToAcquirePropertyPlantAndEquipment",
                              "IncreaseDecreaseInContractWithCustomerLiability")))


def rows(doc):
    return [" ".join(words(tr).replace("\u200b", " ").split())
            for tr in re.findall(rb"<tr\b[^>]*>.*?</tr>", doc, re.IGNORECASE | re.DOTALL)]


def column(table, label, index, width, growth_columns=False, *, reported_nil=False):
    values = set()
    for row in table:
        if not row.startswith(label + " "):
            continue
        rest = row[len(label):].replace("$", "").replace(",", "")
        if growth_columns:  # The 2025 Nebius summary interleaves percentage columns.
            rest = re.sub(r"\d+\s*%", "", rest)
        cells = re.sub(r"\(\s*(\d+(?:\.\d+)?)\s*\)", r"-\1", rest).split()
        if reported_nil:
            cells = ["0" if cell == "—" else cell for cell in cells]
        if len(cells) == width and all(re.fullmatch(r"-?\d+(?:\.\d+)?", v) for v in cells):
            values.add(Decimal(cells[index]))
    if len(values) != 1:
        raise ValueError(f"Missing or conflicting source column for {label}")
    return values.pop()


def statement_cash(table, index, width, *, core=False):
    operations = ("Net cash provided by (used in) operating activities" if core else
                  "Net cash provided by / (used in) operating activities – continuing operations")
    purchases = ("Purchase of property and equipment, including capitalized internal-use software" if core else
                 "Purchases of property and equipment and intangible assets")
    return Cash(column(table, operations, index, width), -column(table, purchases, index, width),
                column(table, "Deferred revenue", index, width))


def facility_rows(doc):
    table, text = "\n".join(rows(doc)), words(doc)
    result = []
    for facility, borrower, terms, recourse in (
        ("4.0", "CoreWeave Compute Acquisition Co. VIII, LLC",
         ("The DDTL 4.0 Facility is non-recourse, except for limited guarantees related to customary "
          "non-recourse carve-out obligations"), "Non-recourse except for customary limited guarantees"),
        ("5.0", "CoreWeave Financing DDTL V, LLC",
         "all obligations under the DDTL 5.0 Facility are unconditionally guaranteed by the Company",
         "Unconditional parent guarantee"),
    ):
        label = "^DDTL " + re.escape(facility) + " Facility "
        balance = re.findall(label + r"[A-Za-z]{3} 203\d \d+ % ([\d,]+) —$", table, re.MULTILINE)
        capacity = re.findall(label + r"[A-Za-z]+ 2026 [^\n]+ \$ ([\d,]+)$", table, re.MULTILINE)
        if len(balance) != 1 or len(capacity) != 1 or borrower not in text or terms.lower() not in text.lower():
            raise ValueError("Cannot reconcile the amount and recourse for " + facility)
        result.append({"facility": "DDTL " + facility, "borrower": borrower,
                       "reported_debt_usd_m": int(balance[0].replace(",", "")),
                       "facility_ceiling_usd_m": int(capacity[0].replace(",", "")),
                       "recourse": recourse})
    return result


def source_documents(registry, keys, originals, fetch, *, reuse_verified=False):
    docs = {}
    for key in keys:
        item = registry[key]
        available = date.fromisoformat(item["filed_at"]) + timedelta(days=14)
        if available.isoformat() != item["available_at"] or available > CUTOFF:
            raise ValueError("SEC availability outside the review cutoff")
        try:
            raw = read_original(originals, key, item["original"], fetch and not reuse_verified)
        except (FileNotFoundError, ValueError):
            if not (fetch and reuse_verified):
                raise
            raw = read_original(originals, key, item["original"], True)
        docs[key] = filing_document(raw, item, item["source_page"].rsplit("/", 1)[1])
    return docs


def build(originals, fetch):
    registry = json.loads(REGISTRY.read_text())
    docs = source_documents(registry, CASH_SOURCES, originals, fetch)

    c_prior = core_cash(docs["crwv_25_h1"], "2025-06-30")
    c_q1 = core_cash(docs["crwv_26_q1"], "2026-03-31")
    c_h1 = core_cash(docs["crwv_26_h1"], "2026-06-30")
    c_q2 = Cash(*(half - first for half, first in zip(c_h1, c_q1)))
    c_release = rows(docs["crwv_26_release"])  # Q2 2026/25, then H1 2026/25.
    if (statement_cash(c_release, 0, 4, core=True) != c_q2
            or statement_cash(c_release, 2, 4, core=True) != c_h1):
        raise ValueError("CoreWeave quarter and half-year do not match the 8-K")

    n_prior_table = rows(docs["nbis_25_h1"])
    n_prior = Cash(column(n_prior_table, "Cash used in operating activities – continuing operations",
                          3, 4, growth_columns=True),
                   -column(n_prior_table, "Purchases of property, plant and equipment",
                           3, 4, growth_columns=True), None)
    n_q1 = statement_cash(rows(docs["nbis_26_q1"]), 1, 2)
    n_release = rows(docs["nbis_26_release"])  # Q2 2025/26, then H1 2025/26.
    n_q2 = statement_cash(n_release, 1, 4)
    n_h1 = statement_cash(rows(docs["nbis_26_h1"]), 1, 2)
    if (statement_cash(n_release, 3, 4) != n_h1
            or any(a + b != h for a, b, h in zip(n_q1, n_q2, n_h1))
            or statement_cash(n_release, 2, 4)[:2] != n_prior[:2]):
        raise ValueError("Nebius continuing cash flows do not reconcile across filings")

    observations = []
    for issuer, period, flow, first, checks in (
        ("CoreWeave", "2025-H1", c_prior, "crwv_25_h1", []),
        ("CoreWeave", "2026-Q1", c_q1, "crwv_26_q1", []),
        ("CoreWeave", "2026-Q2", c_q2, "crwv_26_release", ["crwv_26_q1", "crwv_26_h1"]),
        ("CoreWeave", "2026-H1", c_h1, "crwv_26_release", ["crwv_26_h1"]),
        ("Nebius", "2025-H1", n_prior, "nbis_25_h1", []),
        ("Nebius", "2026-Q1", n_q1, "nbis_26_q1", []),
        ("Nebius", "2026-Q2", n_q2, "nbis_26_release", ["nbis_26_q1", "nbis_26_h1"]),
        ("Nebius", "2026-H1", n_h1, "nbis_26_release", ["nbis_26_h1"]),
    ):
        if flow.purchases <= 0:
            raise ValueError("Expected positive cash purchases in these statements")
        observations.append({
            "issuer": issuer, "period": period, "source": first, "cross_checks": checks,
            "available_from_cited_source": registry[first]["available_at"],
            "all_cited_checks_available": max(registry[k]["available_at"] for k in [first, *checks]),
            "operating_cash_flow": flow.operations, "cash_purchases": flow.purchases,
            "operating_cash_less_purchases": flow.operations - flow.purchases,
            "operating_cash_pct_of_purchases": percent(flow.operations, flow.purchases),
            "change_in_deferred_revenue_in_operating_cash_flow": flow.deferred,
        })

    return {"source_cutoff": CUTOFF.isoformat(), "units": "USD million, except percentages",
            "registry": str(REGISTRY), "observations": observations,
            "purchase_scope": {
                "CoreWeave": "Cash PP&E purchases including capitalized internal-use software.",
                "Nebius": "Continuing operations. In 2026 cash purchases include PP&E and intangibles. "
                          "The 2025 release labels purchases as PP&E. Its H1 amount matches the 2026 comparative."},
            "coreweave_facilities": {"as_of": "2026-06-30", "source": "crwv_26_h1",
                                     "available_at": registry["crwv_26_h1"]["available_at"],
                                     "facilities": facility_rows(docs["crwv_26_h1"])},
            "node_score": None, "index_aics": None,
            "production_weights_changed": False, "verdict_mutated": False, "trades_created": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--originals", type=Path, required=True)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--out", type=Path, default=REPORT)
    args = parser.parse_args()
    result = build(args.originals, args.fetch)
    args.out.write_text(json.dumps(result, default=lambda n: format(n, "f"), indent=2) + "\n")
