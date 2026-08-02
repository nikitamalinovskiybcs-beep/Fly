"""Provider-specific adapters for historical / snapshot data."""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


class YFinanceProvider:
    """Historical + delayed-snapshot data via yfinance (free)."""

    name = "yfinance"

    def history(self, ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        try:
            import yfinance as yf

            return yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("yfinance history failed for %s: %s", ticker, exc)
            return pd.DataFrame()

    def last_price(self, ticker: str) -> float | None:
        df = self.history(ticker, period="5d")
        if df is None or df.empty:
            return None
        close = df["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        return float(close.iloc[-1])


class ProviderChain:
    """Try providers in order until one returns data."""

    def __init__(self, providers: list | None = None):
        self.providers = providers or [YFinanceProvider()]

    def history(self, ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        for provider in self.providers:
            df = provider.history(ticker, period=period, interval=interval)
            if df is not None and not df.empty:
                return df
        return pd.DataFrame()

    def last_price(self, ticker: str) -> float | None:
        for provider in self.providers:
            price = provider.last_price(ticker)
            if price is not None:
                return price
        return None
