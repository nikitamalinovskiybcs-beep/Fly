#!/usr/bin/env python3
"""Independently downloaded and SHA-256 checked official IR bytes: stage-2 only.

The immutable constants below were observed by downloading GitHub Actions run
44369543954, artifact 14458942315, opening the ZIP and checking every HTML
member's SHA256 against the manifest. Checksums are not vintage/PIT proof, and
this receipt cannot provide AICS node scores, OOS or certification.
"""
import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ZIP_SHA = "7f8712108be64add7afd4c77c03cc4c1cae48967b5b75102c9fea9fc75dc93bb"
MANIFEST_SHA = "ea1cd14825cec84605ab1718ee6292266edda9e1b5f39b51cd84387df8c51a80"
ARTIFACT_ID = 14458942315
RUN_URL = "https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44369543954"
RELEASE_SHAS = {
    "MET_2026Q3": "9bdb9237dd00271b828fb8e87d237dedb51a96bf22a7113a2be3607eea348fa3",
    "PRU_2026Q3": "6866aec4736b928a87d506e80edc4c457982b6b13524f20bbcf232426461fe36",
}
ALLOWED_HOSTS = {"www.metlife.com", "investor.prudential.com",
                 "investor.metlife.com"}


def verified_raw_insurers_archive(root: Path, manifest: dict) -> set[str]:
    """Count exactly one externally verified research raw-archive receipt."""
    all_rows = manifest.get("independently_recalculated_raw_archive_receipts", [])
    if (not isinstance(all_rows, list) or len(all_rows) > 2
            or any(not isinstance(x, dict)
                   or x.get("node") not in {"Insurers", "Neoclouds+SPV"}
                   for x in all_rows)):
        raise ValueError("unknown additional raw source receipt")
    rows = [x for x in all_rows if x["node"] == "Insurers"]
    if len(rows) > 1:
        raise ValueError("duplicate insurer archive receipt")
    if not rows:
        return set()
    row = rows[0]
    if not isinstance(row, dict) or row.get("node") != "Insurers":
        raise ValueError("additional archive cannot promote unrelated node")
    path_string = row.get("receipt_path")
    if not isinstance(path_string, str) or not path_string.startswith(
        "aics_data/progress/insurers_ir_raw_archive_receipt_"):
        raise ValueError("unapproved official IR archive receipt path")
    path = (root / path_string).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("missing source archive receipt")
    x = json.loads(path.read_text(encoding="utf-8"))
    if (x.get("schema_version") != "aics-ir-raw-archive-receipt-v1"
            or x.get("node") != "Insurers"
            or x.get("as_of") != manifest.get("report_as_of")
            or x.get("artifact_run_url") != RUN_URL
            or x.get("artifact_id") != ARTIFACT_ID
            or x.get("artifact_zip_sha256") != ZIP_SHA
            or x.get("internal_manifest_sha256") != MANIFEST_SHA
            or x.get("raw_archive_candidate_milestone_complete") is not True
            or x.get("certified_stress_score") is not None
            or x.get("index_aics") is not None
            or x.get("model_predictive_skill") is not None
            or x.get("promotion") != "BLOCKED"
            or x.get("trades_created") is not False):
        raise ValueError("archive receipt cannot establish a genuine raw-source stage")
    checks = x.get("independent_recalculation", {})
    if (checks.get("checked_files") != 4
            or checks.get("verified_hashes_matching") != 4
            or checks.get("earnings_disclosure_sources") != 2
            or checks.get("official_ir_index_sources") != 2
            or checks.get("historical_pit_independently_verified") is not False
            or checks.get("node_score_calibrated") is not False):
        raise ValueError("raw source bytes were not independently checked")
    files = x.get("original_files", [])
    if not isinstance(files, list) or len(files) != 4:
        raise ValueError("all four raw source files are required")
    found = {}
    type_count = {"quarterly_release": 0, "landing_page": 0}
    for obj in files:
        if not isinstance(obj, dict):
            raise ValueError("malformed archive entry")
        sid = obj.get("source_id")
        sha = obj.get("html_sha256")
        url = obj.get("url")
        if (not isinstance(sid, str) or sid in found
                or not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{64}", sha)
                or not isinstance(url, str)
                or urlsplit(url).scheme != "https"
                or urlsplit(url).hostname not in ALLOWED_HOSTS
                or obj.get("kind") not in type_count
                or not isinstance(obj.get("bytes"), int)
                or obj["bytes"] < 100):
            raise ValueError("invalid official IR raw source lineage")
        type_count[obj["kind"]] += 1
        found[sid] = sha
    if (type_count != {"quarterly_release": 2, "landing_page": 2}
            or any(found.get(k) != v for k, v in RELEASE_SHAS.items())):
        raise ValueError("original MetLife/Prudential releases do not match original archive")
    return {"Insurers"}
