#!/usr/bin/env python3
"""Prospective Nasdaq Trader listing snapshots; never historical index membership.

Two official exchange directories include a *file creation wall time*, not a
historical point-in-time basket membership or an independently attested
publication instant. Keep original bytes/SHA and never compute AICS scores.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

from scripts.aics_collect_ai_equities_prices import RESEARCH_SYMBOLS

BASE = "https://www.nasdaqtrader.com/dynamic/symdir/"
FILENAMES = ("nasdaqlisted.txt", "otherlisted.txt")
SCHEMA = "aics-ai-equities-prospective-listing-directory-v1"
MAX_BYTES = 8_000_000
FOOTER = re.compile(r"^File Creation Time:\s*(\d{8})(\d{2}:\d{2})$")
HEADERS = {
    "nasdaqlisted.txt": ("Symbol", "Security Name", "Test Issue", "ETF"),
    "otherlisted.txt": ("ACT Symbol", "Security Name", "Exchange", "Test Issue", "ETF"),
}


def parse_directory(raw: bytes, filename: str) -> dict:
    if filename not in FILENAMES or not raw or len(raw) > MAX_BYTES:
        raise ValueError("Unsupported, empty or oversized official directory")
    try:
        source = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Directory charset cannot be independently parsed") from exc
    lines = [line.rstrip("\r") for line in source.splitlines() if line.strip()]
    if len(lines) < 3:
        raise ValueError("Directory lacks header, listings or creation footer")
    header = lines[0].split("|")
    if len(set(header)) != len(header) or any(col not in header for col in HEADERS[filename]):
        raise ValueError("Official directory fields absent or duplicated")
    footer = lines[-1].split("|", 1)[0].strip()
    match = FOOTER.fullmatch(footer)
    if match is None:
        raise ValueError("Official file creation wall-clock marker missing")
    try:
        generated = dt.datetime.strptime("".join(match.groups()), "%m%d%Y%H:%M")
    except ValueError as exc:
        raise ValueError("Invalid official directory creation timestamp") from exc
    listings: dict[str, dict] = {}
    symbol_key = "Symbol" if filename == "nasdaqlisted.txt" else "ACT Symbol"
    reader = csv.DictReader(io.StringIO("\n".join(lines[:-1])+"\n"), delimiter="|")
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Malformed symbol directory row")
        symbol = row.get(symbol_key, "")
        if not symbol or symbol in listings:
            raise ValueError("Blank or duplicate symbol in original directory")
        if row["Test Issue"] not in ("Y", "N") or row["ETF"] not in ("Y", "N"):
            raise ValueError("Untrusted symbol classification field")
        listings[symbol] = row
    if len(listings) < 100:
        raise ValueError("Official directory unusually short; refuse truncated source")
    return {"filename":filename, "file_creation_wallclock_unverified_timezone":generated.isoformat(),
            "directory_rows":len(listings), "listings":listings}


def fetch_directory(url: str, opener=urlopen) -> bytes:
    if url not in (BASE + filename for filename in FILENAMES):
        raise ValueError("Unapproved Nasdaq Trader source URL")
    req = Request(url, headers={"User-Agent":"AICS-Research/1.0 (primary-source audit)",
                                "Accept":"text/plain"})
    with opener(req, timeout=30) as response:
        if response.geturl() != url:
            raise ValueError("Unexpected source redirect")
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("Oversized Nasdaq Trader response")
    return body


def build_manifest(root: Path, *, clock, fetcher=fetch_directory) -> dict:
    stamp = clock()
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Capture clock must be offset-aware")
    started = stamp.astimezone(dt.timezone.utc)
    raw_root = root / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)
    rows = []
    decoded = {}
    for filename in FILENAMES:
        original = fetcher(BASE + filename)
        parsed = parse_directory(original, filename)
        generated_date = dt.date.fromisoformat(
            parsed["file_creation_wallclock_unverified_timezone"][:10])
        # Wall time has unspecified venue timezone; allow 2-day UTC buffer.
        if abs((started.date() - generated_date).days) > 2:
            raise ValueError("Stale or future exchange directory")
        sha = hashlib.sha256(original).hexdigest()
        original_path = raw_root / (filename.removesuffix(".txt") + "_" + sha + ".txt")
        if original_path.exists() and original_path.read_bytes() != original:
            raise ValueError("Raw exchange directory collision or tampering")
        if not original_path.exists():
            original_path.write_bytes(original)
        rows.append({
            "filename":filename, "url":BASE+filename,
            "sha256":sha, "bytes":len(original),
            "original_path":str(original_path),
            "directory_rows":parsed["directory_rows"],
            "file_creation_wallclock_unverified_timezone":
                parsed["file_creation_wallclock_unverified_timezone"],
        })
        decoded[filename] = parsed["listings"]
    seen = set()
    observed = []
    for symbol in RESEARCH_SYMBOLS:
        found = [(filename, decoded[filename][symbol])
                 for filename in FILENAMES if symbol in decoded[filename]]
        if len(found) != 1:
            raise ValueError("Research symbol missing or in both exchange directories: "+symbol)
        filename, row = found[0]
        if row["Test Issue"] != "N" or row["ETF"] != "N":
            raise ValueError("Research issuer is flagged test issue or ETF: "+symbol)
        venue = row.get("Exchange", "NASDAQ")
        if not row.get("Security Name"):
            raise ValueError("Missing official issuer security name")
        observed.append({
            "symbol":symbol, "directory":filename, "market_code":venue,
            "security_name":row["Security Name"],
            "test_issue":row["Test Issue"], "etf":row["ETF"],
            "listing_snapshot_only":True,
            "historical_membership_attested":False,
            "stock_split_dividend_attested":False,
        })
        seen.add(symbol)
    if seen != set(RESEARCH_SYMBOLS):
        raise ValueError("Incomplete seven-security listing observation")
    return {
        "schema_version":SCHEMA,
        "node":"AI Equities",
        "research_symbols":list(RESEARCH_SYMBOLS),
        "captured_at_utc":started.isoformat(),
        "scope":"PROSPECTIVE_CURRENT_DIRECTORY_NOT_HISTORICAL_MEMBERSHIP",
        "original_files":rows,
        "observed_securities":observed,
        "files_archived":len(rows),
        "securities_observed":len(observed),
        "file_generation_utc_attested":False,
        "historical_security_identity_attested":False,
        "historical_basket_membership_attested":False,
        "corporate_action_pit_attested":False,
        "provider_license_approved":False,
        "node_stress_score":None,
        "index_aics":None, "predictive_skill_score":None,
        "promotion":"BLOCKED", "trades_created":False,
        "notes":[
            "Official directories identify only listed securities visible in this retrieved snapshot.",
            "File creation time is exchange wall-clock, NOT an authenticated UTC release time.",
            "Neither directory provides benchmark membership, splits, dividends or prior ticker histories.",
            "Original source files reside in temporary CI artifacts pending usage-rights and retention review.",
        ],
    }


def _load_verified(root: Path) -> dict:
    manifest = json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("schema_version") != SCHEMA
            or manifest.get("node") != "AI Equities"
            or manifest.get("research_symbols") != list(RESEARCH_SYMBOLS)
            or manifest.get("scope") != "PROSPECTIVE_CURRENT_DIRECTORY_NOT_HISTORICAL_MEMBERSHIP"):
        raise ValueError("Unapproved listing capture metadata")
    capture = dt.datetime.fromisoformat(manifest["captured_at_utc"])
    if capture.tzinfo is None or capture.utcoffset() is None:
        raise ValueError("Untrusted snapshot timestamp")
    if capture > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
        raise ValueError("Capture dated into future")
    if (manifest.get("files_archived") != 2
            or manifest.get("securities_observed") != 7
            or manifest.get("file_generation_utc_attested") is not False
            or manifest.get("historical_security_identity_attested") is not False
            or manifest.get("historical_basket_membership_attested") is not False
            or manifest.get("corporate_action_pit_attested") is not False
            or manifest.get("provider_license_approved") is not False
            or manifest.get("node_stress_score") is not None
            or manifest.get("index_aics") is not None
            or manifest.get("predictive_skill_score") is not None
            or manifest.get("promotion") != "BLOCKED"
            or manifest.get("trades_created") is not False):
        raise ValueError("Unauthorized AICS listing PIT promotion")
    entries = manifest.get("original_files")
    if not isinstance(entries,list) or len(entries) != len(FILENAMES):
        raise ValueError("Incomplete official original directories")
    parsed = {}
    for entry in entries:
        filename = entry.get("filename")
        if filename not in FILENAMES or filename in parsed or entry.get("url") != BASE+filename:
            raise ValueError("Unapproved original directory entry")
        sha = entry.get("sha256")
        if not isinstance(sha,str) or not re.fullmatch("[0-9a-f]{64}",sha):
            raise ValueError("Invalid directory original fingerprint")
        p = Path(entry.get("original_path",""))
        if not p.is_absolute():
            p = Path.cwd()/p
        expected=(root.resolve()/"raw"/(filename.removesuffix(".txt")+"_"+sha+".txt")).resolve()
        if p.resolve()!=expected or not p.is_file():
            raise ValueError("Directory original escaped archived file path")
        raw=p.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=sha or len(raw)!=entry.get("bytes"):
            raise ValueError("Original directory SHA256 or length changed")
        sample=parse_directory(raw,filename)
        generated_date=dt.date.fromisoformat(
            sample["file_creation_wallclock_unverified_timezone"][:10])
        if abs((capture.date() - generated_date).days) > 2:
            raise ValueError("Directory historical relabeling or stale original")
        if (sample["directory_rows"] != entry.get("directory_rows")
                or sample["file_creation_wallclock_unverified_timezone"] !=
                entry.get("file_creation_wallclock_unverified_timezone")):
            raise ValueError("Manifest differs from original directory")
        parsed[filename]=sample["listings"]
    observed = manifest.get("observed_securities")
    if not isinstance(observed,list) or len(observed)!=len(RESEARCH_SYMBOLS):
        raise ValueError("Seven-current-symbol observation incomplete")
    if [entry.get("symbol") for entry in observed] != list(RESEARCH_SYMBOLS):
        raise ValueError("Changed AI research basket")
    for entry in observed:
        symbol=entry["symbol"]
        found=[(filename,parsed[filename][symbol]) for filename in FILENAMES
               if symbol in parsed[filename]]
        if len(found)!=1:
            raise ValueError("Missing/ambiguous original-listed instrument")
        filename,row=found[0]
        if (entry.get("directory") != filename or
                entry.get("market_code") != row.get("Exchange","NASDAQ") or
                entry.get("security_name") != row["Security Name"] or
                entry.get("test_issue") != "N" or row["Test Issue"] != "N" or
                entry.get("etf") != "N" or row["ETF"] != "N" or
                entry.get("listing_snapshot_only") is not True or
                entry.get("historical_membership_attested") is not False or
                entry.get("stock_split_dividend_attested") is not False):
            raise ValueError("Current directory status was relabeled as historical PIT")
    return manifest


def audit_directory(root: Path) -> dict:
    manifest = _load_verified(root)
    receipt = {
        "schema_version":"aics-ai-equities-directory-rehash-v1",
        "capture_utc":manifest["captured_at_utc"],
        "files_original_bytes_rehashed":2,
        "research_securities_observed":7,
        "original_sources_sha256": {e["filename"]:e["sha256"] for e in manifest["original_files"]},
        "historical_pit_attested":False,
        "historical_constituency_attested":False,
        "corporate_actions_pit_attested":False,
        "index_aics":None, "node_stress_score":None,
        "promotion":"BLOCKED", "trades_created":False,
    }
    (root/"rehash_receipt.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    return receipt


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",required=True,choices=("collect","audit"))
    parser.add_argument("--out",type=Path,
                        default=Path("aics_data/source_evidence/ai_equities_directory_live"))
    args=parser.parse_args()
    try:
        if args.mode=="collect":
            result=build_manifest(args.out,clock=lambda:dt.datetime.now(dt.timezone.utc))
            args.out.mkdir(parents=True,exist_ok=True)
            (args.out/"manifest.json").write_text(
                json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
            print(json.dumps({"captured_sources":result["files_archived"],
                "observed_research_securities":result["securities_observed"],
                "historical_pit":False,"index_aics":None}))
        else:
            receipt=audit_directory(args.out)
            print(json.dumps({"original_rehashes":receipt["files_original_bytes_rehashed"],
                "observed_research_securities":receipt["research_securities_observed"],
                "historical_pit":False,"index_aics":None}))
        return 0
    except (OSError,KeyError,TypeError,ValueError) as exc:
        print("AI Equities directory raw capture BLOCKED:",type(exc).__name__)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
