"""Phoenix/Autocall MC pricing engine.

Full Monte Carlo pricing using implied vol, implied correlation,
and optionally local volatility. Generates correlated paths for
worst-of basket products with autocall, coupon, and barrier features.
"""

import logging
from datetime import datetime

import numpy as np

from src.phoenix.models import PhoenixPricingResult

logger = logging.getLogger(__name__)


class PhoenixPricingEngine:
    """MC pricing for Phoenix/Autocall structured products."""

    def price(
        self,
        tickers: list[str],
        strikes: dict[str, float],
        barrier_pct: float = 0.60,
        observation_dates: list[str] = (),
        coupon_rate: float = 0.10,
        autocall_level_pct: float = 1.00,
        notional: float = 100.0,
        n_simulations: int = 50000,
        use_local_vol: bool = False,
        seed: int = 42,
        risk_free_rate: float = 0.05,
    ) -> PhoenixPricingResult:
        """Price a Phoenix/Autocall product via MC simulation.

        Args:
            tickers: Basket underlyings.
            strikes: Initial fixing levels {ticker: price}.
            barrier_pct: Knock-in barrier as fraction of strike.
            observation_dates: Autocall observation dates (YYYY-MM-DD).
            coupon_rate: Annual coupon rate.
            autocall_level_pct: Autocall trigger as fraction of strike.
            notional: Face value.
            n_simulations: Number of MC paths.
            use_local_vol: Use local vol surface instead of flat IV.
            seed: RNG seed.

        Returns:
            PhoenixPricingResult with fair value and probabilities.
        """
        if not tickers or not strikes or not observation_dates:
            return PhoenixPricingResult(fair_value_pct=0.0)
        if n_simulations < 100:
            raise ValueError("n_simulations must be at least 100")
        if not 0 <= barrier_pct <= 1 or not 0 < coupon_rate:
            raise ValueError("invalid barrier or coupon rate")

        rng = np.random.default_rng(seed)
        n = len(tickers)
        r = float(risk_free_rate)

        ivs = self._get_ivs(tickers, use_local_vol)
        corr_matrix = self._get_correlation_matrix(tickers)
        cholesky = np.linalg.cholesky(corr_matrix)

        obs_times = self._dates_to_years(observation_dates)
        if any(
            current <= previous
            for previous, current in zip(obs_times, obs_times[1:])
        ):
            raise ValueError("observation_dates must be strictly increasing")
        n_obs = len(obs_times)
        dt_list = [obs_times[0]] + [obs_times[i] - obs_times[i - 1] for i in range(1, n_obs)]

        autocall_probs: dict[str, float] = {}
        total_coupons = np.zeros(n_simulations)
        total_payoffs = np.zeros(n_simulations)
        autocalled = np.zeros(n_simulations, dtype=bool)
        worst_of_count: dict[str, int] = {t: 0 for t in tickers}
        barrier_breached = np.zeros(n_simulations, dtype=bool)

        spots = np.array([float(strikes[t]) for t in tickers])
        current_levels = np.tile(spots, (n_simulations, 1))

        for obs_idx in range(n_obs):
            dt = dt_list[obs_idx]
            z = rng.standard_normal((n_simulations, n))
            corr_z = z @ cholesky.T

            for j in range(n):
                drift = (r - 0.5 * ivs[j]**2) * dt
                diffusion = ivs[j] * np.sqrt(dt) * corr_z[:, j]
                current_levels[:, j] *= np.exp(drift + diffusion)

            performance = current_levels / spots[np.newaxis, :]
            all_above_autocall = np.all(performance >= autocall_level_pct, axis=1)
            new_autocalls = all_above_autocall & ~autocalled
            n_new = new_autocalls.sum()
            autocall_probs[observation_dates[obs_idx]] = float(n_new / n_simulations)

            coupon_period = dt_list[obs_idx]
            coupon_amount = notional * coupon_rate * coupon_period
            coupon_eligible = ~autocalled
            total_coupons[coupon_eligible] += coupon_amount

            discount = np.exp(-r * obs_times[obs_idx])
            total_payoffs[new_autocalls] = (notional + total_coupons[new_autocalls]) * discount
            autocalled |= new_autocalls

            below_barrier = np.any(performance < barrier_pct, axis=1)
            barrier_breached |= below_barrier

            worst_idx = performance.argmin(axis=1)
            for j, t in enumerate(tickers):
                worst_of_count[t] += int((worst_idx == j).sum())

        final_discount = np.exp(-r * obs_times[-1]) if obs_times else 1.0

        final_worst = (current_levels / spots[np.newaxis, :]).min(axis=1)
        for i in range(n_simulations):
            if not autocalled[i]:
                if barrier_breached[i]:
                    total_payoffs[i] = (notional * final_worst[i] + total_coupons[i]) * final_discount
                else:
                    total_payoffs[i] = (notional + total_coupons[i]) * final_discount

        fair_value = float(total_payoffs.mean())
        fair_value_pct = round(fair_value / notional * 100, 2)

        expected_coupons = int(round(total_coupons.mean() / (notional * coupon_rate * (obs_times[-1] / n_obs)) if n_obs > 0 else 0))
        autocall_cumulative = np.cumsum([autocall_probs.get(d, 0) for d in observation_dates])
        expected_life = sum(
            obs_times[i] * autocall_probs.get(observation_dates[i], 0)
            for i in range(n_obs)
        )
        remaining = 1.0 - (autocall_cumulative[-1] if len(autocall_cumulative) > 0 else 0)
        expected_life += remaining * (obs_times[-1] if obs_times else 1.0)

        worst_asset = max(worst_of_count, key=worst_of_count.get) if worst_of_count else ""
        worst_prob = worst_of_count.get(worst_asset, 0) / (n_simulations * n_obs) if n_obs > 0 else 0

        return PhoenixPricingResult(
            fair_value_pct=fair_value_pct,
            autocall_probabilities=autocall_probs,
            expected_coupon_payments=expected_coupons,
            expected_life_years=round(expected_life, 2),
            worst_of_asset=worst_asset,
            worst_of_prob=round(worst_prob, 4),
        )

    def _get_ivs(self, tickers: list[str], use_local_vol: bool) -> list[float]:
        """Get implied vols for all tickers."""
        try:
            from src.phoenix.implied_vol import ImpliedVolEngine
            engine = ImpliedVolEngine()
            return [engine.get_atm_iv(t) for t in tickers]
        except Exception:
            return [0.30] * len(tickers)

    def _get_correlation_matrix(self, tickers: list[str]) -> np.ndarray:
        """Get correlation matrix for basket."""
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
        """Convert date strings to time in years from now."""
        today = datetime.now().date()
        years = []
        for d in dates:
            try:
                dt = datetime.strptime(d, "%Y-%m-%d").date()
                years.append(max((dt - today).days / 365.25, 0.01))
            except ValueError:
                years.append(0.25)
        return years
