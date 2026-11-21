"""Ten consecutive reproducibility cycles of ten AICS analysis agents.

Each cycle independently reloads the SAME archived V17/V18/S&P research inputs
and current capture manifest, executes all 10 agents, and verifies exact
content equality and non-mutation. Replays are NOT new financial observations,
independent training samples, or 10 independent backtests.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

from scripts.aics_ten_analysis_agents import (
    CAPTURE, OUTPUT, SPX, V17, V18, read, run_agents
)

DEFAULT_OUTPUT = Path("aics_data/agent_runs/aics_ten_analysis_replay_10_cycles.json")
FIXED_CYCLES = 10


def _canonical(document):
    return json.dumps(document, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(blob):
    return hashlib.sha256(blob).hexdigest()


def replay(*, cycles=FIXED_CYCLES, as_of=None,
           v17=V17, v18=V18, sp500=SPX, manifest=CAPTURE,
           write_to=None):
    """Replay every analysis agent 10 times on unchanged real inputs.

    Immutable input SHA comparison before/after each cycle. Input is reloaded
    from persisted research files each time; the manifest is optional for
    an offline AICS-only run, but absence is explicitly exposed.
    """
    if cycles != FIXED_CYCLES:
        raise ValueError("Audit requires exactly ten runs")
    as_of = as_of or dt.datetime.now(dt.timezone.utc).date()
    if not isinstance(as_of, dt.date) or isinstance(as_of, dt.datetime):
        raise ValueError("Cycle cutoff must be an ISO calendar date")
    file_paths = (Path(v17), Path(v18), Path(sp500))
    mpath = Path(manifest) if manifest is not None else None
    required_paths = file_paths + ((mpath,) if mpath is not None and mpath.exists() else ())
    initial_hashes = {str(p): _sha(p.read_bytes()) for p in required_paths}
    cycles_report = []
    baseline_hash = None
    for idx in range(1, FIXED_CYCLES + 1):
        live_bytes = {str(p): _sha(p.read_bytes()) for p in required_paths}
        if live_bytes != initial_hashes:
            raise ValueError("Input research ledger mutated during ten-run replay")
        content = [read(p) for p in file_paths]
        capture = read(mpath) if mpath is not None and mpath.exists() else None
        r = run_agents(v17=content[0], v18=content[1], sp500=content[2],
                       captured=capture, as_of=as_of)
        if (r["agents_count"] != 10 or len(r["results"]) != 10
                or any(item["status"] != "research_pass" for item in r["results"])
                or r["complete_aics_index"] is not None
                or r["aics_sp500_spread"] is not None
                or r["certified_pit"] is not False
                or r["validated_market_predictive_skill"] is not False
                or r["production_model_updated"] is not False
                or r["trades_created"] is not False):
            raise ValueError("Incompatible model promotion or missing analyst agent")
        report_sha = _sha(_canonical(r))
        if baseline_hash is None:
            baseline_hash = report_sha
        if report_sha != baseline_hash:
            raise ValueError("Deterministic agent output drift across identical inputs")
        if {str(p): _sha(p.read_bytes()) for p in required_paths} != initial_hashes:
            raise ValueError("Analyst agent mutated original sources")
        coverage = r["results"][2]["result"]
        alerts = r["results"][8]["result"]["research_attention_flags"]
        cycles_report.append({
            "cycle": idx,
            "source_agents_present": r["source_agents_count"],
            "analysis_agents_passed": 10,
            "current_source_archives": r["actual_source_bytes_in_this_run"],
            "calendar_research_source_coverage_pct":
                coverage["calendar"]["research_observability_pct"],
            "market_weekday_research_source_coverage_pct":
                coverage["market"]["research_observability_pct"],
            "anomaly_research_attention_flags": alerts,
            "result_sha256": report_sha,
        })
    result = {
        "schema": "aics-ten-analysis-agents-ten-fixed-input-replay-v1",
        "as_of": as_of.isoformat(),
        "cycles": FIXED_CYCLES, "analysis_agents_per_cycle": 10,
        "agent_executions": FIXED_CYCLES * 10,
        "source_collector_cycles_performed_here": 0,
        "source_evidence_new_observations_from_replay": 0,
        "new_ml_training_samples_from_replay": 0,
        "independent_out_of_sample_backtests_created": 0,
        "source_input_sha256": initial_hashes,
        "source_manifest_available": mpath is not None and mpath.exists(),
        "cycle_report_sha256": baseline_hash,
        "all_results_bitwise_deterministic": True,
        "cycles_detail": cycles_report,
        "aics_complete_index": None,
        "aics_sp500_spread": None,
        "production_weights_modified": False,
        "trading_orders_created": False,
        "research_only": True,
    }
    if write_to is not None:
        dest = Path(write_to)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cycles", type=int, default=FIXED_CYCLES)
    p.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = p.parse_args()
    result = replay(cycles=args.cycles, write_to=args.out)
    print(json.dumps({
        "cycles": result["cycles"], "analysis_agent_executions": result["agent_executions"],
        "independent_new_source_observations": 0,
        "all_outputs_identical": result["all_results_bitwise_deterministic"],
        "calendar_research_coverage_pct":
            result["cycles_detail"][-1]["calendar_research_source_coverage_pct"],
        "new_trades": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
