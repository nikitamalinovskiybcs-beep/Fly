"""Feature computation functions. Each returns a single scalar value.

All functions are pure and operate on pandas Series of prices/volume.
"""

import numpy as np
import pandas as pd


def compute_rsi(prices: pd.Series, period: int = 14) -> float:
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    last_loss = loss.iloc[-1]
    if last_loss == 0 or pd.isna(last_loss):
        return 100.0
    rs = gain.iloc[-1] / last_loss
    return float(100 - (100 / (1 + rs)))


def compute_sma(prices: pd.Series, period: int) -> float:
    return float(prices.rolling(period).mean().iloc[-1])


def compute_ema(prices: pd.Series, period: int) -> float:
    return float(prices.ewm(span=period, adjust=False).mean().iloc[-1])


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])


def compute_momentum(prices: pd.Series, days: int) -> float:
    if len(prices) <= days:
        return 0.0
    return float((prices.iloc[-1] / prices.iloc[-days] - 1) * 100)


def compute_volume_ratio(volume: pd.Series, period: int = 20) -> float:
    avg = volume.rolling(period).mean().iloc[-1]
    if avg == 0 or pd.isna(avg):
        return 1.0
    return float(volume.iloc[-1] / avg)


def compute_volatility(returns: pd.Series, period: int = 30) -> float:
    return float(returns.tail(period).std() * np.sqrt(252) * 100)


def compute_macd(prices: pd.Series) -> tuple[float, float, float]:
    ema12 = prices.ewm(span=12, adjust=False).mean()
    ema26 = prices.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal
    return (
        float(macd_line.iloc[-1]),
        float(signal.iloc[-1]),
        float(histogram.iloc[-1]),
    )


def compute_bollinger(prices: pd.Series, period: int = 20, std: float = 2.0) -> tuple[float, float, float]:
    sma = prices.rolling(period).mean()
    std_dev = prices.rolling(period).std()
    upper = sma + std * std_dev
    lower = sma - std * std_dev
    denom = (upper - lower).iloc[-1]
    if denom == 0 or pd.isna(denom):
        pct_b = 0.5
    else:
        pct_b = float((prices.iloc[-1] - lower.iloc[-1]) / denom)
    return float(upper.iloc[-1]), float(lower.iloc[-1]), pct_b


def compute_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
    plus_dm = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * ((plus_di - minus_di).abs() / di_sum)
    result = dx.rolling(period).mean().iloc[-1]
    return float(result) if not pd.isna(result) else 0.0


def compute_correlation_to_spy(returns: pd.Series, spy_returns: pd.Series, period: int = 30) -> float:
    result = returns.tail(period).corr(spy_returns.tail(period))
    return float(result) if not pd.isna(result) else 0.0


def compute_beta(returns: pd.Series, market_returns: pd.Series, period: int = 60) -> float:
    cov = returns.tail(period).cov(market_returns.tail(period))
    var = market_returns.tail(period).var()
    if var == 0 or pd.isna(var):
        return 1.0
    return float(cov / var)
