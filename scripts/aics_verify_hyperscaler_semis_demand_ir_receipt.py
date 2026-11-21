#!/usr/bin/env python3
"""Pinned raw-source provenance gate for three AICS corporate evidence nodes.

Two independent acts: (1) original HTML bytes from GitHub Actions artifact
14460201430 were downloaded and re-hashed, and (2) this policy checks the
versioned receipt against exact verified SHA256 digests and AICS raw-source
roles. This only marks *source archive stage 2/6*. It NEVER establishes
historical SEC PIT, an audited numerical stress score, or certified AICS.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ARTIFACT_ID = 14460201430
RUN_URL = "https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44373944211"
ZIP_SHA = "3e70ca77fc14d4f14ace2cb5dd483f9bdf878b160acd3b7ccf4a51192b4d8580"
MANIFEST_SHA = "f44fd7b722b255216c68af8f1007f4ed728a3f8a66e1f1e7eb94ff967b69f0fa"
RECEIPT_PATH = "aics_data/progress/hyperscaler_semiconductors_demand_ir_raw_archive_receipt_2026-11-18.json"
SOURCE_SHA = {
    "MSFT_FY27Q1": "bfcfb04637d8caa8ffbcc5d017c7d7a4d26a01677f6fa8913fff81210d5d1c7e",
    "GOOGL_2026Q3": "7b5b344f9e950e620b7f6dfeced6b3a0396364271cb3abdc6a0497bc31f6ea30",
    "AMZN_2026Q3": "a94780073899490af9aebfa6236cb7710a111e735f67605735ff0e295650d445",
    "META_2026Q3": "1748bc0838ed07d0c6861e18da65ae416a7d029b356c13ed2a37429b848d3b5d",
    "NVDA_FY27Q3": "386488d69782db8f6ed4a493770e0ab98059e7de5e0c6b7ec61305865e0143a2",
    "MU_FY26Q4": "b4b7d01967abf31ed88be1e0cc573a54f40a5d9016ab8ce999172923a0e61d65",
    "ORCL_FY27Q1": "b97fa5e901a418f6eae98ef20c62f16b4681f2a9bdce0c3a7f92177fe64d662f",
}
INDEX_SHA = {
    "Microsoft": "b1b260d04729110a04fc23c7a3fb1bf103208c3631a03ad877b3863e2e80a758",
    "Alphabet": "fa3a5ef5955111105eb1ccb3363d74cbed437578a1f02d4406043f669a32929d",
    "Amazon": "c69f1673e5c9c4976b5939ce3c106e7698871363fda0230a5300c39caaca6836",
    "Meta": "b8bddfe1d2e96499d0448de7274d75bb26370e0efcb0a175b00cfb267f63d06f",
    "NVIDIA": "1ce135168f3aa0a38a75a99555559b63c9da991c451890570e8f379f64a56847",
    "Micron": "d968cd9d328cf86decea23392b5fd4157705c3aa7d865863ec4f07a0d8ef75b3",
    "Oracle": "895094ceddb1dd71321edff339698779a89619bda45244d31160a6a63767b1bf",
}
ROLES = {
    "Hyperscalers": ("MSFT_FY27Q1", "GOOGL_2026Q3", "AMZN_2026Q3", "META_2026Q3"),
    "Semiconductors Supply": ("NVDA_FY27Q3", "MU_FY26Q4"),
    "AI Demand": ("ORCL_FY27Q1",),
}
SOURCE_ISSUER = {
    "MSFT_FY27Q1": "Microsoft",
    "GOOGL_2026Q3": "Alphabet",
    "AMZN_2026Q3": "Amazon",
    "META_2026Q3": "Meta",
    "NVDA_FY27Q3": "NVIDIA",
    "MU_FY26Q4": "Micron",
    "ORCL_FY27Q1": "Oracle",
}
HOSTS = frozenset({
    "www.microsoft.com", "abc.xyz", "ir.aboutamazon.com",
    "investor.atmeta.com", "investor.nvidia.com",
    "investors.micron.com", "investor.oracle.com",
})


def verified_hyperscaler_semis_demand_archives(root: Path, manifest: dict) -> set[str]:
    rows = manifest.get("independently_recalculated_raw_archive_receipts", [])
    if not isinstance(rows, list):
        raise ValueError("invalid archive receipt collection")
    selected = [x for x in rows if isinstance(x, dict) and
                x.get("node") == "Hyperscalers+Semiconductors Supply+AI Demand"]
    if len(selected) > 1:
        raise ValueError("duplicate corporate IR archive receipt")
    if not selected:
        return set()
    item = selected[0]
    if item.get("receipt_path") != RECEIPT_PATH:
        raise ValueError("unknown corporate IR archive receipt path")
    path = (root / RECEIPT_PATH).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("missing corporate IR source archive receipt")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data.get("schema_version") != "aics-ir-raw-archive-receipt-v1"
            or data.get("as_of") != manifest.get("report_as_of")
            or data.get("node_group") != item["node"]
            or data.get("candidate_nodes") != list(ROLES)
            or data.get("artifact_id") != ARTIFACT_ID
            or data.get("artifact_run_url") != RUN_URL
            or data.get("artifact_zip_sha256") != ZIP_SHA
            or data.get("internal_manifest_sha256") != MANIFEST_SHA
            or data.get("raw_archive_candidate_milestone_complete") is not True
            or data.get("independently_verified_pit") is not False
            or data.get("historic_sec_vintage_verified") is not False
            or data.get("audit_node_scores") != {node: None for node in ROLES}
            or data.get("index_aics") is not None
            or data.get("predictive_skill_score") is not None
            or data.get("promotion") != "BLOCKED"
            or data.get("trades_created") is not False):
        raise ValueError("raw archive receipt misrepresents model eligibility")
    checks = data.get("independent_recalculation", {})
    if (checks.get("checked_files") != 14
            or checks.get("verified_hashes_matching") != 14
            or checks.get("official_quarterly_or_fiscal_earnings_release_pages") != 7
            or checks.get("official_ir_index_pages") != 7
            or checks.get("historical_pit_independently_verified") is not False
            or checks.get("sec_14_day_source_filing_verified") is not False
            or checks.get("source_to_metric_scoring_validated") is not False
            or checks.get("audited_node_scores") != 0):
        raise ValueError("incomplete raw-source byte verification or unsafe promotion")
    roles = data.get("raw_source_roles")
    if roles != {key: list(v) for key, v in ROLES.items()}:
        raise ValueError("raw source role assignment changed")
    releases, indexes = data.get("releases"), data.get("ir_indexes")
    if (not isinstance(releases, list) or not isinstance(indexes, list)
            or len(releases) != 7 or len(indexes) != 7):
        raise ValueError("missing source reports or landing pages")
    read_release, read_index = {}, {}
    for row in releases:
        sid = row.get("source_id")
        issuer = row.get("issuer")
        if (sid in read_release or sid not in SOURCE_SHA
                or issuer != SOURCE_ISSUER[sid]
                or row.get("html_sha256") != SOURCE_SHA[sid]
                or row.get("candidate_node") != next(
                    (node for node, ids in ROLES.items() if sid in ids), None)
                or row.get("kind") != "issuer_ir_release_html"
                or row.get("score_eligible") is not False
                or not isinstance(row.get("bytes"), int) or row["bytes"] < 500
                or not isinstance(row.get("url"), str)
                or urlsplit(row["url"]).scheme != "https"
                or urlsplit(row["url"]).hostname not in HOSTS
                or not isinstance(row.get("release_date"), str)
                or row["release_date"] > manifest["report_as_of"]):
            raise ValueError("unmatched or invalid official issuer release")
        read_release[sid] = row["html_sha256"]
    for row in indexes:
        issuer = row.get("issuer")
        if (issuer in read_index or issuer not in INDEX_SHA
                or row.get("html_sha256") != INDEX_SHA[issuer]
                or row.get("kind") != "issuer_ir_landing_html"
                or row.get("score_eligible") is not False
                or not isinstance(row.get("bytes"), int) or row["bytes"] < 500
                or not isinstance(row.get("url"), str)
                or urlsplit(row["url"]).scheme != "https"
                or urlsplit(row["url"]).hostname not in HOSTS):
            raise ValueError("unmatched or invalid issuer IR index")
        read_index[issuer] = row["html_sha256"]
    if read_release != SOURCE_SHA or read_index != INDEX_SHA:
        raise ValueError("incomplete source hash coverage")
    return set(ROLES)
