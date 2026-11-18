#!/usr/bin/env python3
"""Auditable autonomous research loop. Never modifies production signals."""
import datetime as dt
import json
import os
from pathlib import Path

ROOT = Path("aics_data/live")
ROOT.mkdir(parents=True, exist_ok=True)
manifest_path = ROOT / "manifest.json"
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
else:
    manifest = {"results": [], "note": "Evidence manifest unavailable"}
results = manifest.get("results", [])
failed = [r for r in results if r.get("status") != "downloaded_unverified"]
proposals = []
for item in failed:
    proposals.append({
        "proposal_id": "source-" + str(item.get("id", "unknown")),
        "provider": "deterministic-diagnostics",
        "model": "rules-v1",
        "status": "proposed",
        "decision": "RESEARCH",
        "blocker": item.get("error", item.get("status", "unknown")),
        "next_experiment": "inspect source HTTP status, API limits and PIT coverage",
        "acceptance_test": "complete source download with provenance and vintage fields",
    })
if not results:
    proposals.append({
        "proposal_id": "missing-evidence", "provider": "deterministic-diagnostics",
        "model": "rules-v1", "status": "blocked", "decision": "BLOCKED",
        "blocker": "No evidence results", "next_experiment": "run evidence workflow",
        "acceptance_test": "manifest contains source-level results",
    })
report = {
    "as_of": dt.datetime.now(dt.timezone.utc).isoformat(),
    "mode": "research_only",
    "source_count": len(results),
    "downloaded_unverified": len(results) - len(failed),
    "failed_sources": len(failed),
    "proposals": proposals,
    "index_aics": None,
    "model_score": None,
    "promotion": "BLOCKED",
    "production_weights_changed": False,
    "verdict_mutated": False,
    "trades_created": False,
    "next_step": "collect complete PIT evidence; then evaluate chronological 24m OOS",
}
(ROOT / "agent_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
