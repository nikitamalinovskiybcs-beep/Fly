"""Load observed historical OHLCV data into ClickHouse."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.data_manager import DataManager
from src.storage.config import StorageConfig
from src.storage import Storage


def _normalise_history(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame()

    frame = data.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame.columns = [str(column).lower().replace(" ", "_") for column in frame.columns]
    frame = frame.rename(columns={"adj_close": "adj_close"})
    required = ["open", "high", "low", "close", "volume"]
    if any(column not in frame.columns for column in required):
        return pd.DataFrame()

    frame = frame.reset_index()
    date_column = "date" if "date" in frame.columns else "datetime"
    if date_column not in frame.columns:
        date_column = frame.columns[0]
    frame["date"] = pd.to_datetime(frame[date_column], errors="coerce").dt.date
    frame["adj_close"] = frame.get("adj_close", frame["close"])
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0).astype("uint64")
    for column in ["open", "high", "low", "close", "adj_close"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["date", "open", "high", "low", "close", "adj_close"])


def ingest(tickers: list[str], period: str) -> dict[str, int]:
    storage = Storage(StorageConfig())
    if storage.clickhouse is None or not storage.clickhouse.enabled:
        raise RuntimeError("ClickHouse is not enabled; check local .env settings")

    manager = DataManager()
    inserted: dict[str, int] = {}
    for ticker in tickers:
        history = _normalise_history(manager.get_history(ticker, period=period))
        if history.empty:
            inserted[ticker] = 0
            continue

        existing = storage.clickhouse.get_ohlcv(ticker)
        if not existing.empty:
            dates = set(pd.to_datetime(existing["date"]).dt.date)
            history = history[~history["date"].isin(dates)]
        inserted[ticker] = storage.clickhouse.save_ohlcv(ticker, history)
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tickers", nargs="+", help="Equity tickers, for example AAPL MSFT NVDA")
    parser.add_argument("--period", default="3y", help="Provider period, for example 1y or 3y")
    args = parser.parse_args()

    inserted = ingest([ticker.upper() for ticker in args.tickers], args.period)
    print({"source": "yfinance_provider", "as_of": date.today().isoformat(), "inserted": inserted})


if __name__ == "__main__":
    main()
