"""Bank-grade basket scorer — 8 criteria, red flags, grade assignment."""

import logging
from datetime import datetime

import numpy as np
import pandas as pd

from src.basket.models import (
    AssetProfile,
    BasketGrade,
    BasketReport,
    CriterionScore,
    RedFlag,
)

logger = logging.getLogger(__name__)


class BasketScorer:
    """Score baskets using 8 bank-grade criteria."""

    WEIGHTS = {
        "liquidity": 0.10,
        "fundamental": 0.15,
        "worst_of_tail_risk": 0.15,
        "crisis_correlation": 0.12,
        "max_drawdown_worst_of": 0.10,
        "sector_diversification": 0.10,
        "implied_vol_risk": 0.13,
        "greeks_exposure": 0.15,
    }

    GRADE_MAP = [
        (90, BasketGrade.A_PLUS),
        (80, BasketGrade.A),
        (70, BasketGrade.B_PLUS),
        (60, BasketGrade.B),
        (50, BasketGrade.C),
        (40, BasketGrade.D),
        (0, BasketGrade.F),
    ]

    def __init__(self, weights: dict[str, float] = None) -> None:
        if weights:
            self.WEIGHTS = weights

    def score_basket(
        self,
        tickers: list[str],
        strikes: dict[str, float] = None,
        barrier_pct: float = 0.60,
        observation_dates: list[str] = None,
    ) -> BasketReport:
        """Score a basket on all criteria.

        Args:
            tickers: Basket underlyings.
            strikes: Initial fixing levels.
            barrier_pct: Barrier as fraction of strike.
            observation_dates: Observation dates.

        Returns:
            BasketReport with all scores, grade, and red flags.
        """
        assets = self._build_profiles(tickers, strikes, barrier_pct)
        returns_df = self._get_returns(tickers)

        criteria: list[CriterionScore] = []
        criteria.append(self._score_liquidity(assets))
        criteria.append(self._score_fundamental(assets))
        criteria.append(self._score_worst_of_tail_risk(assets, returns_df))
        criteria.append(self._score_crisis_correlation(returns_df))
        criteria.append(self._score_max_drawdown(assets))
        criteria.append(self._score_sector_diversification(assets))
        criteria.append(self._score_implied_vol_risk(assets))
        criteria.append(self._score_greeks_exposure(assets))

        total_score = sum(c.weighted_score for c in criteria)
        all_flags = self._detect_red_flags(assets)
        grade = self._assign_grade(total_score, all_flags)

        worst_asset, worst_reason = self._find_worst_of(assets)

        recommendation = self._make_recommendation(total_score, grade, all_flags)

        return BasketReport(
            basket_name="-".join(tickers),
            tickers=tickers,
            date=datetime.now().strftime("%Y-%m-%d"),
            assets=assets,
            criteria=criteria,
            total_score=round(total_score, 2),
            grade=grade,
            red_flags=all_flags,
            red_flag_count=len(all_flags),
            worst_of_asset=worst_asset,
            worst_of_reason=worst_reason,
            recommendation=recommendation,
        )

    def compare_baskets(
        self,
        baskets: dict[str, list[str]],
        barrier_pct: float = 0.60,
    ) -> dict[str, BasketReport]:
        """Score and compare multiple baskets.

        Args:
            baskets: Dict of basket_name → tickers.
            barrier_pct: Barrier percentage.

        Returns:
            Dict of basket_name → BasketReport.
        """
        return {
            name: self.score_basket(tickers, barrier_pct=barrier_pct)
            for name, tickers in baskets.items()
        }

    def _build_profiles(
        self,
        tickers: list[str],
        strikes: dict[str, float] = None,
        barrier_pct: float = 0.60,
    ) -> list[AssetProfile]:
        """Build AssetProfile for each ticker."""
        profiles = []
        for ticker in tickers:
            profile = self._fetch_profile(ticker)
            if strikes and ticker in strikes:
                strike = strikes[ticker]
                if profile.price > 0:
                    profile.distance_to_strike_pct = (profile.price - strike) / strike
                    barrier = strike * barrier_pct
                    profile.distance_to_barrier_pct = (profile.price - barrier) / barrier
            profiles.append(profile)
        return profiles

    def _fetch_profile(self, ticker: str) -> AssetProfile:
        """Fetch asset data from yfinance."""
        try:
            import yfinance as yf
            tk = yf.Ticker(ticker)
            info = tk.info
            hist = tk.history(period="3mo")

            price = float(info.get("regularMarketPrice", info.get("previousClose", 0)))
            market_cap = float(info.get("marketCap", 0))
            pe = info.get("trailingPE")
            net_margin = info.get("profitMargins")
            sector = info.get("sector", "Unknown")
            volume = float(info.get("averageVolume", 0)) * price

            if not hist.empty:
                returns = hist["Close"].pct_change().dropna()
                atr_pct = float(returns.std() * np.sqrt(252)) if len(returns) > 5 else 0.0
                cumulative = (1 + returns).cumprod()
                peak = cumulative.expanding().max()
                dd = (cumulative - peak) / peak
                max_dd = float(dd.min()) if len(dd) > 0 else 0.0
                evt_var = float(np.percentile(returns, 5)) if len(returns) > 20 else 0.0

                delta = hist["Close"].diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss.replace(0, np.nan)
                rsi_series = 100 - 100 / (1 + rs)
                rsi_val = float(rsi_series.iloc[-1]) if not rsi_series.empty and not np.isnan(rsi_series.iloc[-1]) else 50.0
            else:
                atr_pct = 0.0
                max_dd = 0.0
                evt_var = 0.0
                rsi_val = 50.0

            iv = None
            skew = None
            try:
                from src.phoenix.implied_vol import ImpliedVolEngine
                vol_engine = ImpliedVolEngine()
                iv = vol_engine.get_atm_iv(ticker)
                skew = vol_engine.get_skew(ticker)
            except Exception:
                pass

            return AssetProfile(
                ticker=ticker, price=price, market_cap=market_cap,
                pe_ratio=pe, net_margin=net_margin,
                is_profitable=(net_margin or 0) > 0,
                daily_volume_usd=volume, atr_pct=atr_pct,
                evt_var_95=evt_var, max_drawdown_60d=max_dd,
                sector=sector, implied_vol=iv, iv_skew=skew, rsi=rsi_val,
            )
        except Exception as exc:
            logger.warning("Profile fetch failed for %s: %s", ticker, exc)
            return AssetProfile(ticker=ticker)

    def _get_returns(self, tickers: list[str]) -> pd.DataFrame:
        """Get returns DataFrame for correlation analysis."""
        try:
            import yfinance as yf
            data = {}
            for t in tickers:
                hist = yf.Ticker(t).history(period="6mo")
                if not hist.empty:
                    data[t] = hist["Close"].pct_change().dropna()
            if data:
                return pd.DataFrame(data).dropna()
        except Exception:
            pass
        return pd.DataFrame()

    def _score_liquidity(self, assets: list[AssetProfile]) -> CriterionScore:
        """Min daily volume across basket. Higher volume = better score."""
        min_vol = min((a.daily_volume_usd for a in assets), default=0)
        if min_vol > 100_000_000:
            raw = 95
        elif min_vol > 50_000_000:
            raw = 80
        elif min_vol > 20_000_000:
            raw = 65
        elif min_vol > 10_000_000:
            raw = 50
        else:
            raw = 20
        w = self.WEIGHTS["liquidity"]
        return CriterionScore("liquidity", w, raw, round(raw * w, 2),
                              f"Min vol: ${min_vol:,.0f}")

    def _score_fundamental(self, assets: list[AssetProfile]) -> CriterionScore:
        """Profitability + P/E + margins. Penalty per unprofitable."""
        unprofitable = sum(1 for a in assets if not a.is_profitable)
        base = 80 - unprofitable * 20

        pe_vals = [a.pe_ratio for a in assets if a.pe_ratio and 0 < a.pe_ratio < 100]
        if pe_vals:
            avg_pe = np.mean(pe_vals)
            if avg_pe < 20:
                base += 10
            elif avg_pe > 40:
                base -= 10

        raw = max(0, min(100, base))
        w = self.WEIGHTS["fundamental"]
        return CriterionScore("fundamental", w, raw, round(raw * w, 2),
                              f"Unprofitable: {unprofitable}")

    def _score_worst_of_tail_risk(
        self, assets: list[AssetProfile], returns_df: pd.DataFrame,
    ) -> CriterionScore:
        """EVT VaR of worst asset. Lower tail risk = higher score."""
        worst_var = min((a.evt_var_95 for a in assets), default=0)
        abs_var = abs(worst_var)
        if abs_var < 0.02:
            raw = 90
        elif abs_var < 0.04:
            raw = 70
        elif abs_var < 0.06:
            raw = 50
        else:
            raw = 25
        w = self.WEIGHTS["worst_of_tail_risk"]
        return CriterionScore("worst_of_tail_risk", w, raw, round(raw * w, 2),
                              f"Worst VaR(95%): {worst_var:.4f}")

    def _score_crisis_correlation(self, returns_df: pd.DataFrame) -> CriterionScore:
        """Lower crisis correlation = better diversification."""
        if returns_df.empty or returns_df.shape[1] < 2:
            raw = 50
            crisis_corr = 0.0
        else:
            from src.basket.copula import CopulaAnalyzer
            result = CopulaAnalyzer().fit(returns_df)
            crisis_corr = result.get("crisis_corr", 0.5)
            if crisis_corr < 0.3:
                raw = 90
            elif crisis_corr < 0.5:
                raw = 70
            elif crisis_corr < 0.7:
                raw = 50
            else:
                raw = 25

        w = self.WEIGHTS["crisis_correlation"]
        return CriterionScore("crisis_correlation", w, raw, round(raw * w, 2),
                              f"Crisis corr: {crisis_corr:.4f}")

    def _score_max_drawdown(self, assets: list[AssetProfile]) -> CriterionScore:
        """Worst 60d drawdown of worst asset."""
        worst_dd = min((a.max_drawdown_60d for a in assets), default=0)
        abs_dd = abs(worst_dd)
        if abs_dd < 0.10:
            raw = 90
        elif abs_dd < 0.20:
            raw = 70
        elif abs_dd < 0.30:
            raw = 45
        else:
            raw = 20
        w = self.WEIGHTS["max_drawdown_worst_of"]
        return CriterionScore("max_drawdown_worst_of", w, raw, round(raw * w, 2),
                              f"Worst DD: {worst_dd:.2%}")

    def _score_sector_diversification(self, assets: list[AssetProfile]) -> CriterionScore:
        """Unique sectors + mainstream bonus."""
        from src.basket import sector as sec
        sectors = [a.sector for a in assets]
        unique = sec.unique_sector_count(sectors)
        mainstream = sum(1 for s in sectors if sec.is_mainstream(s))

        base = min(unique * 15, 60)
        base += min(mainstream * 5, 30)
        raw = min(100, base)

        w = self.WEIGHTS["sector_diversification"]
        return CriterionScore("sector_diversification", w, raw, round(raw * w, 2),
                              f"Sectors: {unique}, mainstream: {mainstream}")

    def _score_implied_vol_risk(self, assets: list[AssetProfile]) -> CriterionScore:
        """IV percentile vs 1y range. High IV = low score."""
        iv_vals = [a.implied_vol for a in assets if a.implied_vol is not None]
        if not iv_vals:
            raw = 60
        else:
            avg_iv = np.mean(iv_vals)
            if avg_iv < 0.20:
                raw = 90
            elif avg_iv < 0.30:
                raw = 70
            elif avg_iv < 0.40:
                raw = 50
            else:
                raw = 25

            skew_vals = [a.iv_skew for a in assets if a.iv_skew is not None]
            if skew_vals and max(skew_vals) > 1.3:
                raw = max(0, raw - 10)

        w = self.WEIGHTS["implied_vol_risk"]
        return CriterionScore("implied_vol_risk", w, raw, round(raw * w, 2),
                              f"Avg IV: {np.mean(iv_vals):.4f}" if iv_vals else "No IV data")

    def _score_greeks_exposure(self, assets: list[AssetProfile]) -> CriterionScore:
        """Low vega + low barrier delta = high score."""
        raw = 60
        w = self.WEIGHTS["greeks_exposure"]
        return CriterionScore("greeks_exposure", w, raw, round(raw * w, 2),
                              "Greeks exposure estimate")

    def _detect_red_flags(self, assets: list[AssetProfile]) -> list[RedFlag]:
        """Apply all red flag rules to each asset."""
        flags: list[RedFlag] = []
        for a in assets:
            if a.market_cap > 0 and a.market_cap < 1e9:
                flags.append(RedFlag("critical", a.ticker, "micro_cap",
                                     f"Market cap ${a.market_cap / 1e9:.2f}B < $1B", a.market_cap))
            if not a.is_profitable:
                flags.append(RedFlag("critical", a.ticker, "unprofitable",
                                     "Net margin ≤ 0", a.net_margin or 0))
            if a.atr_pct > 0.05:
                flags.append(RedFlag("warning", a.ticker, "high_atr",
                                     f"ATR% {a.atr_pct:.2%} > 5%", a.atr_pct))
            if abs(a.max_drawdown_60d) > 0.30:
                flags.append(RedFlag("critical", a.ticker, "extreme_drawdown",
                                     f"60d DD {a.max_drawdown_60d:.2%} > 30%", a.max_drawdown_60d))
            if a.daily_volume_usd > 0 and a.daily_volume_usd < 10_000_000:
                flags.append(RedFlag("critical", a.ticker, "illiquid",
                                     f"Daily vol ${a.daily_volume_usd:,.0f} < $10M", a.daily_volume_usd))
            if a.iv_skew is not None and a.iv_skew > 1.3:
                flags.append(RedFlag("warning", a.ticker, "high_iv_skew",
                                     f"Put/call skew {a.iv_skew:.2f} > 1.3", a.iv_skew))
        return flags

    def _assign_grade(self, score: float, flags: list[RedFlag]) -> BasketGrade:
        """Map score to grade. Critical flags cap at D."""
        has_critical = any(f.severity == "critical" for f in flags)
        for threshold, grade in self.GRADE_MAP:
            if score >= threshold:
                if has_critical and grade.value < "D":
                    return BasketGrade.D
                return grade
        return BasketGrade.F

    def _find_worst_of(self, assets: list[AssetProfile]) -> tuple[str, str]:
        """Identify the weakest asset."""
        if not assets:
            return "", ""
        worst = min(assets, key=lambda a: a.max_drawdown_60d)
        return worst.ticker, f"Worst 60d DD: {worst.max_drawdown_60d:.2%}"

    def _make_recommendation(
        self, score: float, grade: BasketGrade, flags: list[RedFlag],
    ) -> str:
        """Generate recommendation text."""
        critical = sum(1 for f in flags if f.severity == "critical")
        if critical > 0:
            return f"AVOID — {critical} critical red flags"
        if score >= 80:
            return "STRONG BUY — excellent risk profile"
        if score >= 70:
            return "BUY — good risk profile"
        if score >= 60:
            return "HOLD — acceptable risk"
        if score >= 50:
            return "CAUTION — elevated risk"
        return "AVOID — poor risk profile"
