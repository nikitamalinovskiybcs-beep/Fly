#!/usr/bin/env python3
"""Validate SEC companyfacts; no scoring or promotion."""
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

ROOT = Path("aics_data/xbrl")
TICKERS = ("NVDA", "MSFT", "AMZN", "GOOGL", "META", "ORCL")
TAGS = {"Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
        "NetIncomeLoss", "OperatingIncomeLoss",
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "CashAndCashEquivalentsAtCarryingValue", "LongTermDebtNoncurrent"}
errors = []
counts = {}
manifest_path = ROOT / "manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
try:
    as_of = dt.date.fromisoformat(manifest["as_of"])
    if as_of > dt.date.today():
        errors.append("future_as_of")
except (KeyError, ValueError, TypeError):
    errors.append("invalid_as_of")
    as_of = dt.date.min
results = manifest.get("results", [])
if len(results) != len(TICKERS) or {r.get("ticker") for r in results} != set(TICKERS):
    errors.append("incomplete_manifest")
if any(r.get("status") != "downloaded_unverified" for r in results):
    errors.append("failed_source")
if manifest.get("publishable") is not False or manifest.get("verified_pit") is not False:
    errors.append("unsafe_manifest_flags")
if manifest.get("index_aics") is not None or manifest.get("model_score") is not None:
    errors.append("unexpected_score")
for ticker in TICKERS:
    path = ROOT / f"sec_xbrl_{ticker}.json"
    if not path.exists():
        errors.append(f"{ticker}:missing_file")
        continue
    try:
        facts = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(facts, list):
            raise ValueError("not a list")
        counts[ticker] = len(facts)
        matching = [r for r in results if r.get("ticker") == ticker]
        if len(matching) != 1 or matching[0].get("facts") != len(facts):
            errors.append(f"{ticker}:manifest_fact_count_mismatch")
        seen = set()
        for fact in facts:
            filed = dt.date.fromisoformat(fact["filed_at"])
            available = dt.date.fromisoformat(fact["available_at"])
            end = dt.date.fromisoformat(fact["period_end"])
            start = dt.date.fromisoformat(fact["period_start"]) if fact.get("period_start") else None
            key = (fact["cik"], fact["xbrl_tag"], fact["unit"],
                   fact.get("period_start"), fact["period_end"],
                   fact["accession_number"], fact["form"], fact["value"])
            if key in seen:
                errors.append(f"{ticker}:duplicate_fact")
                break
            seen.add(key)
            value = fact["value"]
            if (fact["ticker"] != ticker or fact["taxonomy"] != "us-gaap"
                or fact["xbrl_tag"] not in TAGS or fact["verified_pit"] is not False
                or fact["form"] not in ("10-K", "10-Q")
                or not fact["unit"] or not fact["accession_number"]
                or not fact["cik"] or len(str(fact["cik"])) != 10
                or not isinstance(value, (int, float))
                or isinstance(value, bool) or not math.isfinite(value)
                or available != filed + dt.timedelta(days=14)
                or available > as_of or end > filed or (start and start > end)):
                errors.append(f"{ticker}:invalid_fact")
                break
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        errors.append(f"{ticker}:{type(exc).__name__}")
digests = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
           for p in sorted(ROOT.glob("*.json")) if p.name != "quality_report.json"}
report = {"as_of":manifest.get("as_of"), "source":"SEC companyfacts",
          "company_counts":counts, "errors":errors, "passed":not errors,
          "file_sha256":digests, "index_aics":None, "model_score":None,
          "promotion":"BLOCKED", "production_weights_changed":False,
          "verdict_mutated":False, "trades_created":False}
ROOT.mkdir(parents=True, exist_ok=True)
(ROOT/"quality_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({"passed":report["passed"],"errors":errors,"company_counts":counts},indent=2))
if errors:
    raise SystemExit("AICS SEC XBRL quality validation failed")
