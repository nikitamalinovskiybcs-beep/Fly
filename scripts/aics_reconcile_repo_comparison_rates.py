"""Reconcile repo comparison rates at the previously verified SOFR observation dates."""
import hashlib
import json
import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from zipfile import ZipFile


def main():
    root = Path("aics_data/research")
    archive = Path(sys.argv[1])
    receipt = json.loads((root / "nyfed_repo_original_archive_independent_rehash_2026_11_18.json").read_text())
    panel = json.loads((root / "ust_spread_sofr_release_review_2026-11-19.json").read_text())["records"]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != receipt["source_archive_zip_sha256"]:
        raise ValueError("NY Fed archive mismatch")
    if len(panel) != 24 or len({r["cutoff"] for r in panel}) != 24:
        raise ValueError("incomplete monthly SOFR anchors")
    results = []
    with ZipFile(archive) as z:
        for source in receipt["archive_files"]:
            series = source["rate_type"]
            if series not in ("BGCR", "TGCR"):
                continue
            raw = z.read(source["source_file"])
            if hashlib.sha256(raw).hexdigest() != source["raw_sha256"]:
                raise ValueError("source digest mismatch")
            values = {r["effectiveDate"]: Decimal(str(r["percentRate"]))
                      for r in json.loads(raw)["refRates"] if r["type"] == series}
            title = {"TGCR": "Tri-Party General Collateral Rate", "BGCR": "Broad General Collateral Rate"}[series]
            search = "https://api.stlouisfed.org/fred/series/search?" + urlencode(dict(
                search_text=title, file_type="json", api_key=os.environ["FRED_API_KEY"]))
            with urlopen(search, timeout=60) as response:
                catalog = json.load(response)["seriess"]
            ids = [r["id"] for r in catalog if r["title"].casefold() == title.casefold()
                   and r["frequency_short"] == "D" and r["units"] == "Percent"]
            if len(ids) > 1:
                raise ValueError("ambiguous FRED series match")
            if ids:
                vintage_url = "https://api.stlouisfed.org/fred/series/vintagedates?"
                vintage_params = dict(series_id=ids[0], sort_order="asc", limit=1,
                                      realtime_start="1776-07-04", file_type="json")
                with urlopen(vintage_url + urlencode(dict(vintage_params, api_key=os.environ["FRED_API_KEY"])), timeout=60) as response:
                    first_catalog_vintage = json.load(response)["vintage_dates"][0]
            for anchor in panel:
                day, cutoff = anchor["observation"], anchor["cutoff"]
                if not ids:
                    results.append(dict(series=series, cutoff=cutoff, observation=day,
                                        status="no_exact_FRED_catalog_match", first_vintage=None))
                    continue
                if cutoff < first_catalog_vintage:
                    results.append(dict(series=series, cutoff=cutoff, observation=day, first_vintage=None,
                                        status="before_first_catalog_vintage", catalog_start=first_catalog_vintage,
                                        query=vintage_url + urlencode(vintage_params)))
                    continue
                params = dict(series_id=ids[0], observation_start=day, observation_end=day,
                              realtime_start=(date.fromisoformat(day)-timedelta(days=1)).isoformat(),
                              realtime_end=cutoff, file_type="json")
                base = "https://api.stlouisfed.org/fred/series/observations?"
                with urlopen(base + urlencode(dict(params, api_key=os.environ["FRED_API_KEY"])), timeout=60) as response:
                    body = response.read()
                versions = sorted((r for r in json.loads(body)["observations"] if r["value"] != "."),
                                  key=lambda r: r["realtime_start"])
                if not versions:
                    results.append(dict(series=series, cutoff=cutoff, observation=day, first_vintage=None,
                                        status="no_value_in_requested_vintage", query=base + urlencode(params),
                                        sha256=hashlib.sha256(body).hexdigest()))
                    continue
                if not all(r["date"] == day for r in versions):
                    raise ValueError(f"missing {series} observation for {day}")
                latest = versions[-1]
                rate = Decimal(latest["value"])
                if not day <= versions[0]["realtime_start"] <= latest["realtime_start"] <= cutoff <= latest["realtime_end"] or rate != values[day]:
                    raise ValueError(f"release or rate mismatch at {cutoff} for {series}")
                results.append(dict(series=series, cutoff=cutoff, observation=day,
                                    status="matched", first_vintage=versions[0]["realtime_start"], rate_percent=str(rate),
                                    sofr_minus_rate_bp=str(100*(Decimal(anchor["percent"])-rate)),
                                    query=base + urlencode(params), sha256=hashlib.sha256(body).hexdigest()))
    if len({(r["series"], r["cutoff"]) for r in results}) != 48:
        raise ValueError("incomplete repo coverage")
    Path("repo_monthly.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
