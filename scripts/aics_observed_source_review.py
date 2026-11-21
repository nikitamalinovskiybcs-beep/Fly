"""Reproduce issuer and Federal Reserve research observations from pinned originals."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

REGISTRY = Path("aics_data/source_registry/observed_review_2026-11-19.json")
REPORT = Path("aics_data/research/observed_source_review_2026-11-19.json")
FROZEN_DATE = dt.date(2026, 11, 18)
NS = {
    "ix": "http://www.xbrl.org/2013/inlineXBRL",
    "x": "http://www.xbrl.org/2003/instance",
}
FED_URL = "https://www.federalreserve.gov/releases/G17/20261117/g17_sup.txt"
MAX_BYTES = 70_000_000
SOURCES = {"msft", "pru", "orcl", "apld", "nscale", "nvda_split", "nvda_q1", "nvda_q2", "fed_3344"}


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def words(raw):
    parser = Text()
    parser.feed(raw.decode("utf-8-sig"))
    parser.close()
    return " ".join(" ".join(parser.parts).split())


def checked_original(raw, entry):
    if not 0 < len(raw) == entry["bytes"] <= MAX_BYTES or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError("Original bytes differ from receipt: " + entry["url"])
    return raw


def read_original(directory, key, entry, fetch):
    path = directory / (key + ".txt")
    if not fetch:
        return checked_original(path.read_bytes(), entry)
    agent = os.environ.get("AICS_SEC_USER_AGENT") or os.environ.get("EDGAR_IDENTITY")
    request = Request(entry["url"], headers={
        "User-Agent": agent or "AICS source research https://github.com/nikitamalinovskiybcs-beep/Fly"
    })
    with urlopen(request, timeout=45) as response:
        if response.geturl() != entry["url"]:
            raise ValueError("Source redirect differs from registry")
        raw = checked_original(response.read(MAX_BYTES + 1), entry)
    directory.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def filing_document(raw, item, filename):
    """Bind the selected <TEXT> bytes to the filing header and document identity."""
    header, *documents = raw.split(b"<DOCUMENT>")
    metadata = dict(line.split(":", 1) for line in header.decode("ascii", errors="replace").splitlines()
                    if ":" in line)
    expected = {"ACCESSION NUMBER": item["accession"], "CONFORMED SUBMISSION TYPE": item["form"],
                "FILED AS OF DATE": item["filed_at"].replace("-", "")}
    if any(metadata.get(field, "").strip() != value for field, value in expected.items()):
        raise ValueError("Unexpected SEC filing header")
    if not re.search(rb"(?m)^\s*CENTRAL INDEX KEY:\s*0*" + item["cik"].encode() + rb"\s*$", header):
        raise ValueError("SEC issuer CIK does not match the filing header")
    selected = []
    for document in documents:
        info, _, body = document.partition(b"<TEXT>")
        if b"<FILENAME>" + filename.encode() not in info.splitlines():
            continue
        if b"<TYPE>" + item["document_type"].encode() not in info.splitlines():
            raise ValueError("Unexpected SEC document type")
        payload, closing_tag, _ = body.partition(b"</TEXT>")
        if not closing_tag or hashlib.sha256(payload).hexdigest() != item["document_text_sha256"]:
            raise ValueError("SEC document text differs from its receipt")
        payload = payload.strip()
        if payload.startswith(b"<XBRL>") and payload.endswith(b"</XBRL>"):
            payload = payload[6:-7].strip()
        selected.append(payload)
    if len(selected) != 1:
        raise ValueError("Expected exactly one document with this filename")
    return selected[0]


def source_documents(registry, directory, fetch):
    cutoff = dt.date.fromisoformat(registry["evidence_cutoff"])
    if cutoff != FROZEN_DATE:
        raise ValueError("The source review has a fixed information cutoff")
    if set(registry["sources"]) != SOURCES:
        raise ValueError("Source inventory differs from the reviewed documents")
    docs = {}
    for key, item in registry["sources"].items():
        original = item["original"]
        if key == "fed_3344":
            if original["url"] != FED_URL or item["release_date"] != "2026-11-17":
                raise ValueError("Unexpected G.17 release")
            docs[key] = read_original(directory, key, original, fetch)
            continue
        filed = dt.date.fromisoformat(item["filed_at"])
        available = dt.date.fromisoformat(item["available_at"])
        if filed + dt.timedelta(days=14) != available or available > cutoff:
            raise ValueError("SEC filing violates the dated availability rule")
        accession, cik = item["accession"], item["cik"]
        if not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession) or not cik.isdigit():
            raise ValueError("Invalid filing identity")
        base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/"
        filename = item["source_page"].removeprefix(base)
        if not re.fullmatch(r"[\w-]+\.htm", filename) or original["url"] != base + accession + ".txt":
            raise ValueError("Document or full submission outside its accession")
        raw = read_original(directory, key, original, fetch)
        docs[key] = filing_document(raw, item, filename)
    return docs

def dollars(root, tag, cik, period):
    """Select one consolidated USD fact in the stated legal entity and period."""
    contexts = set()
    for context in root.findall(".//x:context", NS):
        identifier = context.findtext("x:entity/x:identifier", namespaces=NS)
        dates = context.find("x:period", NS)
        if (identifier and identifier.lstrip("0") == cik and dates is not None
                and tuple(element.text for element in dates) == period
                and context.find("x:entity/x:segment", NS) is None
                and context.find("x:scenario", NS) is None):
            contexts.add(context.get("id"))
    units = {unit.get("id") for unit in root.findall(".//x:unit", NS)
             if [m.text for m in unit.findall("x:measure", NS)] == ["iso4217:USD"]
             and len(unit) == 1}
    values = set()
    for fact in root.findall(".//ix:nonFraction", NS):
        if fact.get("name") != tag or fact.get("contextRef") not in contexts or fact.get("unitRef") not in units:
            continue
        value = Decimal("".join(fact.itertext()).replace(",", "").strip())
        sign = -1 if fact.get("sign") == "-" else 1
        values.add(sign * value.scaleb(int(fact.get("scale", "0"))))
    if len(values) != 1:
        raise ValueError(f"Missing or conflicting {cik} {tag} USD fact for {period}")
    return values.pop()


def captures(pattern, text):
    """Duplicate narrative disclosures are usable only when their values agree."""
    matches = {m.groups() for m in re.finditer(pattern, text, flags=re.IGNORECASE)}
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous original disclosure: " + pattern[:75])
    return tuple(Decimal(v.replace(",", "")) for v in matches.pop())


def percent(value, base):
    return str((100 * value / base).quantize(Decimal("0.01")))


def review(docs):
    # These two observations have the same three-month duration in successive years.
    msft = ET.fromstring(docs["msft"])
    capex = "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment"
    prior = dollars(msft, capex, "789019", ("2025-07-01", "2025-09-30"))
    current = dollars(msft, capex, "789019", ("2026-07-01", "2026-09-30"))
    pru = ET.fromstring(docs["pru"])
    loans = dollars(pru, "pru:Commercialmortgageandotherloans", "1137774", ("2026-09-30",))
    assets = dollars(pru, "us-gaap:Assets", "1137774", ("2026-09-30",))
    demand, demand_prior = captures(
        r"remaining performance obligations were \$([\d,]+) billion and \$([\d,]+) billion "
        r"as of August 31, 2026 and 2025, respectively", words(docs["orcl"])
    )
    current_rpo = dollars(ET.fromstring(docs["orcl"]), "us-gaap:RevenueRemainingPerformanceObligation",
                          "1341439", ("2026-08-31",))
    if demand * 10**9 != current_rpo:
        raise ValueError("Oracle narrative and inline RPO differ")

    contract = words(docs["nscale"])
    parties = ("NSCALE NC BORROWER SPV, LLC, as the Borrower", "NSCALE SERVICES US INC., as the Affiliate Guarantor")
    if not all(party.casefold() in contract.casefold() for party in parties) or not (
        "limited purpose entity" in contract and "Section 5.14. Separateness" in contract
    ):
        raise ValueError("Executed Nscale instrument lacks expected parties or covenants")
    def commitment(kind):
        return captures("aggregate principal amount of the " + kind
                        + r"Commitments on the Closing Date is \$([\d,]+)", contract)[0]
    fixed = commitment("Fixed Rate Delayed Draw Loan ")
    floating = commitment("Floating Rate Delayed Draw Loan ")
    if fixed + floating != commitment(""):
        raise ValueError("Contract component commitments do not reconcile")

    power = words(docs["apld"])
    first, second = captures(
        r"first HPC data center at our Polaris Forge 1 campus.{0,100}?with (\d+) MW of capacity\."
        r".{0,200}?second HPC data center at our Polaris Forge 1 campus, which reached its full "
        r"(\d+)\s*MW of capacity as of the date of filing", power
    )
    fed = docs["fed_3344"].decode("ascii")
    _, title, rest = fed.partition("Capacity Utilization: Manufacturing, Mining, and Utilities")
    table, next_table, _ = rest.partition(" Table 3")
    if not title or not next_table or "Percent of capacity, seasonally adjusted" not in table:
        raise ValueError("G.17 supplemental table 2 missing")
    if "November 17, 2026" not in fed or not re.search(r"Sept\.\[r\]\s+Oct\.\[p\]", table):
        raise ValueError("Unexpected months or vintage in the G.17 utilization table")
    industry = [line for line in table.splitlines() if re.search(r"electronic components\s*\|\s*3344\s*\|", line)]
    if len(industry) != 1:
        raise ValueError("Missing or ambiguous NAICS 3344 capacity utilization series")
    sept, oct_ = map(Decimal, industry[0].split("|")[-1].split()[-2:])

    split = words(docs["nvda_split"])
    if not all(token in split for token in ("ten-for-one forward stock split", "4:01 p.m. Eastern Time on June 7, 2024",
                                            "split-adjusted basis at market open on June 10, 2024")):
        raise ValueError("NVIDIA split or its effective date changed")
    quarter = words(docs["nvda_q2"])
    shell, sb, maximum = captures(
        r"SB Energy Corp\. guarantees signed in August 2026 \(in billions\): Land, power, and shell "
        r"guarantees for AI clouds \$ ([\d.]+) SB Energy Corp\. guarantees ([\d.]+) Total \$ ([\d.]+)", quarter
    )
    if maximum != shell + sb:
        raise ValueError("Guarantee components differ from the disclosed gross maximum")
    ar = "us-gaap:AccountsReceivableNetCurrent"
    ar_q1 = dollars(ET.fromstring(docs["nvda_q1"]), ar, "1045810", ("2026-04-26",))
    ar_q2 = dollars(ET.fromstring(docs["nvda_q2"]), ar, "1045810", ("2026-07-26",))

    return {
        "pru_commercial_mortgage_and_other_loans": {
            "sources": ["pru"], "period_end": "2026-09-30", "net_loans_usd": int(loans),
            "total_gaap_assets_usd": int(assets), "share_of_assets_pct": percent(loans, assets),
            "ai_attribution": None},
        "nvidia_split": {"sources": ["nvda_split"], "ratio_new_for_old": [10, 1],
                         "effective_date": "2024-06-07", "first_expected_split_basis_session": "2024-06-10",
                         "prices_adjusted_in_review": False, "basket_membership_in_2024_verified": False},
        "microsoft_cash_capex": {"sources": ["msft"], "quarter_ends": ["2025-09-30", "2026-09-30"],
                                 "prior_usd": int(prior), "current_usd": int(current),
                                 "change_usd": int(current - prior), "change_yoy_pct": percent(current - prior, prior),
                                 "ai_attribution": None},
        "nscale_nc_gpu_credit": {"sources": ["nscale"], "borrower": "Nscale NC Borrower SPV, LLC",
                                  "affiliate_guarantor": "Nscale Services US Inc.",
                                  "fixed_commitment_usd": int(fixed), "floating_commitment_usd": int(floating),
                                  "contractual_ceiling_usd": int(fixed + floating),
                                  "drawn_principal_from_this_agreement_usd": None,
                                  "effective_economic_recourse_amount_usd": None},
        "applied_digital_polaris_forge_1": {"sources": ["apld"], "status_date": "2026-10-07",
                                             "building_1_capacity_mw": int(first), "building_2_capacity_mw": int(second),
                                             "two_operating_buildings_capacity_mw": int(first + second),
                                             "electricity_consumed_mwh": None},
        "fed_naics_3344_utilization": {"sources": ["fed_3344"], "release_date": "2026-11-17",
                                       "september_revised_pct": str(sept), "october_preliminary_pct": str(oct_),
                                       "change_within_release_pp": str(oct_ - sept)},
        "oracle_company_wide_rpo": {"sources": ["orcl"], "period_ends": ["2025-08-31", "2026-08-31"],
                                    "prior_usd_bn": int(demand_prior), "current_usd_bn": int(demand),
                                    "change_usd_bn": int(demand - demand_prior),
                                    "change_yoy_pct": percent(demand - demand_prior, demand_prior),
                                    "ai_specific_paid_revenue_usd": None},
        "nvidia_guarantees": {"sources": ["nvda_q2"], "sb_energy_signed_month": "2026-08",
                              "land_power_shell_max_usd_bn": str(shell), "sb_energy_max_usd_bn": str(sb),
                              "total_max_gross_usd_bn": str(maximum), "drawn_or_paid_usd_bn": None},
        "nvidia_net_receivables": {"sources": ["nvda_q1", "nvda_q2"], "period_ends": ["2026-04-26", "2026-07-26"],
                                    "prior_usd": int(ar_q1), "current_usd": int(ar_q2),
                                    "change_usd": int(ar_q2 - ar_q1), "change_qoq_pct": percent(ar_q2 - ar_q1, ar_q1)}
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--originals", type=Path, required=True)
    parser.add_argument("--fetch", action="store_true", help="Download and rehash the eight complete filings and the dated G.17 release")
    parser.add_argument("--out", type=Path, default=REPORT)
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text())
    documents = source_documents(registry, args.originals, args.fetch)
    result = {
        "review_date": registry["review_date"], "source_cutoff": registry["evidence_cutoff"],
        "registry_sha256": hashlib.sha256(REGISTRY.read_bytes()).hexdigest(),
        "observations": review(documents), "independently_attested_historical_pit": False,
        "certified_node_scores": 0, "index_aics": None, "promotion": "BLOCKED",
        "production_weights_changed": False, "verdict_mutated": False, "trades_created": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{len(documents)} dated primary documents, {len(result['observations'])} research findings")


if __name__ == "__main__":
    main()
