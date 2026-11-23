"""Verify November 20 2026 post-roster AI Equities breadth against 7 OHLC quotes.

This is independent source *comparison* for a date-after-roster session, not
primary exchange tape PIT attestation or a historical multi-month AICS score.
"""
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import json

SOURCE=Path("aics_data/research/ai_equities_2026_11_20_cross_vendor_ohlc_reconciliation_2026_11_21.json")
OLDER=Path("aics_data/research/aics_2026_11_20_close_research_rollover.json")
SYMBOLS=("NVDA","MSFT","GOOGL","AMZN","META","ORCL","MU")
PRICE_SOURCES={
    "NVDA":"https://www.stockquote.io/stocks/NVDA/history",
    "MSFT":"https://www.stockquote.io/stocks/MSFT/history",
    "GOOGL":"https://www.stockquote.io/stocks/GOOGL/history",
    "AMZN":"https://stockanalysis.com/stocks/amzn/history/",
    "META":"https://www.stockquote.io/stocks/META/history",
    "ORCL":"https://www.stockquote.io/stocks/ORCL/history",
    "MU":"https://www.stockquote.io/stocks/MU/history"
}


def calculate(receipt=None, older=None):
    receipt=receipt if receipt is not None else json.loads(SOURCE.read_text(encoding="utf-8"))
    older=older if older is not None else json.loads(OLDER.read_text(encoding="utf-8"))
    flags=receipt.get("caveats",{})
    if (receipt.get("schema")!="aics-seven-security-postroster-nov20-secondary-crosscheck-v1"
            or receipt.get("session")!="2026-11-20"
            or receipt.get("research_asof")!="2026-11-21"
            or older.get("session")!="2026-11-20"
            or older.get("source_snapshot_retrieved")!="2026-11-21"
            or receipt.get("predeclared_roster_source")!="aics_data/research/ai_equities_2026_11_19_nasdaq_current_directory_rehash.json"
            or receipt.get("earlier_primary_capture_source")!=str(OLDER)
            or receipt.get("benchmark_state",{}).get("original_rollover_reconciles") is not True
            or receipt["benchmark_state"].get("november_research_11_node_shadow_certified") is not False
            or receipt["benchmark_state"].get("november_20_non_equity_inputs_carried_from")!="2026-11-18"
            or any(flags.get(k) is not False for k in (
                "independent_exchange_primary_price_feed_attested",
                "raw_webpages_saved_as_original_bytes",
                "official_pre_open_constituent_roster_historical_confirmed",
                "independently_certified_pit",
                "full_24_month_composite_available",
                "investment_decision_from_score",
                "originally_quoted_scores_promoted_to_october_2026",
                "trades_created"))
            or flags.get("roster_observed_2026_11_19") is not True
            or flags.get("dated_secondary_price_observations_after_session") is not True
            or flags.get("historical_aics_spread_to_sp500") is not None):
        raise ValueError("Invalid post-roster secondary market source or forged certification")
    rows=receipt["original_ohlc_rows"]
    prior=older["observations"]
    if (len(rows)!=7 or [r["symbol"] for r in rows]!=list(SYMBOLS)
            or len(prior)!=7 or {x["symbol"] for x in prior}!=set(SYMBOLS)):
        raise ValueError("Seven predeclared basket securities not complete")
    original={r["symbol"]:r for r in prior}
    returns=[]
    for row in rows:
        sym=row["symbol"]
        if (row.get("source_url")!=PRICE_SOURCES[sym]
                or row.get("source_original_bytes_sha256") is not None
                or row.get("source_capture_asof")!="2026-11-21"
                or row.get("market_data_original_exchange_feed_verified") is not False):
            raise ValueError("Secondary quote or date provenance was altered")
        start,end=Decimal(row["open"]),Decimal(row["close"])
        if (not start.is_finite() or not end.is_finite() or start<=0 or end<=0
                or Decimal(original[sym]["open"])!=start
                or Decimal(original[sym]["close"])!=end):
            raise ValueError("Cross-vendor original OHLC mismatch")
        returns.append(100*(end/start-1))
    declines=sum(r<0 for r in returns)
    breadth=str((Decimal(100)*declines/7).quantize(Decimal(".01"),rounding=ROUND_HALF_UP))
    pct=str((sum(returns,Decimal(0))/7).quantize(Decimal(".000001"),rounding=ROUND_HALF_UP))
    if (declines!=receipt["scores"]["decliners"]
            or breadth!=receipt["scores"]["equity_breadth_0_100"]
            or pct!=receipt["scores"]["equal_weight_session_return_pct"]
            or breadth!=older["expected"]["ai_equities_score"]
            or pct!=older["expected"]["equal_weight_open_to_close_pct"]):
        raise ValueError("Second-source research breadth or mean differs from frozen release")
    return {
        "market_session":"2026-11-20",
        "post_roster_date":True,
        "seven_decliners":declines,
        "equity_stress_research_only":breadth,
        "mean_intraday_return_pct":pct,
        "observed_corroboration_date":"2026-11-21",
        "official_exchange_original_pit":False,
        "historical_24m_composite":None,
        "aics_sp500_historical_spread":None,
        "trade_signal":False
    }


if __name__=="__main__":
    print(json.dumps(calculate(),ensure_ascii=False,indent=2))
