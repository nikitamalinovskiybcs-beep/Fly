"""Verify historical daily EDGAR index membership for AICS research filings."""
import hashlib
import json
import os
from datetime import date, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

# One accession can supply observations to several nodes.
FILINGS = [
    ("2026-08-26", "1045810", "10-Q", "0001045810-26-000075"),
    ("2026-09-18", "2110365", "S-1", "0001193125-26-395475"),
    ("2026-10-22", "1513845", "6-K", "0001104659-26-117978"),
    ("2026-10-27", "1287750", "10-Q", "0001628280-26-067383"),
    ("2026-10-28", "789019", "10-Q", "0001193125-26-436133"),
    ("2026-10-28", "1101239", "10-Q", "0001101239-26-000180"),
]


def main():
    destination = Path("sec-index-evidence")
    destination.mkdir(exist_ok=True)
    receipts = []
    for day in sorted({item[0] for item in FILINGS}):
        filed = date.fromisoformat(day)
        filename = "master." + filed.strftime("%Y%m%d") + ".idx"
        quarter = (filed.month - 1) // 3 + 1
        url = f"https://www.sec.gov/Archives/edgar/daily-index/{filed.year}/QTR{quarter}/{filename}"
        request = Request(url, headers={"User-Agent": os.environ["SEC_IDENTITY"]})
        with urlopen(request, timeout=60) as response:
            raw = response.read()
        (destination / filename).write_bytes(raw)
        rows = [line.split("|") for line in raw.decode("latin-1").splitlines()]
        for _, cik, form, accession in (item for item in FILINGS if item[0] == day):
            path = f"edgar/data/{cik}/{accession}.txt"
            matches = [row for row in rows if len(row) == 5 and row[0] == cik
                       and row[2:] == [form, day, path]]
            if len(matches) != 1:
                raise ValueError(f"{accession} matched {len(matches)} daily index records")
            receipts.append(dict(accession=accession, index_url=url, row=matches[0],
                                 sha256=hashlib.sha256(raw).hexdigest(),
                                 available_at=(filed + timedelta(days=14)).isoformat()))
    (destination / "matches.json").write_text(json.dumps(receipts, indent=2) + "\n")


if __name__ == "__main__":
    main()
