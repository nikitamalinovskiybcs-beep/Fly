#!/usr/bin/env python3
"""Verify AICS Insurers SEC artifact integrity; NEVER certify historical PIT or scores.

Check byte-for-byte hashes of SEC JSON, linked accession index appendices, and
research CSV.  A pass means only that *locally archived bytes* are internally
consistent and comply with the AICS 14-calendar-day eligibility rule.

No claim of independent source attestation, original filing semantics,
Level 3 risk calibration, or predictive out-of-sample performance is made.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit

from scripts.aics_collect_insurers_sec import (COLUMNS, INSTANT_US_GAAP_TAGS, ISSUERS,
                                            extract_candidates)

EXPECTED_STATUS = "downloaded_unverified"


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_bundle(directory: Path, repository_root: Path) -> dict:
    directory = directory.resolve()
    repository_root = repository_root.resolve()
    if not directory.is_relative_to(repository_root):
        raise ValueError("evidence directory outside repository")
    manifest_path = directory / "manifest.json"
    csv_path = directory / "insurer_balance_sheet_candidates.csv"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "aics-insurers-sec-evidence-v1":
        raise ValueError("unknown evidence manifest version")
    if (manifest.get("independently_verified_pit") is not False
            or manifest.get("insurers_node_score") is not None
            or manifest.get("index_aics") is not None
            or manifest.get("predictive_skill_score") is not None
            or manifest.get("promotion") != "BLOCKED"
            or manifest.get("trades_created") is not False):
        raise ValueError("manifest claims unsupported scores or PIT attestation")
    cutoff = dt.date.fromisoformat(manifest["as_of"])
    if sha_file(csv_path) != manifest.get("csv_sha256"):
        raise ValueError("research CSV checksum mismatch")
    row_count = 0
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != list(COLUMNS):
            raise ValueError("unexpected insurer evidence table schema")
        rows = list(reader)
    if not isinstance(manifest.get("issuers"), list):
        raise ValueError("missing insurer archive inventory")
    source_map = {}
    for item in manifest["issuers"]:
        name = item.get("issuer")
        if name not in ISSUERS or name in source_map or item.get("cik") != ISSUERS[name]:
            raise ValueError("invalid or duplicate issuer")
        source_map[name] = item
    if set(source_map) != set(ISSUERS):
        raise ValueError("incomplete insurer source manifest")
    referenced = {}
    verified_file_count = 0
    decoded_raw = {}
    replayed_rows = []
    first_period = (dt.date.fromisoformat(manifest["first_period"])
                    if manifest.get("first_period") else None)

    def check_raw(item: dict) -> str:
        nonlocal verified_file_count
        raw_path = item.get("raw_path")
        checksum = item.get("sha256")
        if (not isinstance(raw_path, str) or not isinstance(checksum, str)
                or re.fullmatch(r"[a-f0-9]{64}", checksum) is None):
            raise ValueError("missing SEC source path or SHA256")
        untrusted = Path(raw_path)
        path = (untrusted if untrusted.is_absolute()
                else repository_root / untrusted).resolve()
        if not path.is_relative_to(directory / "raw") or not path.is_file():
            raise ValueError("SEC source path missing or outside raw directory")
        payload = path.read_bytes()
        if (hashlib.sha256(payload).hexdigest() != checksum
                or len(payload) != item.get("bytes")):
            raise ValueError("SEC original downloaded byte digest mismatch")
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            raise ValueError("SEC original is not an object")
        decoded_raw[checksum] = parsed
        verified_file_count += 1
        return checksum

    downloaded = 0
    history_count = 0
    for name, item in source_map.items():
        if item.get("status") != EXPECTED_STATUS:
            # A genuine collection failure is not an integrity certification.
            if item.get("status") not in {"collection_error", "not_downloaded"}:
                raise ValueError("unknown insurer collection status")
            referenced[name] = None
            continue
        downloaded += 1
        sources = item.get("sources")
        if not isinstance(sources, dict) or set(sources) != {"submissions", "companyfacts"}:
            raise ValueError("incomplete primary source set")
        shas = {kind: check_raw(sources[kind]) for kind in sources}
        history = item.get("historical_index_pages", [])
        if not isinstance(history, list):
            raise ValueError("historical index page list malformed")
        history_shas = set()
        historical_pages = []
        for h in history:
            sha = check_raw(h)
            historical_pages.append((decoded_raw[sha], sha))
            if sha in history_shas:
                raise ValueError("duplicated historical SEC source")
            history_shas.add(sha)
            history_count += 1
        if len(history) != item.get("historical_index_pages_downloaded", 0):
            raise ValueError("historical index page count mismatch")
        replay, _ = extract_candidates(
            name, decoded_raw[shas["companyfacts"]],
            decoded_raw[shas["submissions"]], cutoff,
            shas["companyfacts"], shas["submissions"],
            first_period=first_period, historical_pages=historical_pages,
        )
        if len(replay) != item.get("candidate_observations"):
            raise ValueError("SEC raw replay differs from issuer candidate count")
        replayed_rows.extend(replay)
        decoded_raw.clear()
        referenced[name] = {
            "companyfacts": shas["companyfacts"],
            "submissions": shas["submissions"],
            "indices": history_shas | {shas["submissions"]},
        }
    if downloaded != manifest.get("successful_issuers"):
        raise ValueError("downloaded source count mismatch")
    if history_count != manifest.get("historical_index_pages_downloaded", 0):
        raise ValueError("historical page count mismatch")
    if downloaded == 0:
        raise ValueError("no complete downloaded SEC issuer to verify")
    for row in rows:
        issuer = row["issuer"]
        if issuer not in referenced or referenced[issuer] is None:
            raise ValueError("candidate row lacks its archived issuer source")
        sources = referenced[issuer]
        if (row["cik"] != ISSUERS[issuer] or row["candidate_node"] != "Insurers"
                or row["taxonomy"] != "us-gaap"
                or row["tag"] not in INSTANT_US_GAAP_TAGS
                or row["unit"] != "USD"
                or row["observation_start"] not in ("", None)
                or row["form"] not in {"10-Q", "10-K", "10-Q/A", "10-K/A"}
                or row["score_eligible"] != "false"
                or row["pit_verified"] != "false"):
            raise ValueError("unsafe candidate row")
        if (row["companyfacts_raw_sha256"] != sources["companyfacts"]
                or row["submissions_raw_sha256"] != sources["submissions"]
                or row["accession_index_raw_sha256"] not in sources["indices"]):
            raise ValueError("candidate points at unarchived source content")
        observed = dt.date.fromisoformat(row["observation_date"])
        filed = dt.date.fromisoformat(row["filed_at"])
        available = dt.date.fromisoformat(row["available_at"])
        if not (observed <= filed <= cutoff and available == filed + dt.timedelta(days=14)
                and available <= cutoff):
            raise ValueError("SEC 14-day PIT chronology violated")
        accession = row["accession"]
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
            raise ValueError("invalid SEC accession identifier")
        path = urlsplit(row["sec_filing_url"])
        prefix = ("/Archives/edgar/data/" + str(int(row["cik"])) + "/"
                  + accession.replace("-", "") + "/")
        if (path.scheme != "https" or path.netloc != "www.sec.gov"
                or not path.path.startswith(prefix)):
            raise ValueError("candidate filing URL inconsistent with accession")
        try:
            number = float(row["value"])
            if not math.isfinite(number):
                raise ValueError("not finite")
        except (ValueError, TypeError):
            raise ValueError("candidate has invalid value")
        row_count += 1
    if row_count != manifest.get("candidate_observations"):
        raise ValueError("candidate rows count mismatch")
    if rows != replayed_rows:
        raise ValueError("research CSV does not exactly replay from archived SEC source JSON")
    return {
        "status": "LOCAL_ARCHIVE_HASHES_VERIFIED_RESEARCH_ONLY",
        "checked_files": verified_file_count,
        "checked_issuers": downloaded,
        "checked_historical_index_pages": history_count,
        "checked_candidate_rows": row_count,
        "candidate_rows_replayed_from_raw_sec": len(replayed_rows),
        "independently_verified_pit": False,
        "insurers_node_score": None,
        "index_aics": None,
        "predictive_skill_score": None,
        "promotion": "BLOCKED",
        "note": ("Checks evidence bundle integrity only. Original SEC filing facts, "
                 "historical publication and validated insurer stress are unaudited.")
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path,
                        default=Path("aics_data/source_evidence/insurers_sec"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    result = verify_bundle(args.directory, args.repo_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
