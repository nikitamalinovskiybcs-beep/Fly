"""AICS V60: recover original observed UST30 24m research, test two scores.

No original model is silently redefined. FRED/ALFRED DGS30 and
20-day Treasury yield-change volatility are genuine retrospectively observed
source values, but the mapping below is a NEW, post-hoc research hypothesis.
It is NOT the approved official UST 30Y 0-100 score, NOT source first-delivery
PIT certified, and NOT an out-of-sample predictive backtest.

Two fixed research alternatives demonstrate model-definition uncertainty:
(1) VOL10: 100 * 20 daily bp-change sample stdev / 10 bp, clipped 0-100
(2) VOL_PLUS_RISE: average(VOL10, 100 * positive month-end DGS30
    change in bp / 50 bp, clipped 0-100); no first-month change invented.

Their 24-month conditional interval examples resolve UST only HYPOTHETICALLY.
The remaining missing nodes are left as [0,100] in proof, never fabricated.
All official AICS indices, readiness, trades and first-delivery PIT stay null.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS
from scripts.aics_v59_24m_uncertainty_envelope import build as base_v59, multiplier

SOURCE_V18=Path("aics_data/research/aics_v18_private_credit_24m_pit_proxy_overlay_2026-11-22.json")
SOURCE_DGS30=Path("aics_data/research/ust30_24_month_public_observed_panel_2026-11-18.json")
SOURCE_VOL=Path("aics_data/research/ust30_yield_change_volatility_2024_2026.json")
OUT=Path("aics_data/research/aics_v60_ust30_two_research_score_hypotheses_24m_2026-11-22.json")
D=Decimal
W=WEIGHTS["UST 30Y"]
EXP_SHA={
    str(SOURCE_DGS30):"586f6112a66597f53a20f34c1d71a172a0c254454d5eed2010ccd99a882e047d",
    str(SOURCE_VOL):"7c6a095d1f4154fe50f9d04d0665c4b40c85f3e4859cf0c54b5867e686e34590",
}
assert W==125 and sum(WEIGHTS.values())==1050 and len(WEIGHTS)==11


def _positive(raw):
    try:
        v=D(str(raw))
    except (InvalidOperation,TypeError,ValueError) as exc:
        raise ValueError("Original Treasury source must have genuine numeric rate") from exc
    if not v.is_finite() or v<0 or v>D("1000"):
        raise ValueError("Out-of-range Treasury source metric")
    return v


def _pct(raw):
    v=_positive(raw)
    if v>D("30"):
        raise ValueError("Physically suspicious Treasury yield")
    return v


def _capped(v):
    return max(D(0),min(D(100),v))


def _fmt(v):
    return float(v.quantize(D("0.01"),rounding=ROUND_HALF_UP))


def _bounds_from_assumption(base,shadow):
    """Conditional bound if a future research group APPROVED one UST formula.

    Research-only what-if, does not modify the original missing-node status.
    """
    if not D(0)<=shadow<=D(100):
        raise ValueError("Hypothetical score outside 0-100")
    if "UST 30Y" not in base["missing_nodes_not_imputed"]:
        raise ValueError("UST already officially scored in original source")
    rest=[name for name in base["missing_nodes_not_imputed"] if name!="UST 30Y"]
    missing_weight=sum(WEIGHTS[name] for name in rest)
    actual_known=D(base["observed_partial_weighted_sum_exact"])
    assumed_raw=actual_known+D(W)*shadow/D(100)
    h=base["known_hot_nodes_strict_gt_60"]+int(shadow>D(60))
    low=assumed_raw*multiplier(h)
    upper=(assumed_raw+D(missing_weight))*multiplier(h+len(rest))
    if not low<=upper:
        raise ValueError("AICS candidate interval not ordered")
    return {
        "research_assumed_UST30_node_score_NOT_OFFICIAL":_fmt(shadow),
        "remaining_unobserved_original_nodes":rest,
        "remaining_unknown_weight":missing_weight,
        "lower_conditional_research_AICS_NOT_CERTIFIED":_fmt(low),
        "upper_conditional_research_AICS_NOT_CERTIFIED":_fmt(upper),
        "width_conditional_research_AICS_NOT_CERTIFIED":_fmt(upper-low),
        "still_includes_below_450_and_above_500":bool(low<D(450) and upper>D(500)),
        "official_AICS":None,
        "no_approved_11node_score":True,
    }


def build(overlay,panel,volatility,*,actual_sha=None):
    if (panel.get("schema_version")!="aics-ust30-24-month-durable-public-metrics-v1"
        or panel.get("observed_public_months")!=24
        or panel.get("independent_provider_historical_release_proven") is not False
        or panel.get("untouched_24_month_oos_proven") is not False
        or panel.get("stress_scores",{}).get("UST 30Y") is not None
        or panel.get("index_aics") is not None
        or panel.get("promotion")!="BLOCKED"
        or volatility.get("series")!="DGS30"
        or volatility.get("node_score") is not None
        or volatility.get("index_aics") is not None
        or volatility.get("untouched_oos") is not False
        or volatility.get("alfred_archive_sha256")!=panel.get("original_csv_zip_sha256")
        or volatility.get("matched_date_value_pairs_across_windows")!=504
        or len(WEIGHTS)!=11 or sum(WEIGHTS.values())!=1050):
        raise ValueError("Only original unscored research history may be used")
    if actual_sha is not None:
        for path,expected in EXP_SHA.items():
            if actual_sha.get(path)!=expected:
                raise ValueError("External independently rehashed Treasury research source SHA changed")
    prior=base_v59(overlay)
    original=prior["monthly_24m_conditional_research_envelopes"]
    yields=panel.get("public_series_observations")
    vols=volatility.get("months")
    if not isinstance(yields,list) or not isinstance(vols,list) or len(yields)!=24 or len(vols)!=24:
        raise ValueError("Do not guess unavailable DGS30 yield and volatility months")
    rows=[]
    old_rate=None
    for base,obsv,vol in zip(original,yields,vols):
        month=base["month"]
        exact_cutoff=dt.date.fromisoformat(base["cutoff_date"])
        if (obsv.get("as_of_month_end")[:7]!=month or
            vol.get("as_of")[:7]!=month or
            vol["as_of"]!=obsv["as_of_month_end"] or
            vol["last_yield_date"]!=obsv["dgs30_observation_date"]):
            raise ValueError("ALFRED yield and Treasury realized volatility date mismatch")
        date=dt.date.fromisoformat(obsv["dgs30_observation_date"])
        if date>=exact_cutoff:
            raise ValueError("Same-day UST publication is NOT proven prior to US market close")
        if (exact_cutoff-date).days>7:
            raise ValueError("UST vintage source is stale or unavailable")
        yieldpct=_pct(obsv["dgs30_pct"])
        sofrpct=_pct(obsv["sofr_pct"])
        original_spread=D(str(obsv["dgs30_minus_sofr_bps"]))
        if (yieldpct-sofrpct)*D(100)!=original_spread:
            raise ValueError("Observed DGS30 minus SOFR arithmetic mismatch")
        volbp=_positive(vol["sample_sd_daily_change_bp"])
        # Two researcher-invented scoring functions, NOT missing observations.
        volscore=_capped(volbp*D(100)/D(10))
        monthly_change=(yieldpct-old_rate)*D(100) if old_rate is not None else None
        risescore=(_capped(max(monthly_change,D(0))*D(100)/D(50))
                   if monthly_change is not None else None)
        blend=(volscore+risescore)/D(2) if risescore is not None else None
        row={
            "month":month,
            "market_cutoff":base["cutoff_date"],
            "last_observed_original_DGS30_date":date.isoformat(),
            "original_ALFRED_DGS30_yield_percent":str(yieldpct),
            "original_ALFRED_SOFR_percent":str(sofrpct),
            "original_DGS30_minus_SOFR_bp_NOT_term_premium":str(original_spread),
            "source_verified_20_daily_change_sd_bp":str(volbp),
            "observed_month_over_month_DGS30_rise_bp":(
                str(monthly_change) if monthly_change is not None else None),
            "candidate_Vol10_risk_proxy_0_100_NOT_OFFICIAL":_fmt(volscore),
            "candidate_VolPlusRise_risk_proxy_0_100_NOT_OFFICIAL":(
                _fmt(blend) if blend is not None else None),
            "conditional_if_shadows_replaced_missing_UST":{
                "Vol10":_bounds_from_assumption(base,volscore),
                "VolPlusRise":_bounds_from_assumption(base,blend) if blend is not None else None,
            },
            "original_unscored_UST_30Y_remains_missing":True,
            "independent_provider_first_delivery_PIT_attested":False,
            "official_11node_AICS":None,
            "official_regime":None,
        }
        if row["conditional_if_shadows_replaced_missing_UST"]["Vol10"]["width_conditional_research_AICS_NOT_CERTIFIED"]>=base["conditional_interval_width"]:
            raise ValueError("Resolving an assumed node should shrink, not widen, interval")
        rows.append(row)
        old_rate=yieldpct
    if rows[0]["observed_month_over_month_DGS30_rise_bp"] is not None:
        raise ValueError("First-month 2024 rate change was filled from thin air")
    if [x["month"] for x in rows]!=[x["month"] for x in original]:
        raise ValueError("Prospective observation dates shifted")
    scenarios={
        name:sum(r["conditional_if_shadows_replaced_missing_UST"][name] is not None
                 and not r["conditional_if_shadows_replaced_missing_UST"][name][
                     "still_includes_below_450_and_above_500"] for r in rows)
        for name in ("Vol10","VolPlusRise")
    }
    return {
        "schema":"aics-v60-existing-real-24m-UST30-vintages-two-POSTHOC-shadow-normalizations-v1",
        "as_of":"2026-11-22",
        "research_source_months":24,
        "original_DGS30_and_SOFR_24m_source_dates_matched":True,
        "original_Treasury_volatility_20_daily_returns_observed_months":24,
        "original_sources_are_2026_retrieval_of_older_ALFRED_vintages":True,
        "historically_original_publisher_delivery_PIT_proven":False,
        "frozen_original_UST30_node_score_method_found_and_certified":False,
        "shadow_formula_Vol10":"clip(100*20-daily-change-SD-bp/10,0,100) ; POSTHOC hypothesis, NOT official",
        "shadow_formula_VolPlusRise":"0.5*Vol10+0.5*clip(100*max(DGS30_mom_change_bp,0)/50,0,100); POSTHOC hypothesis",
        "normalization_10bp_and_50bp_thresholds_NOT_trained_or_preregistered":True,
        "month_count_with_VolPlusRise_hypothesis":23,
        "hypothesis_scenarios_with_conclusive_trading_regime_in_24m":scenarios,
        "prior_V59_conditional_Oct_2026":[322.06,801.07],
        "Oct_2026_last_observed_actual_yield_pct":rows[-1]["original_ALFRED_DGS30_yield_percent"],
        "Oct_2026_last_observed_original_vol_bp":rows[-1]["source_verified_20_daily_change_sd_bp"],
        "Oct_2026_hypothesis_intervals":rows[-1]["conditional_if_shadows_replaced_missing_UST"],
        "historical_full_11node_AICS":None,
        "independently_certified_AICS_nodes":0,
        "all_11_weights_total":1050,
        "readiness_22_of_66_unchanged":True,
        "production_signal_or_trade":None,
        "correct_next_decision":"UST historical observations already exist; seek an independently justified source-to-UST0-100 scoring specification and source first-delivery receipts, NOT more ungrounded curve fits.",
        "observed_months_and_hypothetical_score_stress_tests":rows,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,default=OUT)
    args=p.parse_args()
    paths=(SOURCE_V18,SOURCE_DGS30,SOURCE_VOL)
    raw={str(p):p.read_bytes() for p in paths}
    sha={name:hashlib.sha256(contents).hexdigest() for name,contents in raw.items()}
    inputs=[json.loads(raw[str(p)]) for p in paths]
    report=build(*inputs,actual_sha=sha)
    report["actual_input_sha256"]=sha
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in (
        "observed_months_and_hypothetical_score_stress_tests",)},ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
