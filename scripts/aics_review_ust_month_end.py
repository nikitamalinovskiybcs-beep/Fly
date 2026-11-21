"""Replay the Treasury month-end review from committed evidence (Python stdlib)."""
import calendar
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "aics_data/research"


def read_rows(filename, key, date_field):
    rows = json.loads((ROOT / filename).read_text(encoding="utf-8"))[key]
    indexed = {row[date_field]: row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError(f"duplicate cutoff in {filename}")
    return indexed


def main():
    treasury = read_rows("ust_month_end_release_dates_2026-11-19.json", "records", "cutoff")
    sofr = read_rows("ust_spread_sofr_release_review_2026-11-19.json", "records", "cutoff")
    panel = read_rows("ust30_24_month_public_observed_panel_2026-11-18.json",
                      "public_series_observations", "as_of_month_end")
    expected = set()
    for i in range(24):
        year, month = divmod(2024 * 12 + 10 + i, 12)
        month += 1
        expected.add(date(year, month, calendar.monthrange(year, month)[1]).isoformat())
    if not (expected == treasury.keys() == sofr.keys() == panel.keys()):
        raise ValueError("month-end coverage differs")
    for cutoff in sorted(expected):
        point = panel[cutoff]
        for source, label in [(treasury, "dgs30"), (sofr, "sofr")]:
            row = source[cutoff]
            observed = date.fromisoformat(row["observation"])
            available = date.fromisoformat(row["first_nonmissing_vintage"])
            if not observed <= available <= date.fromisoformat(cutoff):
                raise ValueError(f"{label} availability violation at {cutoff}")
            if (point[label + "_observation_date"] != row["observation"]
                    or Decimal(point[label + "_pct"]) != Decimal(row["percent"])):
                raise ValueError(f"{label} input mismatch at {cutoff}")
        spread = 100 * (Decimal(treasury[cutoff]["percent"]) - Decimal(sofr[cutoff]["percent"]))
        if spread != Decimal(point["dgs30_minus_sofr_bps"]) or spread != Decimal(str(sofr[cutoff]["verified_spread_bp"])):
            raise ValueError(f"spread mismatch at {cutoff}")
    print("24 month ends, 48 dated inputs and 24 spreads reconciled. Independent decision pending.")


if __name__ == "__main__":
    main()
