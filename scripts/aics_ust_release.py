"""Reconcile month-end DGS30 values with provider first availability and Treasury."""
import hashlib
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from zipfile import ZipFile

from aics_compare_macro_vintages import ARCHIVE_SHA, archived_rows


def fetch(url):
    with urlopen(url, timeout=60) as response:
        return response.read()


def treasury_year(year):
    url = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?" + urlencode(
        {"data": "daily_treasury_yield_curve", "field_tdr_date_value": year})
    raw = fetch(url)
    values = {}
    for row in ET.fromstring(raw).findall(".//{*}properties"):
        day = row.findtext("{*}NEW_DATE")[:10]
        value = row.findtext("{*}BC_30YEAR")
        if value:
            if day in values:
                raise ValueError("duplicate Treasury day")
            values[day] = Decimal(value)
    return values, hashlib.sha256(raw).hexdigest(), url


def sofr_year(year):
    url = "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json?" + urlencode(
        {"startDate": year + "-01-01", "endDate": year + "-12-31", "type": "rate"})
    raw = fetch(url)
    values = {}
    for row in json.loads(raw)["refRates"]:
        day = row["effectiveDate"]
        if row["type"] != "SOFR" or day in values:
            raise ValueError("unexpected NY Fed series or duplicate date")
        values[day] = Decimal(str(row["percentRate"]))
    return values, hashlib.sha256(raw).hexdigest(), url


def main():
    series = sys.argv[2] if len(sys.argv) > 2 else "DGS30"
    loaders = {"SOFR": sofr_year, "DGS30": treasury_year}
    path = Path(sys.argv[1])
    if hashlib.sha256(path.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise ValueError("archive digest mismatch")
    with ZipFile(path) as archive:
        history = archived_rows(archive, series)
    cached = {}
    receipts = []
    for cutoff, observations in sorted(history.items()):
        day = max(observations)
        year = day[:4]
        if year not in cached:
            cached[year] = loaders[series](year)
        values, publisher_sha, publisher_url = cached[year]
        params = dict(series_id=series, observation_start=day, observation_end=day,
                      realtime_start=(date.fromisoformat(day)-timedelta(days=1)).isoformat(),
                      realtime_end=cutoff, file_type="json")
        url = "https://api.stlouisfed.org/fred/series/observations?"
        raw = fetch(url + urlencode(dict(params, api_key=os.environ["FRED_API_KEY"])))
        versions = [row for row in json.loads(raw)["observations"] if row["value"] != "."]
        versions.sort(key=lambda row: row["realtime_start"])
        if not versions or versions[-1]["date"] != day or not (day <= versions[0]["realtime_start"] <= cutoff <= versions[-1]["realtime_end"]):
            raise ValueError(f"missing release interval at {cutoff}")
        if Decimal(versions[-1]["value"]) != observations[day] or values.get(day) != observations[day]:
            raise ValueError(f"value disagreement at {cutoff}")
        receipts.append(dict(cutoff=cutoff, observation=day, percent=str(observations[day]),
                             first_nonmissing_vintage=versions[0]["realtime_start"],
                             alfred_query=url + urlencode(params), alfred_sha256=hashlib.sha256(raw).hexdigest(),
                             publisher_source=publisher_url, publisher_sha256=publisher_sha))
        Path("ust_release_dates.json" if series == "DGS30" else "sofr_release_dates.json").write_text(json.dumps(receipts, indent=2) + "\n")
        print(cutoff, day, versions[0]["realtime_start"], flush=True)


if __name__ == "__main__":
    main()
