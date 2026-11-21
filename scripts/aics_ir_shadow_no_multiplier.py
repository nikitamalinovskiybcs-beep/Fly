"""No-multiplier IR shadow AICS for 20-Nov-2026; experimental, not PIT-certified.

Runs from the repository root. All weights remain fixed (total 1050).
Uses only official issuer Q3 IR cash-flow tables for the updated Neoclouds
proxy. The other ten nodes retain explicitly older research inputs.
"""
import json
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path

from scripts.aics_close_20261120 import calculate as close_calculate
from scripts.aics_score_reproducibility_gate import WEIGHTS

RECORD = Path("aics_data/research/aics_2026_11_20_ir_shadow_no_multiplier.json")
RELEASE = Path("aics_data/progress/research_release_2026-11-19.json")
Q = Decimal("0.01")
IR_ORIGINALS = {
    "CoreWeave": "https://investors.coreweave.com/news/news-details/2026/CoreWeave-Reports-Strong-Third-Quarter-2026-Results/",
    "Nebius": "https://assets.nebius.com/assets/e2ac679c-fc62-4799-ba0e-6611e59c6863/Nebius-2026-Q3.pdf",
}


def decimal(value):
    try:
        x = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid source numeric operand") from exc
    if not x.is_finite():
        raise ValueError("Non-finite source operand")
    return x


def hundred(x):
    return min(Decimal(100), max(Decimal(0), x))


def calc(record=None, release=None, close=None):
    record = record if record is not None else json.loads(RECORD.read_text(encoding="utf-8"))
    release = release if release is not None else json.loads(RELEASE.read_text(encoding="utf-8"))
    close = close if close is not None else close_calculate()
    if (record.get("schema") != "aics-research-no-multiplier-ir-shadow-v1"
            or record.get("date_cutoff") != "2026-11-20"
            or record.get("official_production_formula_changed") is not False
            or record.get("base_release") != str(RELEASE)
            or record.get("model_status") != "EXPLORATORY_IR_SHADOW_NOT_PIT_OR_OOS_CERTIFIED"
            or record.get("research_method") != "SUM_NODE_WEIGHTS_TIMES_SCORES_OVER_100_NO_HOT_NODE_MULTIPLIER"
            or record.get("equity_close_record") != "aics_data/research/aics_2026_11_20_close_research_rollover.json"):
        raise ValueError("Invalid research-only scenario identifiers")
    safeguards = record["guardrails"]
    if (safeguards.get("independent_ir_raw_rehash_attested") is not False
            or safeguards.get("complete_24_month_oos_attested") is not False
            or safeguards.get("historical_entry_watch_exit_thresholds_recalibrated") is not False
            or safeguards.get("trades_created") is not False
            or safeguards.get("original_non_equity_data_asof") != "2026-11-18"):
        raise ValueError("IR scenario improperly promoted to certified PIT model")
    if (len(record["q3_inputs"]) != 2 or
            {r["issuer"] for r in record["q3_inputs"]} != set(IR_ORIGINALS)):
        raise ValueError("Incomplete two-issuer Q3 IR panel")
    cfo = Decimal(0)
    purchases = Decimal(0)
    for row in record["q3_inputs"]:
        issuer = row["issuer"]
        if (row["source_url"] != IR_ORIGINALS[issuer]
                or row["source_raw_sha256"] is not None
                or row["reported_q3_2026"] is not True
                or row["cash_purchases_scope"] !=
                ("Purchases of property and equipment including capitalized internal-use software"
                 if issuer == "CoreWeave" else
                 "Purchases of property and equipment and intangible assets")):
            raise ValueError("Unapproved issuer source or capital-purchase scope")
        o, p = decimal(row["operating_cash_flow"]), decimal(row["cash_purchases"])
        if p <= 0:
            raise ValueError("Missing positive cash purchases")
        cfo += o
        purchases += p
    if (close.get("session") != "2026-11-20"
            or close.get("declining_securities") != 7
            or close.get("research_aics") != "669.09"
            or close.get("certified_aics") is not None):
        raise ValueError("Invalid current-session equity replay")
    scores = {r["node"]: decimal(r["score"]) for r in close["nodes"]}
    released = {k: decimal(v) for k, v in release["first_publication"]["scores"].items()}
    if (scores.keys() != WEIGHTS.keys() or released.keys() != WEIGHTS.keys()
            or sum(WEIGHTS.values()) != 1050 or scores != released):
        raise ValueError("Not the original fixed-weight research release")
    before = sum((decimal(WEIGHTS[n]) * scores[n] / 100 for n in WEIGHTS), Decimal(0))
    new_neo = hundred(100 * (1 - cfo / purchases)).quantize(Q, rounding=ROUND_HALF_UP)
    previous_neo = scores["Neoclouds"]
    scores["Neoclouds"] = new_neo
    after = sum((decimal(WEIGHTS[n]) * scores[n] / 100 for n in WEIGHTS), Decimal(0))
    h = sum(s > 60 for s in scores.values())
    legacy_multiplier = min(Decimal("1.35"),
        1 + Decimal("0.20") * min(1, max(0, h-2)) + Decimal("0.05") * max(0, h-3))
    expected = record["expected"]
    actual = {
        "q3_cfo_total":str(cfo),
        "q3_cash_purchases_total":str(purchases),
        "q3_neocloud_score":str(new_neo),
        "q2_neocloud_score":str(previous_neo),
        "raw_no_multiplier_prior":str(before),
        "raw_no_multiplier_ir_shadow":str(after.quantize(Q, rounding=ROUND_HALF_UP)),
        "change_without_multiplier":f"{after-before:+.2f}",
        "legacy_multiplicative_ir_shadow_for_comparison":str(
            (after * legacy_multiplier).quantize(Q, rounding=ROUND_HALF_UP)),
        "certified_aics":None,
    }
    if actual != expected:
        raise ValueError("Shadow AICS original-source operands / expected ledger mismatched")
    return {
        "as_of":record["date_cutoff"],
        "method":"NO_MULTIPLIER",
        "weights_sum":1050,
        "scores":{k:str(v) for k,v in scores.items()},
        "hot_nodes":h,
        "q3_cfo_m":str(cfo),
        "q3_cash_purchases_m":str(purchases),
        "neoclouds_before":str(previous_neo),
        "neoclouds_ir_scenario":str(new_neo),
        "research_no_multiplier_prior":str(before.quantize(Q, rounding=ROUND_HALF_UP)),
        "research_no_multiplier_shadow":actual["raw_no_multiplier_ir_shadow"],
        "research_change":actual["change_without_multiplier"],
        "legacy_multiplier_diagnostic_only":str(legacy_multiplier),
        "legacy_research_shadow_diagnostic_only":actual["legacy_multiplicative_ir_shadow_for_comparison"],
        "old_450_500_thresholds_valid_for_no_m":False,
        "certified_aics":None,
        "source_status":"IR scenario, unarchived raw originals, ten older research inputs",
        "trades_created":False,
    }


if __name__=="__main__":
    print(json.dumps(calc(),indent=2,ensure_ascii=False))
