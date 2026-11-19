"""Reconcile June-quarter cash funding and identify disclosed investor and customer payments."""
from __future__ import annotations

import argparse
import json
from decimal import Decimal
from functools import partial
from pathlib import Path

from scripts.aics_neocloud_cash_coverage import (
    CUTOFF,
    REGISTRY,
    column,
    core_cash,
    rows,
    source_documents,
    statement_cash,
)
from scripts.aics_observed_source_review import captures, percent, words

REPORT = Path("aics_data/research/neocloud_q2_funding_2026.json")
KEYS = ("crwv_26_q1", "crwv_26_release", "crwv_26_h1", "nbis_26_q1",
        "nbis_26_release", "nbis_26_h1", "crwv_jane_8k", "crwv_proxy")


def quarter_bridge(issuer, docs, registry):
    core = issuer == "CoreWeave"
    prefix, position = ("crwv", 0) if core else ("nbis", 1)
    march_key, release_key, june_key = (prefix + "_26_" + part for part in ("q1", "release", "h1"))
    release, march, june = (rows(docs[k]) for k in (release_key, march_key, june_key))
    quarter_amount = partial(column, release, index=position, width=4, reported_nil=True)
    march_amount = partial(column, march, index=position, width=2, reported_nil=True)
    june_amount = partial(column, june, index=position, width=2, reported_nil=True)
    quarter = statement_cash(release, position, 4, core=core)
    quarter_gap = quarter.purchases - quarter.operations

    financing = "Net cash provided by financing activities"
    investing = "Net cash used in investing activities"
    march_financing = financing if core else "Net cash provided by / (used in) financing activities"
    investing_cash, financing_cash = quarter_amount(investing), quarter_amount(financing)
    if (investing_cash != june_amount(investing) - march_amount(investing)
            or financing_cash != june_amount(financing) - march_amount(march_financing)):
        raise ValueError(f"{issuer}: Q2 investing or financing differs from H1 less Q1")

    if core:
        first = core_cash(docs[march_key], "2026-03-31")
        half = core_cash(docs[june_key], "2026-06-30")
        components = {
            "debt_issuance_net_of_costs": quarter_amount("Proceeds from issuance of debt, net"),
            "debt_repayments": quarter_amount("Repayments of debt"),
            "private_placement_net_of_costs": quarter_amount("Issuance of common stock in private placements, net of issuance costs"),
            "capped_calls": quarter_amount("Purchase of capped calls related to convertible senior notes"),
            "other_financing": quarter_amount("Other financing activities"),
        }
        cash_label = "Cash and cash equivalents"
        restricted = "Restricted cash and cash equivalents, "
        restricted_begin = march_amount(restricted + "current") + march_amount(restricted + "non-current")
        restricted_end = june_amount(restricted + "current") + june_amount(restricted + "non-current")
        total_label = "Cash, cash equivalents, and restricted cash—"
        begin_label, end_label = total_label + "beginning of period", total_label + "end of period"
        change = quarter_amount("Net increase (decrease) in cash, cash equivalents, and restricted cash")
        fx = None  # No exchange-rate line appears in this cash-flow statement.
    else:
        first, half = statement_cash(march, 1, 2), statement_cash(june, 1, 2)
        if quarter_amount("Net cash provided by / (used in) operating activities") != quarter.operations:
            raise ValueError("Nebius: continuing and consolidated Q2 operating cash differ")
        components = {
            "convertible_notes_issued": quarter_amount("Proceeds from issuance of convertible notes"),
            "convertible_notes_issuance_costs": quarter_amount("Convertible notes issuance costs"),
            "treasury_share_sale": quarter_amount("Proceeds from sale of treasury shares"),
            "treasury_share_issuance_costs": quarter_amount("Treasury shares issuance costs"),
            "prefunded_warrant_issuance": quarter_amount("Proceeds from issuance of pre-funded warrants"),
            "option_exercises": quarter_amount("Proceeds from exercise of share options"),
            "withholding_tax": quarter_amount("Withholding tax paid"),
        }
        cash_label = "Cash and cash equivalents, end of period"
        restricted_label = "Restricted cash and cash equivalents, end of period"
        restricted_begin, restricted_end = march_amount(restricted_label), june_amount(restricted_label)
        total_label = "Cash and cash equivalents, and restricted cash and cash equivalents, "
        begin_label, end_label = total_label + "beginning of period", total_label + "end of period"
        change = quarter_amount("Net change in cash and cash equivalents, and restricted cash and cash equivalents")
        fx = quarter_amount("Effect of exchange rate changes on cash and cash equivalents, and restricted cash and cash equivalents")

    if any(q1 + q2 != h1 for q1, q2, h1 in zip(first, quarter, half)):
        raise ValueError(f"{issuer}: Q2 operating cash, purchases or deferred revenue differs from H1 less Q1")
    begin, end = quarter_amount(begin_label), quarter_amount(end_label)
    cash_begin, cash_end = march_amount(cash_label), june_amount(cash_label)
    if (begin != cash_begin + restricted_begin or end != cash_end + restricted_end
            or begin != march_amount(end_label) or end != june_amount(end_label)
            or end - begin != change or sum(components.values()) != financing_cash
            or quarter.operations + investing_cash + financing_cash + (fx or 0) != change):
        raise ValueError(f"{issuer}: quarterly cash bridge does not reconcile")
    return {
        "issuer": issuer, "period": "2026-Q2", "sources": [march_key, release_key, june_key],
        "available_with_all_checks": max(registry[k]["available_at"] for k in (march_key, release_key, june_key)),
        "cash_purchases_less_operating_cash": quarter_gap,
        "q2_percent_of_h1_purchase_gap": percent(quarter_gap, half.purchases - half.operations),
        "other_net_investing_cash_beyond_purchases": investing_cash + quarter.purchases,
        "net_investing_cash": investing_cash, "financing_components_signed": components,
        "net_financing_cash": financing_cash, "separately_reported_exchange_effect": fx,
        "cash_including_restricted": {"start": begin, "end": end, "change": change},
        "cash_and_equivalents_excluding_restricted": {"start": cash_begin, "end": cash_end, "change": cash_end - cash_begin},
        "restricted_cash_and_equivalents": {"start": restricted_begin, "end": restricted_end, "change": restricted_end - restricted_begin},
    }


