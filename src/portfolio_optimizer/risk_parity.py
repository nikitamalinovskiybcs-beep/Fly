"""Risk parity optimizer — inverse-volatility weighting."""

import numpy as np
import pandas as pd

from ._common import build_allocation
from .models import PortfolioAllocation


class RiskParityOptimizer:
    """Allocate so each asset contributes equal risk (naive inverse-vol).

    weight_i = (1/sigma_i) / sum_j(1/sigma_j)
    """

    def optimize(self, returns: pd.DataFrame) -> PortfolioAllocation:
        tickers = list(returns.columns)
        vol = returns.std().to_numpy()
        vol = np.where(vol <= 0, np.nan, vol)
        inv = 1.0 / vol
        inv = np.nan_to_num(inv, nan=0.0)
        total = inv.sum()
        if total <= 0:
            weights = np.repeat(1.0 / len(tickers), len(tickers))
        else:
            weights = inv / total
        return build_allocation(tickers, weights, "risk_parity", returns)
