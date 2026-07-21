"""Pairs trading — trade mean-reverting spreads between correlated names."""

import numpy as np
import pandas as pd

from src.backtester.strategy_base import BaseStrategy


class PairsTradingStrategy(BaseStrategy):
    """Trade the spread of highly correlated pairs.

    For each correlated pair, when the z-score of the price spread exceeds
    +2 -> short the outperformer / long the underperformer, and vice-versa.
    """

    CORR_THRESHOLD = 0.7
    Z_ENTRY = 2.0
    LOOKBACK = 60

    def name(self) -> str:
        return "Pairs Trading"

    def generate_signals(self, data, features, date) -> dict[str, float]:
        signals: dict[str, float] = {t: 0.0 for t in data}
        tickers = list(data.keys())
        closes: dict[str, pd.Series] = {}
        for t in tickers:
            window = data[t][data[t].index <= pd.Timestamp(date)]
            c = window["Close"]
            if isinstance(c, pd.DataFrame):
                c = c.iloc[:, 0]
            if len(c) >= self.LOOKBACK:
                closes[t] = c.tail(self.LOOKBACK)

        valid = list(closes.keys())
        for i in range(len(valid)):
            for j in range(i + 1, len(valid)):
                a, b = valid[i], valid[j]
                sa, sb = closes[a], closes[b]
                aligned = pd.concat([sa, sb], axis=1).dropna()
                if len(aligned) < self.LOOKBACK // 2:
                    continue
                x = aligned.iloc[:, 0]
                y = aligned.iloc[:, 1]
                if x.corr(y) < self.CORR_THRESHOLD:
                    continue
                spread = x / x.iloc[0] - y / y.iloc[0]
                mu, sigma = spread.mean(), spread.std()
                if sigma <= 0:
                    continue
                z = (spread.iloc[-1] - mu) / sigma
                if z > self.Z_ENTRY:
                    signals[a] = min(signals[a] - 0.5, -0.5)
                    signals[b] = max(signals[b] + 0.5, 0.5)
                elif z < -self.Z_ENTRY:
                    signals[a] = max(signals[a] + 0.5, 0.5)
                    signals[b] = min(signals[b] - 0.5, -0.5)
        return {t: float(np.clip(s, -1.0, 1.0)) for t, s in signals.items()}
