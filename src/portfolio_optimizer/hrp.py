"""Hierarchical Risk Parity (Lopez de Prado, 2016)."""

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform

from ._common import build_allocation
from .models import PortfolioAllocation


class HRPOptimizer:
    """Hierarchical Risk Parity.

    1. distance matrix from correlation
    2. hierarchical clustering
    3. quasi-diagonalization
    4. recursive bisection for weights

    More stable than Markowitz (no covariance inversion required).
    """

    def optimize(self, returns: pd.DataFrame) -> PortfolioAllocation:
        tickers = list(returns.columns)
        n = len(tickers)
        if n == 1:
            return build_allocation(tickers, np.array([1.0]), "hrp", returns)

        cov = returns.cov()
        corr = returns.corr().fillna(0.0)
        dist = np.sqrt(np.clip((1.0 - corr) / 2.0, 0.0, 1.0))
        np.fill_diagonal(dist.values, 0.0)
        condensed = squareform(dist.values, checks=False)
        link = linkage(condensed, method="single")
        order = self._quasi_diag(link, n)
        ordered_tickers = [tickers[i] for i in order]
        weights = self._recursive_bisection(cov, ordered_tickers)
        w = np.array([weights[t] for t in tickers])
        return build_allocation(tickers, w, "hrp", returns)

    @staticmethod
    def _quasi_diag(link: np.ndarray, n: int) -> list[int]:
        link = link.astype(int)
        sort_ix = [link[-1, 0], link[-1, 1]]
        while max(sort_ix) >= n:
            new = []
            for idx in sort_ix:
                if idx < n:
                    new.append(idx)
                else:
                    row = link[idx - n]
                    new.append(int(row[0]))
                    new.append(int(row[1]))
            sort_ix = new
        return sort_ix

    def _recursive_bisection(self, cov: pd.DataFrame, ordered: list[str]) -> dict[str, float]:
        weights = {t: 1.0 for t in ordered}
        clusters = [ordered]
        while clusters:
            next_clusters = []
            for cluster in clusters:
                if len(cluster) <= 1:
                    continue
                half = len(cluster) // 2
                left, right = cluster[:half], cluster[half:]
                var_left = self._cluster_var(cov, left)
                var_right = self._cluster_var(cov, right)
                alpha = 1.0 - var_left / (var_left + var_right) if (var_left + var_right) > 0 else 0.5
                for t in left:
                    weights[t] *= alpha
                for t in right:
                    weights[t] *= 1.0 - alpha
                next_clusters.extend([left, right])
            clusters = next_clusters
        total = sum(weights.values())
        if total > 0:
            weights = {t: w / total for t, w in weights.items()}
        return weights

    @staticmethod
    def _cluster_var(cov: pd.DataFrame, cluster: list[str]) -> float:
        sub = cov.loc[cluster, cluster].to_numpy()
        ivp = 1.0 / np.diag(sub)
        ivp = ivp / ivp.sum()
        return float(ivp @ sub @ ivp)
