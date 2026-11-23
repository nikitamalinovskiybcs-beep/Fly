"""Ten AICS-specific analysis agents; complements the ten source collectors.

Research only: no future data, fabricated scores, full-index promotion,
investment signal, calibration or trading. The 10 agents have independently
testable, deterministic responsibilities and run on the V18 original research
panel plus the current collector's live-capture manifest when supplied.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_source_anomaly_ml import (
    observed_events, online_learn,
)

ROOT = Path("aics_data/research")
V17 = ROOT / "aics_24m_multi_node_publication_overlay_2026-11-21.json"
V18 = ROOT / "aics_v18_private_credit_24m_pit_proxy_overlay_2026-11-22.json"
SPX = ROOT / "sp500_24_month_closes_2026-11-21.json"
CAPTURE = Path("aics_data/agent_runs/manifest.json")
OUTPUT = Path("aics_data/agent_runs/aics_ten_analysis_agents_report.json")
TWOPLACES = Decimal("0.01")
MODELS = ("calendar", "market")
AGENT_NAMES = (
    "SourceLineageAgent",
    "PITChronologyAgent",
    "CoverageAgent",
    "FreshnessAgent",
    "ScoreAuditAgent",
    "RiskAttributionAgent",
    "StressSensitivityAgent",
    "SP500AlignmentAgent",
    "OnlineAnomalyAgent",
    "GovernanceDirectorAgent",
)
assert len(AGENT_NAMES) == 10 and sum(WEIGHTS.values()) == 1050
assert len(WEIGHTS) == 11


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dec(x):
    if isinstance(x, bool):
        raise ValueError("Boolean is not a score")
    y = Decimal(str(x))
    if not y.is_finite():
        raise ValueError("Nonfinite score")
    return y


def round2(x):
    return str(dec(x).quantize(TWOPLACES, rounding=ROUND_HALF_UP))


def pct(weight_months):
    return round2(dec(weight_months) * 100 / dec(24 * 1050))


def _asof(date):
    if not isinstance(date, dt.date) or isinstance(date, dt.datetime):
        raise ValueError("As-of must be an actual date")
    if date > dt.datetime.now(dt.timezone.utc).date():
        raise ValueError("Future as-of cannot be declared")
    return date


def _data(v17, v18, sp500, captured):
    if (v17.get("schema") != "aics-24m-multi-node-first-public-date-research-overlay-v1"
            or v18.get("schema") != "aics-v18-24m-private-credit-original-sec-expost-research-overlay-v1"
            or v17.get("independently_historical_pit_attested") is not False
            or v18.get("historical_pit_source_bytes_independently_attested") is not False
            or v18.get("scores_are_expost_not_preregistered") is not True
            or v18.get("underlying") != str(V17)
            or v18.get("full_11node_index_months") != 0
            or v18.get("aics_sp500_spread_months") != 0
            or v18.get("production_index_changed") is not False
            or v18.get("trades_created") is not False
            or sp500.get("symbol") != "GSPC"
            or len(sp500.get("points", [])) != 24
            or len(v18.get("monthly_calendar_end_research", [])) != 24
            or len(v18.get("monthly_last_weekday_market_proxy", [])) != 24):
        raise ValueError("Unexpected research source or false certification")

    if captured is not None:
        if (captured.get("schema") != "aics-ten-agents-current-source-collector-v1"
                or captured.get("agent_count") != 10
                or captured.get("unique_publisher_sources") != 20
                or captured.get("current_download_not_historical_pit") is not True
                or captured.get("index_aics") is not None
                or captured.get("independently_verified_node_scores") != 0
                or captured.get("trades_created") is not False):
            raise ValueError("Invalid current collectors provenance or promotion")
        source_ids = [s["source_id"] for s in captured["sources"]]
        if len(source_ids) != 20 or len(set(source_ids)) != 20:
            raise ValueError("Missing or duplicate raw source receipt")
        archived = sum(s["status"] == "archived_current_original_not_pit"
                       for s in captured["sources"])
        if archived != captured["original_sources_archived"]:
            raise ValueError("Source manifest does not match receipts")
    return {
        "v17": v17, "v18": v18, "sp500": sp500, "capture": captured,
        "series": {
            "calendar": v18["monthly_calendar_end_research"],
            "market": v18["monthly_last_weekday_market_proxy"],
        },
    }


def agent_1_lineage(data):
    """Input provenance, 24m structure, immutable model weight roster."""
    v18 = data["v18"]
    rows = data["series"]["calendar"]
    expected = [f"{2024+(10+i)//12}-{(10+i)%12+1:02d}" for i in range(24)]
    if [r["month"] for r in rows] != expected:
        raise ValueError("24-month source chronology mismatch")
    if [r["month"] for r in data["series"]["market"]] != expected:
        raise ValueError("Market and research month roster mismatch")
    if [r["month"] for r in data["sp500"]["points"]] != expected:
        raise ValueError("S&P 500 original observations have wrong months")
    if data["v17"].get("node_weights") != WEIGHTS:
        raise ValueError("V17 node weights changed")
    if len(v18["source_events"]) != 7 or v18["new_original_sec_issuer_quarter_records"] != 24:
        raise ValueError("Private Credit 24 issuer-quarter ledger or source comparisons missing")
    return {
        "input_panels": 2, "months_per_panel": 24,
        "node_weights_total": 1050, "node_count": 11,
        "new_private_credit_issuer_quarters": 24,
        "new_private_credit_breadth_events": 7,
        "historical_pit_certified": False,
    }


def agent_2_chronology(data, as_of):
    """Guard: research eligible dates never exceed a panel cutoff or now."""
    inspected = 0
    cutoff_difference_months = []
    for idx, month in enumerate(data["series"]["calendar"]):
        market = data["series"]["market"][idx]
        cday = dt.date.fromisoformat(month["cutoff_date"])
        mday = dt.date.fromisoformat(market["cutoff_date"])
        if mday > cday or cday > as_of:
            raise ValueError("Market cutoff after calendar or future date")
        if mday < cday:
            cutoff_difference_months.append(month["month"])
        for row, limit in ((month, cday), (market, mday)):
            if row.get("full_aics") is not None or row.get("aics_sp500_spread") is not None:
                raise ValueError("Full index or market spread improperly promoted")
            if row.get("historical_pit_certified") is not False:
                raise ValueError("Unverified panel marked PIT")
            for node, record in row["node_scores"].items():
                published = dt.date.fromisoformat(record["research_eligible_date"])
                if published > limit or node not in WEIGHTS:
                    raise ValueError("Future/unknown source eligible event")
                score = dec(record["score"])
                if not 0 <= score <= 100:
                    raise ValueError("Out-of-bound 0..100 score")
                inspected += 1
    if data["v18"].get("scores_are_expost_not_preregistered") is not True:
        raise ValueError("Lookahead scoring method not disclosed")
    return {
        "source_date_checks": inspected, "calendar_vs_market_cutoff_diverges": cutoff_difference_months,
        "date_only_sec_research_proxy": "filed_at+1_cal_day",
        "market_cutoff": "last_weekday_proxy_not_exchange_calendar",
        "future_source_accepted": False,
    }


def agent_3_coverage(data):
    """Source observability percentages, not the proportion of certified index."""
    out = {}
    for mode, series in data["series"].items():
        total = 0
        months_with_8 = 0
        for row in series:
            known = row["node_scores"]
            missing = row["missing_nodes"]
            if (set(known).intersection(missing)
                    or set(known).union(missing) != set(WEIGHTS)
                    or len(known) != row["known_node_count"]):
                raise ValueError("Duplicate/missing node in monthly panel")
            weight = sum(WEIGHTS[k] for k in known)
            if weight != row["known_weight"] or weight + sum(WEIGHTS[k] for k in missing) != 1050:
                raise ValueError("Weighted coverage arithmetic invalid")
            total += weight
            months_with_8 += len(known) >= 8
        expected = ("calendar_source_weight_months" if mode == "calendar"
                    else "market_weekday_proxy_source_weight_months")
        if total != data["v18"][expected]:
            raise ValueError("Persisted V18 weighted month summary changed")
        out[mode] = {
            "observed_weight_months": total,
            "possible_weight_months": 24 * 1050,
            "research_observability_pct": pct(total),
            "months_8_or_more_nodes": months_with_8,
            "latest_known_nodes": series[-1]["known_node_count"],
            "latest_known_weight": series[-1]["known_weight"],
            "latest_missing_nodes": list(series[-1]["missing_nodes"]),
        }
    return out


def agent_4_freshness(data):
    """Age in calendar days since first research visibility; no data-imputation."""
    scenarios = {}
    for mode, rows in data["series"].items():
        scenarios[mode] = {}
        for max_age in (60, 90, 120):
            accepted_weight_months = 0
            stale_months = []
            latest_stale = []
            for row in rows:
                cutoff = dt.date.fromisoformat(row["cutoff_date"])
                rejected = []
                for node, observation in row["node_scores"].items():
                    observed = dt.date.fromisoformat(observation["research_eligible_date"])
                    age = (cutoff - observed).days
                    if age > max_age:
                        rejected.append({"node": node, "age_days": age, "weight": WEIGHTS[node]})
                    else:
                        accepted_weight_months += WEIGHTS[node]
                if rejected:
                    stale_months.append(row["month"])
                if row is rows[-1]:
                    latest_stale = rejected
            scenarios[mode][str(max_age)] = {
                "valid_weight_months": accepted_weight_months,
                "research_fresh_coverage_pct": pct(accepted_weight_months),
                "months_with_any_stale": len(stale_months),
                "stale_latest": latest_stale,
            }
    return scenarios


def _components(month):
    result = {}
    for node, item in month["node_scores"].items():
        result[node] = dec(WEIGHTS[node]) * dec(item["score"]) / dec(100)
    return result


def agent_5_arithmetic(data):
    """Reconcile exact individual node contributions with V18 stored partial."""
    out = {}
    for mode, rows in data["series"].items():
        max_delta = dec(0)
        for row in rows:
            comp = _components(row)
            raw = sum(comp.values(), dec(0))
            expected = round2(raw) if comp else None
            if row["partial_weighted_points_not_full_aics"] != expected:
                raise ValueError("Partial weighted-point arithmetic broken")
            stored = dec(expected) if expected is not None else dec(0)
            max_delta = max(max_delta, abs(raw - stored))
        out[mode] = {"reconciled_months": len(rows),
                     "maximum_quantization_error_points": round2(max_delta),
                     "full_aics": None}
    return out


def agent_6_attribution(data):
    """Latest source-defined observed partial contributions, not total AICS."""
    out = {}
    for mode, rows in data["series"].items():
        latest = rows[-1]
        contributions = _components(latest)
        ranks = sorted(contributions, key=lambda n: (-contributions[n], n))
        out[mode] = {
            "month": latest["month"],
            "partial_research_sum": latest["partial_weighted_points_not_full_aics"],
            "known_nodes": len(contributions),
            "top_observed_contributors": [{
                "node": node, "score": latest["node_scores"][node]["score"],
                "weight": WEIGHTS[node], "contribution_points": round2(contributions[node]),
            } for node in ranks[:5]],
            "unknown_node_values_not_assumed": latest["missing_nodes"],
        }
    return out


def agent_7_sensitivity(data):
    """Bounds and +/-10pt measured-node what-ifs; never fill absent nodes."""
    out = {}
    for mode, rows in data["series"].items():
        scenarios = []
        for row in rows:
            comp = _components(row)
            lower = sum(comp.values(), dec(0))
            unseen = sum(WEIGHTS[k] for k in row["missing_nodes"])
            upper = lower + dec(unseen)
            if upper > dec(1050) or lower < 0:
                raise ValueError("Invalid arithmetic bounds")
            scenarios.append({
                "month": row["month"],
                "lower_arithmetic_if_missing_zero_NOT_OBSERVED": round2(lower),
                "upper_arithmetic_if_missing_100_NOT_OBSERVED": round2(upper),
                "missing_node_weight": unseen,
            })
        latest = rows[-1]
        variations = []
        for node, datum in latest["node_scores"].items():
            score = dec(datum["score"])
            up = min(dec(100), score + dec(10))
            down = max(dec(0), score - dec(10))
            variations.append({
                "node": node, "measured_score": str(score),
                "hypothetical_up_delta_known_points": round2(dec(WEIGHTS[node])*(up-score)/100),
                "hypothetical_down_delta_known_points": round2(dec(WEIGHTS[node])*(down-score)/100),
            })
        out[mode] = {
            "last_month": latest["month"], "latest_math_bounds": scenarios[-1],
            "bounds_months": len(scenarios),
            "hypothetical_unobserved_10pt_single_node_score_changes": variations,
            "scenario_is_actual_prediction": False,
            "model_multiplier_applied": False,
        }
    return out


def agent_8_spx(data):
    """S&P observed month-end close and returns, never an invented AICS spread."""
    pts = data["sp500"]["points"]
    prices = []
    for p in pts:
        value = dec(p["sp500_month_end_close"])
        if value <= 0:
            raise ValueError("S&P close must be a real positive price index")
        prices.append(value)
    changes = [round2(100*(prices[i]/prices[i-1]-1)) for i in range(1,len(prices))]
    # Merely describe counts where the same set of research nodes are visible.
    consecutive_same_constituents = {}
    for mode, rows in data["series"].items():
        consecutive_same_constituents[mode] = sum(
            set(rows[i]["node_scores"]) == set(rows[i-1]["node_scores"])
            for i in range(1, len(rows)))
    return {
        "source_observations": 24, "market_return_observations": 23,
        "first_month": pts[0]["month"], "last_month": pts[-1]["month"],
        "first_close": str(prices[0]), "last_close": str(prices[-1]),
        "cumulative_market_return_pct": round2(100*(prices[-1]/prices[0]-1)),
        "observed_monthly_sp500_returns_pct": [
            {"month": pts[i]["month"], "return_pct": changes[i-1]}
            for i in range(1,len(pts))],
        "same_node_roster_adjacent_month_pairs": consecutive_same_constituents,
        "aics_sp500_normalized_spread": None,
        "forecasting_skill": None,
    }


def agent_9_anomaly(data, as_of):
    """Reuse existing causal unsupervised learner; no return prediction."""
    result = online_learn(observed_events(data["v17"], data["v18"]),
                          as_of=as_of)
    if (result["complete_11_node_index"] is not None
            or result["predictive_accuracy"] is not None
            or result["trades_created"] is not False
            or result["aics_weights_changed"] is not False
            or result["source_delivery_historically_pit_attested"] is not False):
        raise ValueError("Anomaly detection attempted score/predictive promotion")
    return {
        "source_eligible_events": result["research_events_evaluated"],
        "causal_training_eligible_events": result["events_with_trainable_history"],
        "research_attention_flags": result["research_attention_events"],
        "alerts": result["alerts"],
        "trained_event_counts_per_node": result["learned_prior_node_event_counts"],
        "supervised_market_prediction": None,
        "historical_oos_performance": None,
    }


def agent_10_governance(data, prior, as_of):
    """Summarize conditions for committee research; no self-approval."""
    if len(prior) != 9 or any(a["status"] != "research_pass" for a in prior):
        raise ValueError("Missing or failed upstream AICS analysis agents")
    collector = data["capture"]
    source_status = None if collector is None else {
        "source_archives": collector["original_sources_archived"],
        "source_tasks": collector["unique_publisher_sources"],
        "all_sources_captured": collector["original_sources_archived"] == 20,
        "missing_source_ids": [
            x["source_id"] for x in collector["sources"]
            if x["status"] != "archived_current_original_not_pit"],
    }
    return {
        "as_of_utc_date": as_of.isoformat(),
        "analyst_agents_prior_passed": len(prior),
        "source_collectors": source_status,
        "research_panel_is_incomplete": True,
        "full_11node_index_months": 0,
        "certified_historical_pit_node_count": 0,
        "independent_untouched_24m_oos": False,
        "committee_release": "RESEARCH_ONLY_UNCERTIFIED",
        "production_promotion": "BLOCKED",
        "scoring_weights_mutated": False, "trades_created": False,
        "pending": [
            "Original public timestamps and independent delivery receipts",
            "Original AI Equities historical universe and split chronology",
            "Updated primary issuer numeric statement parsing",
            "Official trading sessions and market-release-time alignment",
            "Out-of-sample validation using prior-frozen scoring formulas",
        ],
    }


def run_agents(*, v17, v18, sp500, captured=None, as_of=None):
    """One analysis cycle, with fixed order and explicit previous-agent gates."""
    as_of = _asof(as_of or dt.datetime.now(dt.timezone.utc).date())
    data = _data(v17, v18, sp500, captured)
    agents = []
    operations = [
        agent_1_lineage,
        lambda d: agent_2_chronology(d, as_of),
        agent_3_coverage, agent_4_freshness,
        agent_5_arithmetic, agent_6_attribution,
        agent_7_sensitivity, agent_8_spx,
        lambda d: agent_9_anomaly(d, as_of),
    ]
    for name, fn in zip(AGENT_NAMES[:9], operations):
        payload = fn(data)
        agents.append({
            "name": name, "status": "research_pass",
            "result": payload, "trades_created": False,
            "model_weight_change": False,
        })
    governance = agent_10_governance(data, agents, as_of)
    agents.append({
        "name": AGENT_NAMES[9], "status": "research_pass",
        "result": governance, "trades_created": False,
        "model_weight_change": False,
    })
    if len(agents) != 10 or [a["name"] for a in agents] != list(AGENT_NAMES):
        raise ValueError("Wrong AICS analysis agent sequence")
    return {
        "schema": "aics-v21-ten-analysis-agents-research-cycle-v1",
        "as_of": as_of.isoformat(), "agents_count": 10,
        "results": agents, "source_agents_count": 10 if captured is not None else None,
        "actual_source_bytes_in_this_run": (
            captured["original_sources_archived"] if captured is not None else None),
        "complete_aics_index": None, "aics_sp500_spread": None,
        "certified_pit": False, "validated_market_predictive_skill": False,
        "production_model_updated": False, "trades_created": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUTPUT)
    p.add_argument("--source-manifest", type=Path, default=CAPTURE)
    args = p.parse_args()
    captured = read(args.source_manifest) if args.source_manifest.exists() else None
    result = run_agents(
        v17=read(V17), v18=read(V18), sp500=read(SPX),
        captured=captured)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n",
                        encoding="utf-8")
    print(json.dumps({
        "analysis_agents": 10, "source_agents": result["source_agents_count"],
        "source_archives": result["actual_source_bytes_in_this_run"],
        "calendar_observability_pct": result["results"][2]["result"]["calendar"]["research_observability_pct"],
        "market_observability_pct": result["results"][2]["result"]["market"]["research_observability_pct"],
        "research_anomalies": result["results"][8]["result"]["research_attention_flags"],
        "full_aics": None, "trades_created": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
