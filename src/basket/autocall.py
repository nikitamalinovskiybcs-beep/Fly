"""Autocall probability engine — Monte Carlo for worst-of basket products."""

import logging

import numpy as np

logger = logging.getLogger(__name__)


class AutocallEngine:
    """Calculate autocall probabilities via correlated MC simulation."""

    def calculate_probabilities(
        self,
        tickers: list[str],
        strikes: dict[str, float],
        barrier_pct: float = 0.60,
        observation_dates: list[str] = (),
        n_sims: int = 50000,
        seed: int = 42,
    ) -> dict:
        """MC autocall probability calculation.

        Args:
            tickers: Basket underlyings.
            strikes: Initial fixing levels.
            barrier_pct: Knock-in barrier as fraction.
            observation_dates: Observation dates.
            n_sims: Number of simulations.
            seed: RNG seed.

        Returns:
            Dict with per-date autocall probs, barrier breach prob, worst-of prediction.
        """
        if not tickers or not strikes or not observation_dates:
            return {"error": "insufficient parameters"}

        n = len(tickers)
        rng = np.random.default_rng(seed)

        ivs = self._get_ivs(tickers)
        corr_matrix = self._get_corr(tickers)

        try:
            cholesky = np.linalg.cholesky(corr_matrix)
        except np.linalg.LinAlgError:
            corr_matrix += np.eye(n) * 0.01
            cholesky = np.linalg.cholesky(corr_matrix)

        obs_years = self._dates_to_years(observation_dates)
        spots = np.array([float(strikes[t]) for t in tickers])

        autocall_probs: dict[str, float] = {}
        barrier_breach_count = 0
        worst_of_count: dict[str, int] = {t: 0 for t in tickers}

        dt_list = [obs_years[0]] + [obs_years[i] - obs_years[i - 1] for i in range(1, len(obs_years))]
        levels = np.tile(spots, (n_sims, 1))
        autocalled = np.zeros(n_sims, dtype=bool)

        for obs_idx, dt in enumerate(dt_list):
            z = rng.standard_normal((n_sims, n))
            corr_z = z @ cholesky.T
            for j in range(n):
                drift = (0.05 - 0.5 * ivs[j]**2) * dt
                diffusion = ivs[j] * np.sqrt(dt) * corr_z[:, j]
                levels[:, j] *= np.exp(drift + diffusion)

            perf = levels / spots[np.newaxis, :]
            all_above = np.all(perf >= 1.0, axis=1)
            new_ac = all_above & ~autocalled
            autocall_probs[observation_dates[obs_idx]] = float(new_ac.sum() / n_sims)
            autocalled |= new_ac

            below = np.any(perf < barrier_pct, axis=1) & ~autocalled
            barrier_breach_count += int(below.sum())

            worst_idx = perf.argmin(axis=1)
            for j, t in enumerate(tickers):
                worst_of_count[t] += int((worst_idx == j).sum())

        total_ac = float(autocalled.sum() / n_sims)
        worst_asset = max(worst_of_count, key=worst_of_count.get) if worst_of_count else ""
        total_obs = n_sims * len(observation_dates)

        return {
            "autocall_probs_by_date": autocall_probs,
            "total_autocall_prob": round(total_ac, 4),
            "barrier_breach_prob": round(barrier_breach_count / total_obs, 4) if total_obs > 0 else 0,
            "worst_of_prediction": worst_asset,
            "worst_of_frequency": {t: round(c / total_obs, 4) for t, c in worst_of_count.items()} if total_obs > 0 else {},
        }

    def _get_ivs(self, tickers: list[str]) -> list[float]:
        """Get implied vols."""
        try:
            from src.phoenix.implied_vol import ImpliedVolEngine
            engine = ImpliedVolEngine()
            return [engine.get_atm_iv(t) for t in tickers]
        except Exception:
            return [0.30] * len(tickers)

    def _get_corr(self, tickers: list[str]) -> np.ndarray:
        """Get correlation matrix."""
        n = len(tickers)
        try:
            import yfinance as yf
            returns = {}
            for t in tickers:
                hist = yf.Ticker(t).history(period="6mo")
                if not hist.empty:
                    returns[t] = hist["Close"].pct_change().dropna()
            if len(returns) < n:
                return np.eye(n) * 0.5 + np.ones((n, n)) * 0.5
            min_len = min(len(v) for v in returns.values())
            data = np.column_stack([returns[t].values[-min_len:] for t in tickers])
            corr = np.corrcoef(data, rowvar=False)
            eigvals = np.linalg.eigvalsh(corr)
            if np.min(eigvals) <= 0:
                corr += np.eye(n) * (-np.min(eigvals) + 0.01)
                d = np.sqrt(np.diag(corr))
                corr = corr / np.outer(d, d)
            return corr
        except Exception:
            return np.eye(n) * 0.5 + np.ones((n, n)) * 0.5

    def _dates_to_years(self, dates: list[str]) -> list[float]:
        """Convert dates to years from now."""
        from datetime import datetime
        today = datetime.now().date()
        return [max((datetime.strptime(d, "%Y-%m-%d").date() - today).days / 365.25, 0.01) for d in dates]
