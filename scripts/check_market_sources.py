"""Compare free OHLCV sources without changing model state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_module import fetch_prices, fetch_stooq_prices
from src.data_quality import compare_price_sources


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tickers", nargs="+")
    args = parser.parse_args()
    primary_frame = fetch_prices(args.tickers, period="1y")
    primary = {
        ticker: [float(value) for value in primary_frame[ticker].dropna()]
        for ticker in args.tickers
        if ticker in primary_frame
    }
    secondary = fetch_stooq_prices(args.tickers)
    print(json.dumps(compare_price_sources(primary, secondary), indent=2))


if __name__ == "__main__":
    main()
