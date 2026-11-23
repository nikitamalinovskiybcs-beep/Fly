"""Calculate month-end volatility of 30-year constant maturity Treasury yield changes."""
import argparse
import hashlib
import json
from decimal import Decimal
from itertools import pairwise
from pathlib import Path
from statistics import stdev
from zipfile import ZipFile

from scripts.aics_compare_macro_vintages import (
    ARCHIVE_SHA,
    archived_rows,
    export_values,
    month_ends,
)
from scripts.aics_ust_release import fetch, treasury_year

RESEARCH = Path("aics_data/research")
EXPORTS = RESEARCH / "alfred_macro_export_reconciliation_2026-11-19.json"
RELEASES = RESEARCH / "ust_month_end_release_dates_2026-11-19.json"
REPORT = RESEARCH / "ust30_yield_change_volatility_2024_2026.json"
CHANGES = 20


def vintages(archive_path):
    if archive_path is not None:
        if hashlib.sha256(archive_path.read_bytes()).hexdigest() != ARCHIVE_SHA:
            raise ValueError("Original ALFRED archive digest differs")
        with ZipFile(archive_path) as archive:
            return archived_rows(archive, "DGS30")

    result = {}
    for item in json.loads(EXPORTS.read_text())["vintages"]:
        if item["series"] == "DGS30":
            raw = fetch(item["source"])
            cutoff = item["vintage"]
            if cutoff in result or hashlib.sha256(raw).hexdigest() != item["provider_sha256"]:
                raise ValueError(f"Duplicate or changed ALFRED export at {cutoff}")
            result[cutoff] = export_values("DGS30", cutoff, raw)
    return result


def build(archive_path, treasury_directory):
    history = vintages(archive_path)
    releases = {r["cutoff"]: r for r in json.loads(RELEASES.read_text())["records"]}
    expected = set(month_ends())
    if history.keys() != expected or releases.keys() != expected:
        raise ValueError("Missing or additional historical month end")

    treasury, source_years = {}, []
    for year in sorted({date[:4] for date in expected}):
        values, digest, url = treasury_year(year, treasury_directory)
        if not values or any(day[:4] != year for day in values):
            raise ValueError(f"Unexpected Treasury calendar for {year}")
        treasury.update(values)
        source_years.append({"year": year, "url": url, "retrieved_xml_sha256": digest})

    months = []
    distinct_days = set()
    matched_inputs = hashlib.sha256()
    for cutoff, values in sorted(history.items()):
        days = sorted(values)[-(CHANGES + 1):]
        release = releases[cutoff]
        if (len(days) != CHANGES + 1 or days[-1] != release["observation"]
                or values[days[-1]] != Decimal(release["percent"])
                or not days[-1] <= release["first_nonmissing_vintage"] <= cutoff):
            raise ValueError(f"Missing window or dated closing yield at {cutoff}")
        treasury_days = sorted(day for day in treasury if days[0] <= day <= days[-1])
        if days != treasury_days or any(values[d] != treasury[d] for d in days):
            raise ValueError(f"Treasury dates or yields differ within the ALFRED window at {cutoff}")
        distinct_days.update(days)
        for day in days:
            matched_inputs.update(f"{cutoff},{day},{values[day]:.2f}\n".encode("ascii"))
        changes = [(values[b] - values[a]) * 100 for a, b in pairwise(days)]
        months.append({"as_of": cutoff, "first_yield_date": days[0], "last_yield_date": days[-1],
                       "sample_sd_daily_change_bp": str(stdev(changes).quantize(Decimal("0.01")))})
    return {
        "research_as_of": "2026-11-18", "series": "DGS30",
        "method": "For each month-end vintage take its latest 21 reported yields. Express 20 changes in basis points and calculate their sample standard deviation (divisor 19), without annualizing.",
        "date_check": "Treasury reported dates and values matched throughout each window. Historical window selection used only that month's ALFRED vintage.",
        "alfred_archive_sha256": ARCHIVE_SHA, "alfred_public_exports": str(EXPORTS),
        "closing_release_evidence": str(RELEASES), "treasury_calendar_sources": source_years,
        "matched_date_value_pairs_across_windows": len(months) * (CHANGES + 1),
        "matched_inputs_sha256_cutoff_date_yield_csv": matched_inputs.hexdigest(),
        "unique_matched_dates": len(distinct_days), "months": months,
        "node_score": None, "index_aics": None, "untouched_oos": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Pinned archive. Omit to use the public ALFRED vintage exports.")
    parser.add_argument("--treasury-directory", type=Path, help="Directory of treasury_YYYY.xml. Omit to use Treasury.")
    parser.add_argument("--out", type=Path, default=REPORT)
    args = parser.parse_args()
    args.out.write_text(json.dumps(build(args.archive, args.treasury_directory), indent=2) + "\n")
