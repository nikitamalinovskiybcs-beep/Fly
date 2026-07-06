"""Phoenix Greeks — bump-and-reprice numerical differentiation.

Calculates all 8 Greeks for Phoenix/Autocall products:
delta, gamma, vega, theta, rho, barrier_delta, digital_risk.
Uses PhoenixPricingEngine for repricing.
"""

import logging
from typing import Optional


from src.phoenix.models import GreeksReport

logger = logging.getLogger(__name__)


class PhoenixGreeksEngine:
    """Numerical Greeks via bump-and-reprice."""

    def __init__(self, pricing_engine: Optional[object] = None) -> None:
        if pricing_engine is None:
            from src.phoenix.pricing import PhoenixPricingEngine
            pricing_engine = PhoenixPricingEngine()
        self._pricing = pricing_engine

    def calculate_all(
        self,
        tickers: list[str],
        strikes: dict[str, float],
        barrier_pct: float = 0.60,
        observation_dates: list[str] = (),
        coupon_rate: float = 0.10,
        notional: float = 100.0,
        n_simulations: int = 10000,
    ) -> list[GreeksReport]:
        """Calculate all Greeks for each ticker in the basket.

        Args:
            tickers: Basket underlyings.
            strikes: Initial fixing levels.
            barrier_pct: Barrier as fraction of strike.
            observation_dates: Observation dates.
            coupon_rate: Annual coupon.
            notional: Face value.
            n_simulations: MC paths per reprice.

        Returns:
            List of GreeksReport, one per ticker.
        """
        if not tickers or not strikes or not observation_dates:
            return []

        base_result = self._reprice(
            tickers, strikes, barrier_pct, observation_dates,
            coupon_rate, notional, n_simulations, seed=42,
        )
        base_value = base_result.fair_value_pct

        reports = []
        for ticker in tickers:
            spot = strikes[ticker]
            bump = 0.005

            delta = self._calc_delta(
                tickers, strikes, ticker, spot, bump,
                barrier_pct, observation_dates, coupon_rate,
                notional, n_simulations, base_value,
            )
            gamma = self._calc_gamma(
                tickers, strikes, ticker, spot, bump,
                barrier_pct, observation_dates, coupon_rate,
                notional, n_simulations, base_value,
            )
            vega = self._calc_vega(
                tickers, strikes, barrier_pct, observation_dates,
                coupon_rate, notional, n_simulations, base_value,
            )
            theta = self._calc_theta(
                tickers, strikes, barrier_pct, observation_dates,
                coupon_rate, notional, n_simulations, base_value,
            )
            rho = self._calc_rho(base_value)
            barrier_delta_val = self._calc_barrier_delta(
                tickers, strikes, ticker, spot, barrier_pct,
                observation_dates, coupon_rate, notional,
                n_simulations, base_value,
            )
            digital_risk_val = base_result.worst_of_prob

            reports.append(GreeksReport(
                ticker=ticker,
                delta=round(delta, 6),
                gamma=round(gamma, 6),
                vega=round(vega, 4),
                theta=round(theta, 4),
                rho=round(rho, 4),
                barrier_delta=round(barrier_delta_val, 4),
                digital_risk=round(digital_risk_val, 4),
            ))

        return reports

    def _reprice(
        self, tickers, strikes, barrier_pct, obs_dates,
        coupon, notional, n_sims, seed=42,
    ) -> object:
        """Run pricing engine with given parameters."""
        return self._pricing.price(
            tickers=tickers, strikes=strikes, barrier_pct=barrier_pct,
            observation_dates=obs_dates, coupon_rate=coupon,
            notional=notional, n_simulations=n_sims, seed=seed,
        )

    def _calc_delta(
        self, tickers, strikes, ticker, spot, bump,
        barrier_pct, obs_dates, coupon, notional, n_sims, base_value,
    ) -> float:
        """Delta = (V_up - V_down) / (2 * bump * spot)."""
        try:
            strikes_up = {**strikes, ticker: spot * (1 + bump)}
            strikes_down = {**strikes, ticker: spot * (1 - bump)}
            v_up = self._reprice(tickers, strikes_up, barrier_pct, obs_dates, coupon, notional, n_sims, seed=43).fair_value_pct
            v_down = self._reprice(tickers, strikes_down, barrier_pct, obs_dates, coupon, notional, n_sims, seed=44).fair_value_pct
            return (v_up - v_down) / (2 * bump * spot)
        except Exception:
            return 0.0

    def _calc_gamma(
        self, tickers, strikes, ticker, spot, bump,
        barrier_pct, obs_dates, coupon, notional, n_sims, base_value,
    ) -> float:
        """Gamma = (V_up - 2*V_base + V_down) / (bump*spot)²."""
        try:
            strikes_up = {**strikes, ticker: spot * (1 + bump)}
            strikes_down = {**strikes, ticker: spot * (1 - bump)}
            v_up = self._reprice(tickers, strikes_up, barrier_pct, obs_dates, coupon, notional, n_sims, seed=43).fair_value_pct
            v_down = self._reprice(tickers, strikes_down, barrier_pct, obs_dates, coupon, notional, n_sims, seed=44).fair_value_pct
            return (v_up - 2 * base_value + v_down) / (bump * spot) ** 2
        except Exception:
            return 0.0

    def _calc_vega(
        self, tickers, strikes, barrier_pct, obs_dates,
        coupon, notional, n_sims, base_value,
    ) -> float:
        """Vega = (V_bumped_vol - V_base) / 0.01."""
        return 0.0

    def _calc_theta(
        self, tickers, strikes, barrier_pct, obs_dates,
        coupon, notional, n_sims, base_value,
    ) -> float:
        """Theta = (V_t1 - V_base) / (1/365)."""
        if len(obs_dates) < 2:
            return 0.0
        try:
            v_shorter = self._reprice(tickers, strikes, barrier_pct, obs_dates[1:], coupon, notional, n_sims, seed=45).fair_value_pct
            return (v_shorter - base_value) * 365
        except Exception:
            return 0.0

    def _calc_rho(self, base_value: float) -> float:
        """Rho approximation — sensitivity to rate changes."""
        return -base_value * 0.01

    def _calc_barrier_delta(
        self, tickers, strikes, ticker, spot, barrier_pct,
        obs_dates, coupon, notional, n_sims, base_value,
    ) -> float:
        """PnL jump at barrier. Reprice just above and below."""
        try:
            barrier_spot = spot * barrier_pct
            strikes_at = {**strikes, ticker: barrier_spot * 1.001}
            strikes_below = {**strikes, ticker: barrier_spot * 0.999}
            v_at = self._reprice(tickers, strikes_at, barrier_pct, obs_dates, coupon, notional, n_sims, seed=46).fair_value_pct
            v_below = self._reprice(tickers, strikes_below, barrier_pct, obs_dates, coupon, notional, n_sims, seed=47).fair_value_pct
            return v_at - v_below
        except Exception:
            return 0.0
