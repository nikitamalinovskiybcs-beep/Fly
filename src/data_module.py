"""Data Module — загрузка и обновление рыночных данных через yfinance."""

import datetime as dt
from typing import Optional
import time
import logging

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

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
    if not tickers:
        raise ValueError("tickers не может быть пустым")
    
    kwargs: dict = {"interval": interval, "group_by": "ticker", "threads": True}
    if start and end:
        kwargs["start"] = start
        kwargs["end"] = end
    else:
        kwargs["period"] = period

    try:
        logger.info(f"Загружаю данные для {len(tickers)} тикеров, период: {period}")
        raw = yf.download(tickers, **kwargs)

        if isinstance(raw.columns, pd.MultiIndex):
            closes = raw.xs("Close", axis=1, level=1)
        else:
            closes = raw[["Close"]].rename(columns={"Close": tickers[0]})

        closes = closes.dropna(how="all").ffill()
        
        if closes.empty:
            raise ValueError("Не удалось загрузить данные — проверьте тикеры")
        
        logger.info(f"Успешно загружены данные: {closes.shape}")
        return closes
    
    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {str(e)}")
        raise


def fetch_ohlcv(
    ticker: str,
    period: str = "5y",
    interval: str = "1d",
) -> pd.DataFrame:
    """Загрузка полного OHLCV для одного тикера."""
    try:
        data = yf.download(ticker, period=period, interval=interval)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data.dropna()
    except Exception as e:
        logger.error(f"Ошибка загрузки OHLCV для {ticker}: {str(e)}")
        raise


def last_close(ticker: str) -> float:
    """Возвращает последнюю цену закрытия."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="1d")
        if hist.empty:
            return float("nan")
        return float(hist["Close"].iloc[-1])
    except Exception as e:
        logger.error(f"Ошибка получения цены {ticker}: {str(e)}")
        return float("nan")


def market_is_closed() -> bool:
    """Грубая проверка — NYSE закрывается в 21:00 UTC в будние."""
    now = dt.datetime.now(dt.timezone.utc)
    if now.weekday() >= 5:
        return True
    return now.hour >= 21 or now.hour < 13
