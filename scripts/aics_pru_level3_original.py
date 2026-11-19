#!/usr/bin/env python3
"""Replay Prudential 2026 Q3 Level 3 fixed maturities from its original SEC 10-Q.

Frozen research as-of November 19, 2026. Original SEC bytes are previously
independently SHA-256 pinned. This is NOT historical delivery-time PIT
attestation, NAIC/AI exposure, model scoring, or a private-credit loss.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_insurers_pru_credit_asof import safe_dates
from scripts.aics_observed_source_review import (
    checked_original, filing_document, read_original,
)

AS_OF = dt.date(2026, 11, 19)
SOURCE_DIR = Path("aics_data/source_evidence/insurers_pru_credit_original")
OUTPUT = SOURCE_DIR / "pru_level3_original_replay.json"
TABLE = re.compile(rb"<table\b[^>]*>.*?</table\s*>", re.I | re.S)
ROW = re.compile(rb"<tr\b[^>]*>.*?</tr\s*>", re.I | re.S)
STRIP = re.compile(rb"<[^>]+>")
SCOPE = b"PFI excluding Closed Block Division and Funds Withheld"


def plaintext(raw: bytes) -> str:
    return re.sub(r"\s+", " ", html.unescape(STRIP.sub(b" ", raw).decode(
        "utf-8", errors="replace"))).strip()


def percentage(n: int, d: int) -> str:
    if d <= 0:
        raise ValueError("Nonpositive original SEC denominator")
    return str((Decimal(n) * 100 / Decimal(d)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP))


def read_scope_table(primary: bytes, day: str) -> dict[str, dict[str, int]]:
    matches = [table for table in TABLE.findall(primary)
               if SCOPE in table and day.encode() in table
               and b"Fixed maturities, available-for-sale" in table
               and b"Fixed maturities, trading" in table
               and b"Total assets" in table]
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous dated PFI Level 3 SEC table")
    table_text = plaintext(matches[0])
    if ("Total Level 3" not in table_text and "Total Level 3(1)" not in table_text):
        raise ValueError("Missing Level 3 original table column heading")
    found: dict[str, dict[str, int]] = {}
    for row in ROW.findall(matches[0]):
        cleaned = plaintext(row)
        for label, key in (("Fixed maturities, available-for-sale", "afs"),
                           ("Fixed maturities, trading", "trading"),
                           ("Total assets", "total_assets")):
            if not cleaned.startswith(label + " "):
                continue
            if key in found:
                raise ValueError("Duplicate Level 3 fair-value line")
            # First pair belongs to PFI excluding Closed Block and Funds
            # Withheld; remaining four columns are different populations.
            after = cleaned[len(label):].strip()
            pairs = re.findall(r"-?\d[\d,]*|\(\s*\d[\d,]*\s*\)", after)
            if len(pairs) != 6:
                raise ValueError("SEC hierarchy row columns are incomplete")
            values = [int(s.replace(",", "")) for s in pairs]
            if min(values) < 0 or values[1] > values[0]:
                raise ValueError("Implausible fair-value hierarchy amounts")
            found[key] = {"fair_value": values[0], "level3": values[1]}
    if set(found) != {"afs", "trading", "total_assets"}:
        raise ValueError("Missing securities or total assets row")
    return found


def build_from_primary(primary: bytes, as_of: dt.date = AS_OF) -> dict:
    if as_of != AS_OF:
        raise ValueError("Only frozen November 19, 2026 research is permitted")
    narrative = plaintext(primary)
    pattern = (r"Level 3 fixed maturity securities for PFI excluding the Closed Block "
               r"division and Funds Withheld included approximately \$([\d,]+) "
               r"million of public fixed maturities as of September 30, 2026"
               r".{0,200}?approximately \$([\d,]+) million of private fixed maturities")
    entries = re.findall(pattern, narrative, flags=re.I)
    if len(entries) != 1:
        raise ValueError("Missing/ambiguous Prudential Level 3 private and public statement")
    public, private = (int(x.replace(",", "")) for x in entries[0])
    sept = read_scope_table(primary, "As of September 30, 2026")
    dec = read_scope_table(primary, "As of December 31, 2025")
    sep_afs, sep_trading = sept["afs"]["level3"], sept["trading"]["level3"]
    dec_afs, dec_trading = dec["afs"]["level3"], dec["trading"]["level3"]
    sep_total, dec_total = sep_afs + sep_trading, dec_afs + dec_trading
    if (public, private, sep_afs, sep_trading, dec_afs, dec_trading,
        sept["total_assets"]["level3"], dec["total_assets"]["level3"]) != (
        1154, 12510, 13135, 529, 10802, 480, 18131, 15488):
        raise ValueError("Real SEC Level 3 original values changed")
    if public + private != sep_total or sep_total != 13664 or dec_total != 11282:
        raise ValueError("SEC private/public does not reconcile to AFS/trading")
    if sept["total_assets"]["fair_value"] != 500781 or dec["total_assets"]["fair_value"] != 507023:
        raise ValueError("SEC fair value total asset population changed")
    return {
        "schema_version": "aics-pru-level3-sec-original-replay-v1",
        "node": "Insurers", "issuer": "Prudential Financial, Inc.",
        "frozen_as_of": as_of.isoformat(),
        "scope": "PFI excluding Closed Block Division and Funds Withheld",
        "unit": "USD millions", "september_2026": {
            "private_fixed_maturities_level3": private,
            "public_fixed_maturities_level3": public,
            "afs_fixed_maturities_level3": sep_afs,
            "trading_fixed_maturities_level3": sep_trading,
            "fixed_maturities_level3_total": sep_total,
            "private_share_of_level3_fixed_maturities_pct": percentage(private,sep_total),
            "recurring_fair_value_assets_level3": sept["total_assets"]["level3"],
            "recurring_fair_value_assets_total": sept["total_assets"]["fair_value"],
            "level3_share_of_total_fair_value_assets_pct": percentage(
                sept["total_assets"]["level3"],sept["total_assets"]["fair_value"]),
        }, "december_2025_comparative_in_november_2026_filing": {
            "afs_fixed_maturities_level3": dec_afs,
            "trading_fixed_maturities_level3": dec_trading,
            "fixed_maturities_level3_total": dec_total,
            "recurring_fair_value_assets_level3": dec["total_assets"]["level3"],
            "recurring_fair_value_assets_total": dec["total_assets"]["fair_value"],
            "level3_share_of_total_fair_value_assets_pct": percentage(
                dec["total_assets"]["level3"],dec["total_assets"]["fair_value"]),
        }, "observed_change_dec_to_sept": {
            "level3_fixed_maturities_millions": sep_total-dec_total,
            "level3_fixed_maturities_pct": percentage(sep_total-dec_total,dec_total),
            "recurring_fair_value_assets_level3_millions":
                sept["total_assets"]["level3"]-dec["total_assets"]["level3"],
        },
        "source_statement_and_distinct_table_totals_agree": True,
        "december_2025_comparative_is_not_2025_historical_pit": True,
        "private_credit_ai_specific_exposure": None,
        "independent_historical_provider_delivery_attested": False,
        "untouched_24m_oos": False, "insurers_stress_score": None,
        "index_aics": None, "promotion": "BLOCKED", "trades_created": False,
    }


def replay(directory: Path, as_of: dt.date = AS_OF) -> dict:
    source, met = safe_dates(as_of)
    if met["available_at"] != "2026-11-20" or met["eligible_at_frozen_cutoff"]:
        raise ValueError("MET Q3 SEC embargo must remain in force")
    original = read_original(directory, "pru", source["original"], fetch=False)
    checked_original(original, source["original"])
    primary = filing_document(original, source, "pru-20260930.htm")
    output = build_from_primary(primary, as_of)
    output.update({
        "sec_original_sha256": source["original"]["sha256"],
        "sec_original_bytes": source["original"]["bytes"],
        "embedded_primary_sha256": source["document_text_sha256"],
        "sec_filed_at": source["filed_at"],
        "sec_eligible_at": source["available_at"],
        "original_url": source["original"]["url"],
        "met_q3_embargo_until": met["available_at"],
    })
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pru-directory", type=Path, default=SOURCE_DIR)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    parser.add_argument("--as-of", type=dt.date.fromisoformat, default=AS_OF)
    args = parser.parse_args()
    try:
        result = replay(args.pru_directory, args.as_of)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"promotion":"BLOCKED","reason":type(exc).__name__,"detail":str(exc)[:220]}))
        return 2
    print(json.dumps({
        "private_level3_usd_millions": result["september_2026"]["private_fixed_maturities_level3"],
        "level3_fixed_maturities_usd_millions": result["september_2026"]["fixed_maturities_level3_total"],
        "change_from_comparative_usd_millions": result["observed_change_dec_to_sept"]["level3_fixed_maturities_millions"],
        "index_aics":None,"promotion":"BLOCKED"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
