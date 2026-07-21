"""Unified data access — live (if available) + historical fallback."""

import logging
import os

import pandas as pd

from .live_feed import LiveFeed
from .providers import ProviderChain

logger = logging.getLogger(__name__)


class DataManager:
    """Single entry point for market data.

    - get_price(ticker): latest live price if the feed has it, else last close.
    - get_history(ticker, period): historical OHLCV via provider chain.
    """

    def __init__(self, providers: ProviderChain | None = None, live_feed: LiveFeed | None = None):
        self.providers = providers or ProviderChain()
        self.live = live_feed or LiveFeed(finnhub_token=os.getenv("FINNHUB_TOKEN", ""))

    def get_price(self, ticker: str) -> float | None:
        live_price = self.live.get_latest(ticker)
        if live_price is not None:
            return live_price
        return self.providers.last_price(ticker)

    def get_prices(self, tickers: list[str]) -> dict[str, float]:
        return {t: p for t in tickers if (p := self.get_price(t)) is not None}

    def get_history(self, ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        return self.providers.history(ticker, period=period, interval=interval)

    def start_live(self, tickers: list[str], on_price=None) -> bool:
        """Subscribe + start the live feed. Returns False if unavailable."""
        self.live.subscribe(tickers)
        if on_price:
            self.live.on_price(on_price)
        return self.live.start()

    def stop_live(self) -> None:
        self.live.stop()

    @property
    def live_available(self) -> bool:
        return self.live.available
