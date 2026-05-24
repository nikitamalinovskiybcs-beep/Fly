"""Data Module — загрузка и обновление рыночных данных через yfinance."""

import datetime as dt
from typing import Optional

import pandas as pd
import yfinance as yf

DEFAULT_TICKERS = [
    "SPY", "QQQ", "IWM",   # индексы
    "TLT", "GLD", "USO",   # облигации, золото, нефть
    "BTC-USD", "ETH-USD",  # крипто
]


def fetch_prices(
    tickers: list[str],
    period: str = "5y",
    interval: str = "1d",
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    """Скачивает close-цены для списка тикеров.

    Returns
    -------
    pd.DataFrame
        Колонки — тикеры, индекс — даты.
    """
    kwargs: dict = {"interval": interval, "group_by": "ticker", "threads": True}
    if start and end:
        kwargs["start"] = start
        kwargs["end"] = end
    else:
        kwargs["period"] = period

    raw = yf.download(tickers, **kwargs)

    if isinstance(raw.columns, pd.MultiIndex):
        closes = raw.xs("Close", axis=1, level=1)
    else:
        closes = raw[["Close"]].rename(columns={"Close": tickers[0]})

    closes = closes.dropna(how="all").ffill()
    return closes


def fetch_ohlcv(
    ticker: str,
    period: str = "5y",
    interval: str = "1d",
) -> pd.DataFrame:
    """Загрузка полного OHLCV для одного тикера."""
    data = yf.download(ticker, period=period, interval=interval)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data.dropna()


def last_close(ticker: str) -> float:
    """Возвращает последнюю цену закрытия."""
    t = yf.Ticker(ticker)
    hist = t.history(period="1d")
    if hist.empty:
        return float("nan")
    return float(hist["Close"].iloc[-1])


def market_is_closed() -> bool:
    """Грубая проверка — NYSE закрывается в 21:00 UTC в будние."""
    now = dt.datetime.now(dt.timezone.utc)
    if now.weekday() >= 5:
        return True
    return now.hour >= 21 or now.hour < 13
