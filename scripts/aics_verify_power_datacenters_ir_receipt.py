#!/usr/bin/env python3
"""Pinned Power/Data Centers raw HTML receipt gate (stage 2, not AICS PIT)."""
import json
from pathlib import Path
from urllib.parse import urlsplit

ZIP_SHA="76766627f1a5056c1684b1743cda233e71a882360227de9c73bcdd6a9d7590e6"
MANIFEST_SHA="60730db46f3f0ca9be42775ab9213606c26d4c330c8b7c3e17a20095b419c8cd"
RUN_URL="https://github.com/nikitamalinovskiybcs-beep/Fly/actions/runs/44375113829"
ARTIFACT_ID=14459494653
PATH="aics_data/progress/power_datacenters_ir_raw_archive_receipt_2026-11-18.json"
RELEASES={
 "APLD_FY27Q1":("Applied Digital","6ea9c370146a6ca1ba2eb80f8b001645c2921b7f3803e212380b623e81220813"),
 "EQIX_2026Q3":("Equinix","60e4d13fbbf3861ba0b9480fc9312de6d4157b695affddb5797e37d03935b5ae"),
}
INDEXES={
 "Applied Digital":"512429568e701a9002656e8cfb18bd13cd1824af5fa36447fd373134f4f934d7",
 "Equinix":"d9a364b8e7b02668485b9f3a6a786d6742dbc24173938a6a53168ab0fcd9a67c",
}
HOSTS=frozenset({"ir.applieddigital.com","equinix.mediaroom.com","investor.equinix.com"})


def verified_power_datacenters_archive(root:Path,manifest:dict)->set[str]:
    source=manifest.get("independently_recalculated_raw_archive_receipts",[])
    if not isinstance(source,list):
        raise ValueError("invalid raw archive list")
    found=[x for x in source if isinstance(x,dict) and x.get("node")=="Power/Data Centers"]
    if len(found)>1:
        raise ValueError("duplicate Power/Data Centers receipt")
    if not found:
        return set()
    if found[0].get("receipt_path")!=PATH:
        raise ValueError("unknown power original source archive")
    root=root.resolve()
    file=(root/PATH).resolve()
    if not file.is_relative_to(root) or not file.is_file():
        raise ValueError("missing Power/Data Centers original source receipt")
    d=json.loads(file.read_text(encoding="utf-8"))
    if (d.get("schema_version")!="aics-ir-raw-archive-receipt-v1"
        or d.get("as_of")!=manifest.get("report_as_of")
        or d.get("node_group")!="Power/Data Centers"
        or d.get("candidate_nodes")!=["Power/Data Centers"]
        or d.get("artifact_zip_sha256")!=ZIP_SHA
        or d.get("internal_manifest_sha256")!=MANIFEST_SHA
        or d.get("artifact_run_url")!=RUN_URL
        or d.get("artifact_id")!=ARTIFACT_ID
        or d.get("raw_archive_candidate_milestone_complete") is not True
        or d.get("independently_verified_pit") is not False
        or d.get("validated_node_score") is not None
        or d.get("index_aics") is not None
        or d.get("predictive_skill_score") is not None
        or d.get("promotion")!="BLOCKED"
        or d.get("trades_created") is not False):
        raise ValueError("raw Power receipt tries unsupported certification")
    checks=d.get("independent_recalculation",{})
    if (checks.get("checked_files")!=4
        or checks.get("verified_hashes_matching")!=4
        or checks.get("official_quarterly_earnings_releases")!=2
        or checks.get("official_ir_index_pages")!=2
        or checks.get("independent_historical_pit_attestation") is not False
        or checks.get("calibrated_power_stress_score") is not False):
        raise ValueError("not all original Power HTML bytes independently checked")
    if d.get("raw_source_roles")!={"Power/Data Centers":["APLD_FY27Q1","EQIX_2026Q3"]}:
        raise ValueError("incorrect raw source power roles")
    r=d.get("releases"); i=d.get("ir_indexes")
    if not isinstance(r,list) or len(r)!=2 or not isinstance(i,list) or len(i)!=2:
        raise ValueError("incomplete primary source and IR index pairs")
    seen=set()
    for x in r:
        sid=x.get("source_id")
        if (sid in seen or sid not in RELEASES or
            x.get("issuer")!=RELEASES[sid][0] or
            x.get("html_sha256")!=RELEASES[sid][1] or
            x.get("kind")!="issuer_ir_release_html" or
            x.get("score_eligible") is not False or
            not isinstance(x.get("bytes"),int) or x["bytes"]<500 or
            not isinstance(x.get("url"),str) or
            urlsplit(x["url"]).scheme!="https" or
            urlsplit(x["url"]).hostname not in HOSTS or
            not isinstance(x.get("release_date"),str) or
            x["release_date"]>manifest["report_as_of"]):
            raise ValueError("unknown or altered power source release")
        seen.add(sid)
    if seen!=set(RELEASES):
        raise ValueError("missing one original quarterly Power report")
    seen=set()
    for x in i:
        issuer=x.get("issuer")
        if (issuer in seen or issuer not in INDEXES or
            x.get("html_sha256")!=INDEXES[issuer] or
            x.get("kind")!="issuer_ir_landing_html" or
            x.get("score_eligible") is not False or
            not isinstance(x.get("bytes"),int) or x["bytes"]<500 or
            not isinstance(x.get("url"),str) or
            urlsplit(x["url"]).scheme!="https" or
            urlsplit(x["url"]).hostname not in HOSTS):
            raise ValueError("unknown or altered power IR homepage")
        seen.add(issuer)
    if seen!=set(INDEXES):
        raise ValueError("missing original power investor homepages")
    return {"Power/Data Centers"}
