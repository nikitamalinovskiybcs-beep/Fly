"""Compare archived ALFRED month ends against a separately retrieved provider export."""
import calendar
import csv
import hashlib
import io
import json
import sys
import zipfile
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ARCHIVE_SHA = "03d06b287dc591d6830223bd181db401d19ce618a785b40c25a999ab1ddd5cc3"


def check(condition, message):
    if not condition:
        raise ValueError(message)


def month_ends():
    for index in range(24):
        year, month = divmod(2024 * 12 + 10 + index, 12)
        yield date(year, month + 1, calendar.monthrange(year, month + 1)[1]).isoformat()


def archived_rows(archive, series):
    result = defaultdict(dict)
    with archive.open(f"alfred_asof_{series}.csv") as raw:
        for row in csv.DictReader(io.TextIOWrapper(raw)):
            cutoff, day = row["as_of"], row["observation_date"]
            check(row["series_id"] == series and "2010-01-01" <= day <= cutoff, "wrong series/date")
            check(row["realtime_start"] == row["realtime_end"] == cutoff, "wrong vintage")
            check(day not in result[cutoff], "duplicate observation")
            result[cutoff][day] = Decimal(row["value"])
    check(set(result) == set(month_ends()), "incomplete vintage inventory")
    return result


def export_values(series, cutoff, raw):
    rows = csv.reader(io.StringIO(raw.decode("utf-8-sig")))
    header = next(rows)
    check(header[1:] == [series + "_" + cutoff.replace("-", "")], "provider vintage mismatch")
    actual = {}
    for day, value in rows:
        if value not in {"", "."} and "2010-01-01" <= day <= cutoff:
            check(day not in actual, "duplicate provider date")
            actual[day] = Decimal(value)
    return actual


def compare_export(series, cutoff, expected, raw):
    actual = export_values(series, cutoff, raw)
    check(actual == expected, f"{series} {cutoff} observations differ")
    return {"series": series, "vintage": cutoff, "observations": len(actual),
            "provider_sha256": hashlib.sha256(raw).hexdigest()}


def main():
    path, report = map(Path, sys.argv[1:])
    check(hashlib.sha256(path.read_bytes()).hexdigest() == ARCHIVE_SHA, "archive digest mismatch")
    receipts = []
    with zipfile.ZipFile(path) as archive:
        for series in ("DGS30", "SOFR"):
            for cutoff, expected in sorted(archived_rows(archive, series).items()):
                query = urlencode({"id": series, "vintage_date": cutoff, "cosd": "2010-01-01", "coed": cutoff})
                url = "https://alfred.stlouisfed.org/graph/alfredgraph.csv?" + query
                with urlopen(url, timeout=60) as response:
                    receipt = compare_export(series, cutoff, expected, response.read())
                receipts.append(dict(receipt, source=url))
                report.write_text(json.dumps(receipts, indent=2) + "\n")
                print(series, cutoff, receipt["observations"], flush=True)


if __name__ == "__main__":
    main()