def counterparty_disclosures(docs, registry):
    proxy, sale = words(docs["crwv_proxy"]), words(docs["crwv_jane_8k"])
    records = []
    for name in ("Jane Street", "NVIDIA"):
        fy, q1 = captures(
            r"For the year ended December 31, 2025 and the three months ended March 31, 2026, "
            + name + r" has paid us an aggregate of approximately \$([\d,.]+) million and \$([\d,.]+) million",
            proxy,
        )
        records.append({"payer": name, "recipient": "CoreWeave", "type": "service_payments_approximate",
                        "2025-FY": fy, "2026-Q1": q1, "source": "crwv_proxy",
                        "available_from_cited_source": registry["crwv_proxy"]["available_at"]})
    if "Jane Street Global Trading, LLC" not in sale or "issued and sold to Jane Street" not in sale:
        raise ValueError("CoreWeave: cannot identify the April equity buyer")
    js_shares, js_price, js_billions = captures(
        r"completed the issuance and sale of ([\d,]+) shares.{0,200}?at a price of \$([\d.]+) "
        r"per share for an aggregate purchase price of approximately \$([\d.]+) billion in cash", sale,
    )
    nv_shares, nv_price, nv_billions = captures(
        r"sale of ([\d,]+) shares of our Class A common stock to NVIDIA.{0,160}?at a price of \$([\d.]+) "
        r"per share for an aggregate purchase price of \$([\d.]+) billion in cash", proxy,
    )
    for payer, event, shares, price, billions, key in (
        ("Jane Street Global Trading, LLC", "2026-04-15", js_shares, js_price, js_billions, "crwv_jane_8k"),
        ("NVIDIA", "2026-01-23", nv_shares, nv_price, nv_billions, "crwv_proxy"),
    ):
        gross = billions * 1000
        if (shares * price / 1_000_000).quantize(Decimal(1)) != gross:
            raise ValueError("Gross equity purchase price differs from shares times price")
        records.append({"payer": payer, "recipient": "CoreWeave", "type": "common_stock_purchase",
                        "event_date": event, "shares": int(shares), "price_usd_per_share": price,
                        "reported_gross_proceeds_usd_m": gross, "source": key,
                        "available_from_cited_source": registry[key]["available_at"]})
    warrants, proceeds = captures(
        r"On March 11, 2026 the Company entered into a securities purchase agreement with NVIDIA "
        r"to issue Pre-Funded Warrants to purchase ([\d,]+) Class A ordinary shares.{0,110}?"
        r"aggregate gross proceeds of \$([\d,]+\.\d)", words(docs["nbis_26_h1"]),
    )
    if proceeds != column(rows(docs["nbis_26_q1"]), "Proceeds from issuance of prefunded warrants", 1, 2, reported_nil=True):
        raise ValueError("Nebius: warrant proceeds differ from Q1 cash received")
    records.append({"payer": "NVIDIA", "recipient": "Nebius", "type": "pre_funded_warrant_purchase",
                    "event_date": "2026-03-11", "shares_underlying_warrants": int(warrants),
                    "reported_gross_proceeds_usd_m": proceeds, "sources": ["nbis_26_h1", "nbis_26_q1"],
                    "available_with_all_checks": max(registry[k]["available_at"] for k in ("nbis_26_h1", "nbis_26_q1"))})
    return records


def build(originals, fetch):
    registry = json.loads(REGISTRY.read_text())
    docs = source_documents(registry, KEYS, originals, fetch, reuse_verified=True)
    return {
        "as_of": CUTOFF.isoformat(), "units": "USD million unless specified", "source_registry": str(REGISTRY),
        "cash_bridges": [quarter_bridge(issuer, docs, registry) for issuer in ("CoreWeave", "Nebius")],
        "counterparty_disclosures": counterparty_disclosures(docs, registry),
        "node_score": None, "index_aics": None,
        "production_weights_changed": False, "verdict_mutated": False, "trades_created": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--originals", type=Path, required=True)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--out", type=Path, default=REPORT)
    args = parser.parse_args()
    args.out.write_text(json.dumps(build(args.originals, args.fetch), default=str, indent=2) + "\n")
