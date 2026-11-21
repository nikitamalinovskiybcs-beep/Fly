#!/usr/bin/env python3
"""Reconcile 24 genuine archival month-ends across UST 30Y and Repo.

Descriptive co-occurrences are NOT independently attested point-in-time model
inputs, an 11-node AICS score, a calibrated stress trigger, or untouched OOS.
Input data are obtained from separate original-source provenance/review chains.
The shared SOFR dates and values must match exactly, without interpolation.
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import hashlib
import json
from decimal import Decimal
from pathlib import Path

ROOT = Path("aics_data/research")
REPO_PATH = ROOT / "repo_24_month_observed_research_2026-11-18.json"
UST_PATH = ROOT / "ust30_24_month_public_observed_panel_2026-11-18.json"
VOL_PATH = ROOT / "ust30_yield_change_volatility_2024_2026.json"
REPORT_PATH = ROOT / "ust_repo_joint_observed_24_months_2026-11-19.json"


def _rows_by_date(rows: list, field: str, label: str) -> dict[str, dict]:
    if not isinstance(rows, list) or len(rows) != 24:
        raise ValueError("Incomplete " + label + " 24-month archive")
    by_date = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get(field), str):
            raise ValueError("Malformed " + label + " original month")
        day = row[field]
        if day in by_date:
            raise ValueError("Duplicate " + label + " month-end")
        by_date[day] = row
    expected = set()
    for i in range(24):
        y, m = divmod(2024 * 12 + 10 + i, 12)
        m += 1
        expected.add(dt.date(y, m, calendar.monthrange(y, m)[1]).isoformat())
    if set(by_date) != expected:
        raise ValueError("Unmatched historical monthly source periods: " + label)
    return by_date


def _basis_points(a, b) -> int:
    result = (Decimal(str(a)) - Decimal(str(b))) * 100
    if result != result.to_integral_value():
        raise ValueError("Unsupported fractional basis point or mislabeled data")
    return int(result)


def build(repo: dict, ust: dict, vol: dict, *, source_hashes: dict | None = None) -> dict:
    """Recalculate all 24 dates without looking ahead or inventing missing rows."""
    if (repo.get("schema_version") != "aics-repo-24-matched-source-observed-rates-v2"
            or repo.get("research_as_of") != "2026-11-18"
            or repo.get("fixed_node") != "Repo"
            or repo.get("fixed_node_weight") != 100
            or repo.get("observed_months") != 24
            or repo.get("missing_months") != 0
            or repo.get("synthetic_market_rows") != 0
            or repo.get("source_release_timestamp_pit_attested") is not False
            or repo.get("contemporaneous_alfred_snapshots_attested") is not False
            or repo.get("independent_24_month_oos") is not False
            or repo.get("index_aics") is not None or repo.get("stress_score") is not None
            or repo.get("promotion") != "BLOCKED"):
        raise ValueError("Repo original research source or historical caveat altered")
    if (ust.get("schema_version") != "aics-ust30-24-month-durable-public-metrics-v1"
            or ust.get("observed_public_months") != 24
            or ust.get("independent_provider_historical_release_proven") is not False
            or ust.get("untouched_24_month_oos_proven") is not False
            or ust.get("index_aics") is not None
            or ust.get("promotion") != "BLOCKED"):
        raise ValueError("UST original research source or historical caveat altered")
    if (vol.get("research_as_of") != "2026-11-18"
            or vol.get("series") != "DGS30"
            or vol.get("matched_date_value_pairs_across_windows") != 504
            or vol.get("node_score") is not None
            or vol.get("index_aics") is not None
            or vol.get("untouched_oos") is not False):
        raise ValueError("DGS30 real-vintage volatility identity/caveat altered")
    repo_rows = _rows_by_date(repo["monthly_observations"], "as_of", "repo")
    ust_rows = _rows_by_date(ust["public_series_observations"], "as_of_month_end", "UST")
    vol_rows = _rows_by_date(vol["months"], "as_of", "DGS30 daily volatility")
    dates = sorted(repo_rows)
    joined = []
    for day in dates:
        a, b, c = repo_rows[day], ust_rows[day], vol_rows[day]
        cutoff = dt.date.fromisoformat(day)
        obs = dt.date.fromisoformat(a["market_effective_date"])
        published = dt.date.fromisoformat(a["publication_proxy_date"])
        if (b["dgs30_observation_date"] != b["sofr_observation_date"]
                or b["sofr_observation_date"] != a["market_effective_date"]
                or not obs <= published <= cutoff
                or b["sofr_pct"] != a["sofr_pct"]
                or b["dgs30_pct"] is None):
            raise ValueError("Same-as-of SOFR dates/levels or publication proxy differ")
        if c["last_yield_date"] != b["dgs30_observation_date"]:
            raise ValueError("DGS30 volatility window ends at another observation")
        term_bp = _basis_points(b["dgs30_pct"], b["sofr_pct"])
        overnight_bp = _basis_points(a["sofr_pct"], a["iorb_pct"])
        bgcr_bp = _basis_points(a["sofr_pct"], a["bgcr_pct"])
        if (term_bp != int(Decimal(b["dgs30_minus_sofr_bps"]))
                or overnight_bp != a["sofr_minus_iorb_bps"]
                or bgcr_bp != a["sofr_minus_bgcr_bps"]
                or Decimal(a["tgcr_pct"]) > Decimal(a["bgcr_pct"])):
            raise ValueError("Cross-source spread calculation differs")
        sd = Decimal(c["sample_sd_daily_change_bp"])
        if not sd.is_finite() or sd < 0 or sd.as_tuple().exponent < -2:
            raise ValueError("Unreproducible rounded DGS30 volatility")
        joined.append({
            "month_end": day,
            "joint_source_observation_date": obs.isoformat(),
            "nyfed_publication_proxy_date_not_attested": published.isoformat(),
            "dgs30_pct": b["dgs30_pct"],
            "sofr_pct": b["sofr_pct"],
            "iorb_pct": a["iorb_pct"],
            "dgs30_minus_sofr_bp": term_bp,
            "sofr_minus_iorb_bp": overnight_bp,
            "sofr_minus_bgcr_bp": bgcr_bp,
            "dgs30_20_daily_changes_sample_sd_bp": str(sd),
        })
    # 100bp is a transparent retrospective comparison, NOT an AICS hot-score.
    high_term = [x["month_end"] for x in joined if x["dgs30_minus_sofr_bp"] > 100]
    overnight_above_iorb = [x["month_end"] for x in joined if x["sofr_minus_iorb_bp"] > 0]
    both = [x["month_end"] for x in joined if
            x["dgs30_minus_sofr_bp"] > 100 and x["sofr_minus_iorb_bp"] > 0]
    latest, prior = joined[-1], joined[-2]
    if both != ["2025-12-31", "2026-10-31"]:
        raise ValueError("The reproduced joint retrospective comparison changed")
    if (len(high_term), len(overnight_above_iorb)) != (10, 5):
        raise ValueError("Unexpected descriptive source distribution")
    return {
        "schema_version": "aics-ust30-repo-24-month-joint-descriptive-research-v1",
        "research_as_of": "2026-11-19",
        "observation_window": [dates[0], dates[-1]],
        "distinct_nodes": ["UST 30Y", "Repo"],
        "fixed_node_weights": {"UST 30Y": 125, "Repo": 100},
        "source_paths": [str(UST_PATH), str(REPO_PATH), str(VOL_PATH)],
        "source_sha256": source_hashes or {},
        "matched_distinct_month_ends": len(joined),
        "missing_joint_months": 0,
        "invented_or_interpolated_market_rows": 0,
        "method": "Exact same-month, same-day DGS30/SOFR, SOFR/IORB, SOFR/BGCR arithmetic; join pre-existing DGS30 20 daily yield-change sample SD (bp), without recalculating original vintages or adjusting prices.",
        "threshold_100bp_purpose": "ONLY ex-post descriptive count of term-versus-overnight yield difference; NOT fixed model threshold, calibrated risk score, or validated trading rule",
        "descriptive_counts": {
            "months_dgs30_minus_sofr_gt_100bp": len(high_term),
            "months_sofr_above_iorb": len(overnight_above_iorb),
            "months_both": len(both),
            "months_both_dates": both,
        },
        "last_month_delta_vs_prior": {
            "month_end": latest["month_end"],
            "previous_month_end": prior["month_end"],
            "dgs30_minus_sofr_bp_change": latest["dgs30_minus_sofr_bp"] - prior["dgs30_minus_sofr_bp"],
            "sofr_minus_iorb_bp_change": latest["sofr_minus_iorb_bp"] - prior["sofr_minus_iorb_bp"],
            "dgs30_20daily_sample_sd_bp_change": str(
                Decimal(latest["dgs30_20_daily_changes_sample_sd_bp"])
                - Decimal(prior["dgs30_20_daily_changes_sample_sd_bp"])),
        },
        "rows": joined,
        "publication_proxy_only_not_independent_provider_release_attestation": True,
        "all_24_months_used_for_descriptive_analysis_not_untouched_oos": True,
        "independent_historical_pit_attested": False,
        "licensed_ice_credit_series_included": False,
        "causal_stress_inference": False,
        "historical_model_predictive_skill": None,
        "model_node_scores": {"UST 30Y": None, "Repo": None},
        "index_aics": None,
        "promotion": "BLOCKED",
        "trades_created": False,
        "limitations": [
            "DGS30 minus SOFR is NOT a Treasury term premium; SOFR above IORB is NOT proof of repo-market crisis.",
            "Month-end publication proxy and retrospective ALFRED API vintage do not independently attest intraday historical release.",
            "All 24 month-ends have been examined for research, so they may not be relabeled untouched 24-month OOS.",
            "The >100bp comparison was chosen for this descriptive summary; it is NOT a pre-registered risk-model stress threshold.",
            "No calibrated AICS 0-100 node scoring, 1050-weight model index, loss estimate, or investment recommendation can be generated.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    try:
        paths = (REPO_PATH, UST_PATH, VOL_PATH)
        values = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
        hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in paths}
        report = build(*values, source_hashes=hashes)
    except (OSError, TypeError, KeyError, ValueError, ArithmeticError) as exc:
        print(json.dumps({"promotion": "BLOCKED", "error": type(exc).__name__}))
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps({
        "matched_real_months": report["matched_distinct_month_ends"],
        "joint_positive_and_gt100_months": report["descriptive_counts"]["months_both_dates"],
        "latest_term_minus_sofr_bp": report["rows"][-1]["dgs30_minus_sofr_bp"],
        "latest_sofr_minus_iorb_bp": report["rows"][-1]["sofr_minus_iorb_bp"],
        "index_aics": None, "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
