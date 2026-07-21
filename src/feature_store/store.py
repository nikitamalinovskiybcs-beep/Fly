"""Main feature store interface. Compute once, reuse everywhere."""

import logging

import pandas as pd

from .cache import FeatureCache
from .features import (
    compute_adx,
    compute_atr,
    compute_beta,
    compute_bollinger,
    compute_correlation_to_spy,
    compute_ema,
    compute_macd,
    compute_momentum,
    compute_rsi,
    compute_sma,
    compute_volatility,
    compute_volume_ratio,
)
from .models import FeatureVector

logger = logging.getLogger(__name__)

MIN_CACHED_FEATURES = 20  # if this many features are cached, skip recompute


class FeatureStore:
    """Centralized feature computation and caching.

    Usage:
        store = FeatureStore()
        vector = store.get_features("AAPL")          # FeatureVector
        vectors = store.get_features_batch(["AAPL", "MSFT"])
        matrix = store.get_feature_matrix(["AAPL", "MSFT"])  # DataFrame
    """

    def __init__(self, data_fetcher=None):
        self.cache = FeatureCache()
        self._spy_returns: pd.Series | None = None
        self._vix: float | None = None
        # data_fetcher(ticker, period) -> DataFrame with OHLCV columns.
        # Defaults to yfinance; injectable for tests / offline use.
        self._fetch = data_fetcher or self._default_fetch

    @staticmethod
    def _default_fetch(ticker: str, period: str = "1y") -> pd.DataFrame:
        try:
            import yfinance as yf

            return yf.download(ticker, period=period, progress=False, auto_adjust=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("yfinance fetch failed for %s: %s", ticker, exc)
            return pd.DataFrame()

    def get_features(self, ticker: str, date: str | None = None) -> FeatureVector:
        """Get all features for a ticker. Uses cache, computes if missing."""
        if date is None:
            date = pd.Timestamp.now().strftime("%Y-%m-%d")

        cached = self.cache.get_vector(ticker, date)
        if len(cached) >= MIN_CACHED_FEATURES:
            return FeatureVector(ticker=ticker, date=date, **cached)

        data = self._fetch(ticker, "1y")
        if data is None or data.empty:
            logger.warning("No price data for %s", ticker)
            return FeatureVector(ticker=ticker, date=date)

        close = _squeeze(data["Close"])
        high = _squeeze(data["High"])
        low = _squeeze(data["Low"])
        volume = _squeeze(data["Volume"])
        returns = close.pct_change().dropna()

        features: dict[str, float] = {}
        try:
            features["rsi_14"] = compute_rsi(close, 14)
            features["rsi_28"] = compute_rsi(close, 28)
            features["sma_20"] = compute_sma(close, 20)
            features["sma_50"] = compute_sma(close, 50)
            features["sma_100"] = compute_sma(close, 100)
            features["sma_200"] = compute_sma(close, 200)
            features["ema_12"] = compute_ema(close, 12)
            features["ema_26"] = compute_ema(close, 26)
            features["atr_14"] = compute_atr(high, low, close, 14)
            features["atr_pct"] = features["atr_14"] / float(close.iloc[-1]) * 100
            features["momentum_5d"] = compute_momentum(close, 5)
            features["momentum_10d"] = compute_momentum(close, 10)
            features["momentum_30d"] = compute_momentum(close, 30)
            features["momentum_60d"] = compute_momentum(close, 60)
            features["volume_ratio_20d"] = compute_volume_ratio(volume, 20)
            features["volatility_30d"] = compute_volatility(returns, 30)
            features["volatility_60d"] = compute_volatility(returns, 60)
            features["distance_to_sma50_pct"] = (float(close.iloc[-1]) / features["sma_50"] - 1) * 100
            features["distance_to_sma200_pct"] = (float(close.iloc[-1]) / features["sma_200"] - 1) * 100
            macd, signal, hist = compute_macd(close)
            features["macd"] = macd
            features["macd_signal"] = signal
            features["macd_histogram"] = hist
            upper, lower, pct_b = compute_bollinger(close)
            features["bollinger_upper"] = upper
            features["bollinger_lower"] = lower
            features["bollinger_pct_b"] = pct_b
            features["adx_14"] = compute_adx(high, low, close, 14)

            spy = self._get_spy_returns()
            if spy is not None and len(spy) > 60:
                features["correlation_spy_30d"] = compute_correlation_to_spy(returns, spy, 30)
                features["beta_spy_60d"] = compute_beta(returns, spy, 60)

            vix = self._get_vix()
            if vix is not None:
                features["vix"] = vix
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error computing features for %s: %s", ticker, exc)

        for name, value in features.items():
            if value is not None and not pd.isna(value):
                self.cache.set(ticker, date, name, value)

        clean = {k: v for k, v in features.items() if v is not None and not pd.isna(v)}
        return FeatureVector(ticker=ticker, date=date, **clean)

    def get_features_batch(self, tickers: list[str]) -> dict[str, FeatureVector]:
        return {t: self.get_features(t) for t in tickers}

    def get_feature_matrix(
        self, tickers: list[str], feature_names: list[str] | None = None
    ) -> pd.DataFrame:
        """Get features as DataFrame (tickers x features). For ML models."""
        vectors = self.get_features_batch(tickers)
        rows = [vec.to_dict() for vec in vectors.values()]
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.set_index("ticker")
        if feature_names and not df.empty:
            keep = [c for c in feature_names if c in df.columns]
            df = df[keep]
        return df

    def _get_spy_returns(self) -> pd.Series | None:
        if self._spy_returns is None:
            spy = self._fetch("SPY", "1y")
            if spy is not None and not spy.empty:
                self._spy_returns = _squeeze(spy["Close"]).pct_change().dropna()
        return self._spy_returns

    def _get_vix(self) -> float | None:
        if self._vix is None:
            vix = self._fetch("^VIX", "5d")
            if vix is not None and not vix.empty:
                self._vix = float(_squeeze(vix["Close"]).iloc[-1])
        return self._vix

    def invalidate_cache(self, ticker: str | None = None) -> None:
        self.cache.invalidate(ticker)

    def cache_stats(self) -> dict:
        return self.cache.stats()


def _squeeze(obj) -> pd.Series:
    """Coerce a possibly-2D yfinance column into a 1D Series."""
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj
