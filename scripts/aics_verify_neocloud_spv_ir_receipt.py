#!/usr/bin/env python3
"""Pin actual SHA-verified CoreWeave, Nebius and Equinix IR archives, stage-2 only.

Verification performed against original HTML ZIP members in GitHub Actions
run 44371061805, artifact 14459560533, captured 2026-11-18.
No historical-PIT, SPV legal status, calibrated scores, or OOS claims.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ZIP_SHA = "92559e7d8ef4494e21c6ec450ad32af85345db2a2ac8ac9a5320dd240d4473b8"
MANIFEST_SHA = "399938eaf45390abf5d891054daf6c744340a24fb489b510b5e36cea9344b22c"
ARTIFACT_ID = 14459560533
RUN_URL = "https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44371061805"
SOURCE_SHAS = {
    "CRWV_2026Q3": "b49ab90435c7debdc5d7ac85ac9db69bf6fee7f6ecb5b1edd93bbc8b2dd85edc",
    "NBIS_2026Q3": "79e7481410b4ce1b3e91479426fe8a850b0c32cfa652723eb7384bda49312558",
    "NBIS_CITI_20261022": "6ca33efcb5fddfab1141945ade8f00554dd7c33b9b84f6fe461c007e0164ed13",
    "EQIX_2026Q3": "f079aa418f6043f3faa363c39e73ac7ea1a33dbe7a1f5af072f5bcafc4682195",
}
INDEX_SHAS = {
    "CRWV_IR_INDEX_20261118": "ccff87481e01398d7c9931457e7ef061bb75f09626aa3a992b07977be8657729",
    "NBIS_IR_INDEX_20261118": "0fe373e6f7bf4d9d77a5094ba887733fb227b16356191b58759facc3cfa51b9e",
    "EQIX_IR_INDEX_20261118": "d9a364b8e7b02668485b9f3a6a786d6742dbc24173938a6a53168ab0fcd9a67c",
}
HOSTS = frozenset({"investors.coreweave.com", "nebius.com",
                   "equinix.mediaroom.com", "investor.equinix.com"})


def verified_neocloud_spv_archives(root: Path, manifest: dict) -> set[str]:
    rows = manifest.get("independently_recalculated_raw_archive_receipts", [])
    if not isinstance(rows, list):
        raise ValueError("invalid raw archive receipts list")
    selected = [row for row in rows if isinstance(row, dict)
                and row.get("node") == "Neoclouds+SPV"]
    if len(selected) > 1:
        raise ValueError("duplicate SPV/Neocloud archive milestone")
    if not selected:
        return set()
    row = selected[0]
    path_text = row.get("receipt_path")
    if (not isinstance(path_text, str) or path_text !=
            "aics_data/progress/neocloud_spv_ir_raw_archive_receipt_2026-11-18.json"):
        raise ValueError("unsupported Neocloud/SPV raw archive receipt")
    path = (root / path_text).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("missing Neocloud/SPV archive receipt")
    x = json.loads(path.read_text(encoding="utf-8"))
    if (x.get("schema_version") != "aics-ir-raw-archive-receipt-v1"
            or x.get("node_group") != "Neoclouds+SPV"
            or x.get("candidate_nodes") != ["Neoclouds", "SPV"]
            or x.get("as_of") != manifest.get("report_as_of")
            or x.get("artifact_run_url") != RUN_URL
            or x.get("artifact_id") != ARTIFACT_ID
            or x.get("artifact_zip_sha256") != ZIP_SHA
            or x.get("internal_manifest_sha256") != MANIFEST_SHA
            or x.get("raw_archive_candidate_milestone_complete") is not True
            or x.get("index_aics") is not None
            or x.get("spv_node_score") is not None
            or x.get("neoclouds_node_score") is not None
            or x.get("model_predictive_skill") is not None
            or x.get("promotion") != "BLOCKED"
            or x.get("trades_created") is not False):
        raise ValueError("unverified or misclassified SPV/Neocloud source archive")
    checked = x.get("independent_recalculation", {})
    if (checked.get("checked_files") != 7
            or checked.get("verified_hashes_matching") != 7
            or checked.get("quarterly_and_financing_releases") != 4
            or checked.get("official_ir_index_sources") != 3
            or checked.get("historical_pit_independently_verified") is not False
            or checked.get("sec_14_day_source_filing_verified") is not False
            or checked.get("spv_economic_structure_independently_verified") is not False
            or checked.get("audited_node_scores") != 0):
        raise ValueError("unsupported scientific promotion in archive receipt")
    roles = x.get("archive_roles", {})
    if (roles != {"Neoclouds": ["CRWV_2026Q3", "NBIS_2026Q3"],
                  "SPV": ["NBIS_CITI_20261022", "EQIX_2026Q3"]}):
        raise ValueError("source roles misidentified as evidence for other nodes")
    entries = x.get("original_files")
    if not isinstance(entries, list) or len(entries) != 7:
        raise ValueError("incomplete source archive")
    expected = {**SOURCE_SHAS, **INDEX_SHAS}
    seen = {}
    for row in entries:
        if not isinstance(row, dict):
            raise ValueError("malformed IR source")
        sid = row.get("source_id")
        url = row.get("url")
        sha = row.get("html_sha256")
        if (sid in seen or sid not in expected
                or sha != expected[sid]
                or not isinstance(url, str)
                or urlsplit(url).scheme != "https"
                or urlsplit(url).hostname not in HOSTS
                or not isinstance(row.get("bytes"), int)
                or row["bytes"] < 100):
            raise ValueError("source bytes/URL/sha mismatch")
        if sid in INDEX_SHAS and row.get("kind") != "landing_page":
            raise ValueError("missing true IR index role")
        if sid in SOURCE_SHAS and row.get("kind") == "landing_page":
            raise ValueError("IR document mislabeled")
        seen[sid] = sha
    if seen != expected:
        raise ValueError("not all original IR sources are archived")
    return {"Neoclouds", "SPV"}
