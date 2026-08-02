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

# Preset baskets for quick testing / demos, ordered from low to high risk.
SAMPLE_BASKETS: dict[str, list[str]] = {
    "Mega-Cap Quality": ["AAPL", "MSFT", "JNJ"],
    "US Banks": ["JPM", "BAC", "WFC"],
    "Big Energy": ["XOM", "CVX", "COP"],
    "High-Beta Tech": ["NVDA", "TSLA", "AMD"],
    "Speculative": ["PLUG", "RIOT", "AMC"],
}


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

    @staticmethod
    def _interp(x: float, points: list[tuple[float, float]]) -> float:
        """Piecewise-linear interpolation over (input, score) anchor points.

        ``points`` must be sorted ascending by input. Values outside the range
        are clamped to the nearest anchor. This replaces coarse step buckets so
        small input differences map to smoothly varying scores (wider spread).
        """
        if not points:
            return 0.0
        if x <= points[0][0]:
            return points[0][1]
        if x >= points[-1][0]:
            return points[-1][1]
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            if x0 <= x <= x1:
                if x1 == x0:
                    return y1
                frac = (x - x0) / (x1 - x0)
                return y0 + frac * (y1 - y0)
        return points[-1][1]

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
        history = self._fetch_history_batch(tickers)
        assets = self._build_profiles(tickers, history, strikes, barrier_pct)
        returns_df = self._get_returns(tickers, history)
        return self.score_profiles(assets, returns_df, basket_name="-".join(tickers))

    def score_profiles(
        self,
        assets: list[AssetProfile],
        returns_df: pd.DataFrame = None,
        basket_name: str = "",
    ) -> BasketReport:
        """Score pre-built asset profiles (no network I/O).

        Splitting scoring from fetching makes the scorer deterministic and
        testable, and lets callers score custom/injected profiles.
        """
        if returns_df is None:
            returns_df = pd.DataFrame()
        tickers = [a.ticker for a in assets]

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
            basket_name=basket_name or "-".join(tickers),
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

    def _fetch_history_batch(
        self, tickers: list[str], retries: int = 3,
    ) -> dict[str, pd.DataFrame]:
        """Download 6mo OHLCV for all tickers in one batched call, with retry.

        Batching (one request for the whole basket) plus exponential backoff
        greatly reduces yfinance rate-limiting versus per-ticker requests.
        Returns a dict ticker -> OHLCV DataFrame (may be empty on failure).
        """
        if not tickers:
            return {}
        try:
            import time

            import yfinance as yf
        except ImportError:
            return {}

        for attempt in range(retries):
            try:
                raw = yf.download(
                    tickers, period="6mo", interval="1d",
                    progress=False, group_by="ticker", auto_adjust=True,
                    threads=True,
                )
                out: dict[str, pd.DataFrame] = {}
                if raw is None or raw.empty:
                    raise ValueError("empty download")
                for t in tickers:
                    try:
                        df = raw[t] if len(tickers) > 1 else raw
                        if df is not None and not df.dropna(how="all").empty:
                            out[t] = df.dropna(how="all")
                    except (KeyError, TypeError):
                        continue
                if out:
                    return out
            except Exception as exc:
                logger.info("Batch history attempt %d failed: %s", attempt + 1, exc)
            time.sleep(1.5 * (attempt + 1))
        return {}

    def _build_profiles(
        self,
        tickers: list[str],
        history: dict[str, pd.DataFrame],
        strikes: dict[str, float] = None,
        barrier_pct: float = 0.60,
    ) -> list[AssetProfile]:
        """Build AssetProfile for each ticker."""
        profiles = []
        for ticker in tickers:
            profile = self._fetch_profile(ticker, history.get(ticker))
            if strikes and ticker in strikes:
                strike = strikes[ticker]
                if profile.price > 0:
                    profile.distance_to_strike_pct = (profile.price - strike) / strike
                    barrier = strike * barrier_pct
                    profile.distance_to_barrier_pct = (profile.price - barrier) / barrier
            profiles.append(profile)
        return profiles

    def _fetch_profile(
        self, ticker: str, hist: pd.DataFrame = None,
    ) -> AssetProfile:
        """Build a profile from batched price history + best-effort fundamentals.

        Price-derived metrics (price, volume, ATR, drawdown, tail VaR, RSI) come
        from the batched history so they populate even when the rate-limited
        ``.info`` endpoint is unavailable. Fundamentals are best-effort.
        """
        price = 0.0
        volume = 0.0
        atr_pct = 0.0
        max_dd = 0.0
        evt_var = 0.0
        rsi_val = 50.0

        if hist is not None and not hist.empty and "Close" in hist:
            close = hist["Close"].dropna()
            if len(close) > 0:
                price = float(close.iloc[-1])
                if "Volume" in hist:
                    dollar_vol = (hist["Close"] * hist["Volume"]).dropna()
                    if len(dollar_vol) > 0:
                        volume = float(dollar_vol.tail(20).mean())
                returns = close.pct_change().dropna()
                if len(returns) > 5:
                    atr_pct = float(returns.std() * np.sqrt(252))
                if len(returns) > 0:
                    cumulative = (1 + returns).cumprod()
                    peak = cumulative.expanding().max()
                    dd = (cumulative - peak) / peak
                    max_dd = float(dd.min()) if len(dd) > 0 else 0.0
                if len(returns) > 20:
                    evt_var = float(np.percentile(returns, 5))

                delta = close.diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss.replace(0, np.nan)
                rsi_series = 100 - 100 / (1 + rs)
                if not rsi_series.empty and not np.isnan(rsi_series.iloc[-1]):
                    rsi_val = float(rsi_series.iloc[-1])

        market_cap = 0.0
        pe = None
        net_margin = None
        sector = "Unknown"
        is_profitable = True
        try:
            import yfinance as yf
            info = yf.Ticker(ticker).info
            if info:
                market_cap = float(info.get("marketCap", 0) or 0)
                pe = info.get("trailingPE")
                net_margin = info.get("profitMargins")
                sector = info.get("sector", "Unknown") or "Unknown"
                if net_margin is not None:
                    is_profitable = net_margin > 0
                if price == 0:
                    price = float(info.get("regularMarketPrice",
                                           info.get("previousClose", 0)) or 0)
                if volume == 0:
                    volume = float(info.get("averageVolume", 0) or 0) * price
        except Exception as exc:
            logger.info("Fundamentals unavailable for %s: %s", ticker, exc)

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
            pe_ratio=pe, net_margin=net_margin, is_profitable=is_profitable,
            daily_volume_usd=volume, atr_pct=atr_pct,
            evt_var_95=evt_var, max_drawdown_60d=max_dd,
            sector=sector, implied_vol=iv, iv_skew=skew, rsi=rsi_val,
        )

    def _get_returns(
        self, tickers: list[str], history: dict[str, pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Get returns DataFrame for correlation analysis from batched history."""
        if history is None:
            history = self._fetch_history_batch(tickers)
        data = {}
        for t in tickers:
            df = history.get(t)
            if df is not None and not df.empty and "Close" in df:
                data[t] = df["Close"].pct_change().dropna()
        if data:
            return pd.DataFrame(data).dropna()
        return pd.DataFrame()

    def _score_liquidity(self, assets: list[AssetProfile]) -> CriterionScore:
        """Min daily volume across basket. Higher volume = better score."""
        min_vol = min((a.daily_volume_usd for a in assets), default=0)
        log_vol = np.log10(max(min_vol, 1.0))
        raw = self._interp(log_vol, [
            (6.0, 15),    # $1M
            (7.0, 50),    # $10M
            (7.3, 65),    # $20M
            (7.7, 80),    # $50M
            (8.0, 90),    # $100M
            (8.7, 98),    # $500M
        ])
        w = self.WEIGHTS["liquidity"]
        return CriterionScore("liquidity", w, raw, round(raw * w, 2),
                              f"Min vol: ${min_vol:,.0f}")

    def _score_fundamental(self, assets: list[AssetProfile]) -> CriterionScore:
        """Profitability + P/E + margins. Penalty per unprofitable."""
        n = max(len(assets), 1)
        unprofitable = sum(1 for a in assets if not a.is_profitable)
        base = 82 - (unprofitable / n) * 55

        margins = [a.net_margin for a in assets if a.net_margin is not None]
        if margins:
            avg_margin = float(np.mean(margins))
            base += self._interp(avg_margin, [
                (-0.10, -12), (0.0, -4), (0.10, 3), (0.20, 8), (0.35, 14),
            ])

        pe_vals = [a.pe_ratio for a in assets if a.pe_ratio and 0 < a.pe_ratio < 100]
        if pe_vals:
            avg_pe = float(np.mean(pe_vals))
            base += self._interp(avg_pe, [
                (8, 10), (15, 6), (20, 2), (30, -3), (40, -8), (70, -14),
            ])

        raw = max(0.0, min(100.0, base))
        w = self.WEIGHTS["fundamental"]
        return CriterionScore("fundamental", w, raw, round(raw * w, 2),
                              f"Unprofitable: {unprofitable}")

    def _score_worst_of_tail_risk(
        self, assets: list[AssetProfile], returns_df: pd.DataFrame,
    ) -> CriterionScore:
        """EVT VaR of worst asset. Lower tail risk = higher score."""
        worst_var = min((a.evt_var_95 for a in assets), default=0)
        abs_var = abs(worst_var)
        raw = self._interp(abs_var, [
            (0.00, 96), (0.02, 84), (0.04, 66), (0.06, 48), (0.10, 22), (0.15, 8),
        ])
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
            raw = self._interp(crisis_corr, [
                (0.0, 96), (0.3, 80), (0.5, 62), (0.7, 42), (0.9, 20), (1.0, 12),
            ])

        w = self.WEIGHTS["crisis_correlation"]
        return CriterionScore("crisis_correlation", w, raw, round(raw * w, 2),
                              f"Crisis corr: {crisis_corr:.4f}")

    def _score_max_drawdown(self, assets: list[AssetProfile]) -> CriterionScore:
        """Worst 60d drawdown of worst asset."""
        worst_dd = min((a.max_drawdown_60d for a in assets), default=0)
        abs_dd = abs(worst_dd)
        raw = self._interp(abs_dd, [
            (0.0, 95), (0.10, 82), (0.20, 64), (0.30, 42), (0.50, 18), (0.70, 6),
        ])
        w = self.WEIGHTS["max_drawdown_worst_of"]
        return CriterionScore("max_drawdown_worst_of", w, raw, round(raw * w, 2),
                              f"Worst DD: {worst_dd:.2%}")

    def _score_sector_diversification(self, assets: list[AssetProfile]) -> CriterionScore:
        """Unique sectors + mainstream bonus."""
        from src.basket import sector as sec
        sectors = [a.sector for a in assets]
        unique = sec.unique_sector_count(sectors)
        mainstream = sum(1 for s in sectors if sec.is_mainstream(s))

        n = max(len(assets), 1)
        concentration = unique / n  # 1.0 = fully diversified
        base = self._interp(concentration, [
            (0.34, 25), (0.5, 45), (0.67, 62), (0.8, 75), (1.0, 88),
        ])
        base += min(mainstream * 3.5, 12)
        raw = min(100.0, base)

        w = self.WEIGHTS["sector_diversification"]
        return CriterionScore("sector_diversification", w, raw, round(raw * w, 2),
                              f"Sectors: {unique}, mainstream: {mainstream}")

    def _score_implied_vol_risk(self, assets: list[AssetProfile]) -> CriterionScore:
        """IV percentile vs 1y range. High IV = low score."""
        iv_vals = [a.implied_vol for a in assets if a.implied_vol is not None]
        if not iv_vals:
            raw = 60
        else:
            avg_iv = float(np.mean(iv_vals))
            raw = self._interp(avg_iv, [
                (0.10, 95), (0.20, 82), (0.30, 64), (0.40, 46), (0.60, 22), (0.90, 8),
            ])

            skew_vals = [a.iv_skew for a in assets if a.iv_skew is not None]
            if skew_vals:
                raw -= self._interp(max(skew_vals), [(1.0, 0), (1.3, 6), (1.8, 16)])
                raw = max(0.0, raw)

        w = self.WEIGHTS["implied_vol_risk"]
        return CriterionScore("implied_vol_risk", w, raw, round(raw * w, 2),
                              f"Avg IV: {np.mean(iv_vals):.4f}" if iv_vals else "No IV data")

    def _score_greeks_exposure(self, assets: list[AssetProfile]) -> CriterionScore:
        """Score based on realized vol and IV: lower combined risk = higher score."""
        iv_vals = [a.implied_vol for a in assets if a.implied_vol is not None and a.implied_vol > 0]
        atr_vals = [a.atr_pct for a in assets if a.atr_pct > 0]

        if not iv_vals and not atr_vals:
            raw = 60
            detail = "No vol data"
        else:
            avg_iv = float(np.mean(iv_vals)) if iv_vals else 0.3
            max_atr = max(atr_vals) if atr_vals else 0.05
            vega_proxy = avg_iv * 100
            barrier_delta_proxy = max_atr * 100

            combined = vega_proxy * 0.6 + barrier_delta_proxy * 0.4

            raw = self._interp(combined, [
                (10, 92), (15, 85), (25, 70), (35, 55), (45, 40), (60, 25),
                (80, 12), (100, 5),
            ])

            detail = f"Vega proxy: {vega_proxy:.1f}, barrier delta: {barrier_delta_proxy:.1f}"

        w = self.WEIGHTS["greeks_exposure"]
        return CriterionScore("greeks_exposure", w, raw, round(raw * w, 2), detail)

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
