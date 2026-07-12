"""Feature store data models."""

from dataclasses import asdict, dataclass, fields
from typing import Optional


@dataclass
class FeatureVector:
    """All computed features for a single ticker on a given date."""

    ticker: str
    date: str
    rsi_14: Optional[float] = None
    rsi_28: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_100: Optional[float] = None
    sma_200: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    atr_14: Optional[float] = None
    atr_pct: Optional[float] = None
    momentum_5d: Optional[float] = None
    momentum_10d: Optional[float] = None
    momentum_30d: Optional[float] = None
    momentum_60d: Optional[float] = None
    volume_ratio_20d: Optional[float] = None
    volatility_30d: Optional[float] = None
    volatility_60d: Optional[float] = None
    distance_to_sma50_pct: Optional[float] = None
    distance_to_sma200_pct: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_lower: Optional[float] = None
    bollinger_pct_b: Optional[float] = None
    adx_14: Optional[float] = None
    regime: Optional[str] = None  # bull/bear/sideways
    regime_confidence: Optional[float] = None
    evt_var_95: Optional[float] = None
    implied_vol: Optional[float] = None
    iv_skew: Optional[float] = None
    iv_percentile: Optional[float] = None
    correlation_spy_30d: Optional[float] = None
    beta_spy_60d: Optional[float] = None
    vix: Optional[float] = None
    dxy_change_5d: Optional[float] = None
    us10y: Optional[float] = None
    oil_change_5d: Optional[float] = None

    @classmethod
    def numeric_fields(cls) -> list[str]:
        """Names of all float features (excludes ticker/date/regime)."""
        skip = {"ticker", "date", "regime"}
        return [f.name for f in fields(cls) if f.name not in skip]

    def to_dict(self) -> dict:
        return asdict(self)

    def as_feature_map(self) -> dict[str, float]:
        """Return only the non-None numeric features."""
        out: dict[str, float] = {}
        for name in self.numeric_fields():
            val = getattr(self, name)
            if val is not None:
                out[name] = val
        return out
