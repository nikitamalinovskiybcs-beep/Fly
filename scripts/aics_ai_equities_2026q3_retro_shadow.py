"""Replay three month-end Nasdaq 7-stock intraday-breadth shadow scenarios.

The optional raw archive is the independently SHA-256 checked original
GitHub Actions artifact from 2026-11-18. No Nasdaq raw redistribution or
backdating is approved. An Oct 2026 scenario conditional on a later-retrieved,
later-defined basket is NOT a historical as-of source-eligible AICS value.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import zipfile
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from scripts.aics_score_reproducibility_gate import WEIGHTS

RECORD = Path("aics_data/research/ai_equities_aug_oct_2026_retrospective_shadow_2026-11-21.json")
COVERAGE = Path("aics_data/research/aics_24_month_no_multiplier_coverage_2026-11-21.json")
ARCHIVE_RECEIPT = Path("aics_data/progress/ai_equities_nasdaq_raw_archive_receipt_2026-11-18.json")
SYMBOLS = ("NVDA", "MSFT", "GOOGL", "AMZN", "META", "ORCL", "MU")
DATES = {"2026-08": "2026-08-31", "2026-09": "2026-09-30", "2026-10": "2026-10-30"}
ZIP_HASH = "0354dea8f0507a770afc4dcfcbb7ce9d4ddf33539d774664b62fa1b04464e9b8"
Q = Decimal(".01")
Q4 = Decimal(".0001")


def p2(x):
    return str(x.quantize(Q, rounding=ROUND_HALF_UP))


def validate_receipt(data=None, coverage=None, receipt=None):
    data = data if data is not None else json.loads(RECORD.read_text(encoding="utf-8"))
    coverage = coverage if coverage is not None else json.loads(COVERAGE.read_text(encoding="utf-8"))
    receipt = receipt if receipt is not None else json.loads(ARCHIVE_RECEIPT.read_text(encoding="utf-8"))
    if (data.get("schema") != "aics-ai-equities-month-end-2026q3-retrospective-shadow-v1"
            or data.get("node") != "AI Equities"
            or data.get("node_weight") != 100
            or tuple(data.get("research_symbols",[])) != SYMBOLS
            or sum(WEIGHTS.values()) != 1050
            or data.get("approved_historical_constituency") is not False
            or data.get("original_provider_historical_vintages_attested") is not False
            or data.get("corporate_actions_complete_original_timeline_attested") is not False
            or data.get("original_score_coverage_panel_promotion") is not False
            or data.get("independent_historical_pit_24m") is not False
            or data.get("certified_aics") is not None
            or data.get("historical_aics_sp500_spread") is not None
            or data.get("hist_24_month_full_index") is not None
            or data.get("trades_created") is not False):
        raise ValueError("Retrospective research scenario improperly promoted")
    source = data["original_archive"]
    if (source.get("zip_sha256") != ZIP_HASH
            or source.get("artifact_id") != 14466941540
            or source.get("original_rows_total") != 441
            or source.get("capture_utc") != "2026-11-18T20:04:42.909182+00:00"
            or receipt.get("artifact_zip_sha256") != ZIP_HASH
            or receipt.get("artifact_id") != 14466941540
            or receipt["independent_recalculation"].get("validated_original_rows") != 441
            or receipt["independent_recalculation"].get("historical_pit_verified") is not False):
        raise ValueError("Original 2026 Nasdaq 441-row source archive receipt mismatch")
    raw_sha = source["original_json_sha256"]
    if set(raw_sha) != set(SYMBOLS):
        raise ValueError("Missing or extraneous 7-name raw source hashes")
    original_sources = {s["symbol"]: s for s in receipt["original_files"]}
    if set(original_sources) != set(SYMBOLS):
        raise ValueError("Original issuer coverage incomplete")
    for sym in SYMBOLS:
        if (not re.fullmatch(r"[0-9a-f]{64}",raw_sha[sym])
                or raw_sha[sym] != original_sources[sym]["raw_json_sha256"]
                or original_sources[sym]["rows"] != 63):
            raise ValueError("Nasdaq source hash or 63-row sample mismatch")
    months = coverage["monthly"]
    historic = {r["month"]:r for r in months}
    if len(months) != 24 or coverage["new_11_node_full_aics_months"] != 0:
        raise ValueError("Complete AICS history wrongfully promoted")
    rows = data["observations"]
    if len(rows) != 3 or [row["month"] for row in rows] != list(DATES):
        raise ValueError("Only three observed month-end sessions can be replayed")
    results = []
    for row in rows:
        m = row["month"]
        if row.get("last_trading_session") != DATES[m]:
            raise ValueError("Unverified last market session")
        if dt.date.fromisoformat(DATES[m]) >= dt.date.fromisoformat(source["capture_utc"][:10]):
            raise ValueError("Not a later-fetched retrospective observation")
        decliners = row["decliners"]
        if (len(decliners) != len(set(decliners))
                or any(x not in SYMBOLS for x in decliners)
                or not 0 <= len(decliners) <= 7):
            raise ValueError("Decliner data invalid")
        shadow_score = p2(Decimal(len(decliners))*100/7)
        if row.get("score") != shadow_score:
            raise ValueError("Breadth score differs from observed 7-name decliner count")
        a = historic[m]
        if (a["known_node_count_research_only"] != row.get("other_known_node_count")
                or a["partial_known_weighted_points_not_aics"] != row.get("other_known_points")
                or "AI Equities" not in a["missing_nodes"]
                or a["full_11_node_aics_no_multiplier"] is not None
                or a["aics_sp500_normalized_spread"] is not None):
            raise ValueError("Independent source-gated AICS monthly coverage mutated")
        total = p2(Decimal(row["other_known_points"]) + Decimal(shadow_score))
        if (row.get("conditional_known_plus_equity") != total
                or row.get("conditional_complete_11_node_scenario") !=
                    (total if row["other_known_node_count"] == 10 else None)):
            raise ValueError("Incorrect conditional scenario, not a genuine AICS value")
        results.append({
            "month":m, "session":DATES[m],"decliners":decliners,
            "score":shadow_score,
            "other_dated_research_nodes":a["known_node_count_research_only"],
            "conditional_research_score":total,
            "is_conditional_11_node_scenario":row["other_known_node_count"] == 10,
            "eligible_original_month_pit":False,
            "actual_historical_aics":None,
            "actual_historical_spread_vs_sp500":None
        })
    return results


def validate_original_zip(archive, data=None):
    """Require actual original files, not solely the derivative month-end receipt."""
    data = data if data is not None else json.loads(RECORD.read_text(encoding="utf-8"))
    if hashlib.sha256(Path(archive).read_bytes()).hexdigest() != ZIP_HASH:
        raise ValueError("Original Nasdaq ZIP SHA256 mismatch")
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError("Corrupt original Nasdaq ZIP CRC")
        manifest = json.loads(z.read("manifest.json"))
        if (manifest["schema_version"] != "aics-ai-equities-price-capture-v1"
                or manifest["retrieved_at_utc"] != data["original_archive"]["capture_utc"]
                or manifest["archive_candidates"] != 7):
            raise ValueError("Wrong original Nasdaq manifest")
        original_names = [n for n in z.namelist() if n.startswith("raw/") and n.endswith(".json")]
        if len(original_names) != 7:
            raise ValueError("Expected exactly seven raw original Nasdaq JSON files")
        sessions = {m:{} for m in DATES}
        seen = set()
        for filename in original_names:
            body = z.read(filename)
            raw = json.loads(body)
            sym = raw["data"]["symbol"]
            if sym in seen or sym not in SYMBOLS:
                raise ValueError("Invalid or duplicated security in Nasdaq source")
            seen.add(sym)
            if hashlib.sha256(body).hexdigest() != data["original_archive"]["original_json_sha256"][sym]:
                raise ValueError("Original raw Nasdaq JSON hash mismatch")
            all_rows = raw["data"]["tradesTable"]["rows"]
            if len(all_rows) != 63:
                raise ValueError("Unapproved original Nasdaq history length")
            for month, date in DATES.items():
                matching = [x for x in all_rows
                            if dt.datetime.strptime(x["date"], "%m/%d/%Y").date().isoformat() == date]
                if len(matching) != 1:
                    raise ValueError("Missing or duplicated original last trading session")
                open_price = Decimal(matching[0]["open"].replace("$", "").replace(",", ""))
                close_price = Decimal(matching[0]["close"].replace("$", "").replace(",", ""))
                if not open_price.is_finite() or not close_price.is_finite() or min(open_price,close_price) <= 0:
                    raise ValueError("Invalid original Nasdaq OHLC")
                sessions[month][sym] = {
                    "declined":close_price < open_price,
                    "return":100*(close_price/open_price-1)
                }
        out = []
        original_data = data["observations"]
        for row in original_data:
            m = row["month"]
            observed = [s for s in SYMBOLS if sessions[m][s]["declined"]]
            avg_return = sum((sessions[m][s]["return"] for s in SYMBOLS), Decimal(0))/7
            avg_4 = str(avg_return.quantize(Q4, rounding=ROUND_HALF_UP))
            if (observed != row["decliners"]
                    or avg_4 != row["mean_equal_open_notional_session_return_pct"]):
                raise ValueError("Original Nasdaq OHLC does not reproduce shadow market observation")
            out.append({"month":m,"decliners":observed,"mean_intraday_return_pct":avg_4,
                        "raw_sha256_rechecked":7,"historical_pit":False})
        return out


if __name__=="__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--original-zip",type=Path,default=None)
    args=ap.parse_args()
    result={"research_scenarios":validate_receipt(),"has_archive_rehash":args.original_zip is not None,
            "original_archive_checks":validate_original_zip(args.original_zip) if args.original_zip else None,
            "historical_pit_certified":False,"historical_aics":None}
    print(json.dumps(result,ensure_ascii=False,indent=2))
