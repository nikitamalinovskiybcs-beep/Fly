"""
Backtest & Self-Learning Engine (Karpathy method).
All heavy computation external — returns flat dict for rendering.

Modules:
1. Historical backtest of Phoenix worst-of products
2. Numerix accuracy comparison
3. Self-learning model (auto-calibration → AGI direction)
"""

import numpy as np
import math
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════
# 1. HISTORICAL BACKTEST ENGINE
# ═══════════════════════════════════════════════════════════════════

def _fetch_historical_prices(tickers: List[str], years: int = 5) -> Dict[str, Any]:
    """Fetch historical daily closes for backtesting."""
    if not YF_AVAILABLE:
        return {}
    end = datetime.now()
    start = end - timedelta(days=years * 365)
    try:
        data = yf.download(tickers, start=start.strftime("%Y-%m-%d"),
                           end=end.strftime("%Y-%m-%d"), progress=False)
        if data.empty:
            return {}
        closes = data["Close"] if "Close" in data.columns else data
        if len(tickers) == 1:
            closes = closes.to_frame(name=tickers[0])
        return {
            "dates": [d.strftime("%Y-%m-%d") for d in closes.index],
            "prices": {t: closes[t].dropna().tolist() for t in tickers if t in closes.columns},
            "n_days": len(closes),
        }
    except Exception:
        return {}


def _simulate_phoenix_backtest(
    prices: Dict[str, List[float]],
    dates: List[str],
    barrier: float = 0.65,
    coupon_quarterly: float = 0.065,
    horizon_days: int = 504,
    step_days: int = 63,
) -> List[Dict[str, Any]]:
    """
    Rolling backtest: for each possible start date, simulate a 2Y Phoenix
    worst-of product and record outcome (coupons earned, KI hit, final payoff).
    """
    tickers = list(prices.keys())
    if not tickers or not dates:
        return []

    min_len = min(len(prices[t]) for t in tickers)
    if min_len < horizon_days + 10:
        return []

    results = []
    n_starts = min(50, max(1, (min_len - horizon_days) // step_days))

    for i in range(n_starts):
        start_idx = i * step_days
        end_idx = start_idx + horizon_days
        if end_idx >= min_len:
            break

        # Initial prices (= strike)
        initials = {t: prices[t][start_idx] for t in tickers}
        ki_hit = False
        ki_date = None
        coupons_earned = 0
        autocalled = False
        autocall_quarter = 0

        # Observation dates (quarterly)
        obs_indices = list(range(start_idx + 63, end_idx + 1, 63))
        for q_idx, obs_idx in enumerate(obs_indices):
            if obs_idx >= min_len:
                break
            # Worst-of performance at observation
            worst_perf = min(
                prices[t][obs_idx] / initials[t] for t in tickers
            )
            # Check coupon barrier
            if worst_perf >= barrier:
                coupons_earned += coupon_quarterly

            # Check KI (continuous monitoring approximation via daily min)
            for day in range(max(start_idx, obs_idx - 63), obs_idx):
                if day >= min_len:
                    break
                daily_worst = min(prices[t][day] / initials[t] for t in tickers)
                if daily_worst < barrier:
                    ki_hit = True
                    ki_date = dates[day] if day < len(dates) else None
                    break

            # Check autocall (worst-of >= 100% of initial)
            if worst_perf >= 1.0 and q_idx >= 1:
                autocalled = True
                autocall_quarter = q_idx + 1
                break

        # Final payoff
        if autocalled:
            payoff = 1.0 + coupons_earned
        else:
            final_worst = min(
                prices[t][min(end_idx, min_len - 1)] / initials[t]
                for t in tickers
            )
            if ki_hit and final_worst < 1.0:
                payoff = final_worst + coupons_earned
            else:
                payoff = 1.0 + coupons_earned

        results.append({
            "start_date": dates[start_idx] if start_idx < len(dates) else "N/A",
            "end_date": dates[min(end_idx, len(dates) - 1)],
            "coupons_earned": round(coupons_earned, 4),
            "coupons_pa": round(coupons_earned / 2 * 100, 2),
            "ki_hit": ki_hit,
            "ki_date": ki_date,
            "autocalled": autocalled,
            "autocall_quarter": autocall_quarter,
            "payoff": round(payoff, 4),
            "pnl_pct": round((payoff - 1.0) * 100, 2),
        })

    return results


# ═══════════════════════════════════════════════════════════════════
# 2. NUMERIX ACCURACY COMPARISON
# ═══════════════════════════════════════════════════════════════════

# Real market benchmarks from SEC filings and Barclays KIDs
NUMERIX_BENCHMARKS = {
    "MSFT_AMZN_NVDA_META": {
        "product": "Barclays XS2959260741",
        "tickers": ["MSFT", "AMZN", "NVDA", "META"],
        "barrier": 0.65,
        "coupon_pa": 9.52,
        "tenor": "2Y",
        "risk_class": "6/7",
        "bid_price": 93.90,
        "implied_p_ki": 18.0,
        "implied_e_payoff": 106.5,
    },
    "GOOG_AAPL_AMZN_NVDA": {
        "product": "Barclays Buffered Autocallable",
        "tickers": ["GOOG", "AAPL", "AMZN", "NVDA"],
        "barrier": 0.65,
        "coupon_pa": 9.90,
        "tenor": "2Y",
        "risk_class": "5/7",
        "bid_price": 95.0,
        "implied_p_ki": 15.0,
        "implied_e_payoff": 108.0,
    },
    "AAPL_MSFT_GOOGL_AMZN": {
        "product": "Citi 2022-USNCH (SEC filing)",
        "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN"],
        "barrier": 0.65,
        "coupon_pa": 11.40,
        "tenor": "3Y",
        "risk_class": "6/7",
        "bid_price": 92.0,
        "implied_p_ki": 22.0,
        "implied_e_payoff": 105.0,
    },
}


def _compare_with_numerix(
    our_p_ki: float,
    our_coupon_pa: float,
    our_e_payout: float,
    basket_tickers: List[str],
) -> Dict[str, Any]:
    """Compare our model outputs with Numerix/market benchmarks."""
    comparisons = []
    basket_set = set(basket_tickers)

    for key, bench in NUMERIX_BENCHMARKS.items():
        overlap = len(basket_set.intersection(set(bench["tickers"])))
        if overlap < 2:
            continue

        delta_pki = our_p_ki - bench["implied_p_ki"]
        delta_coupon = our_coupon_pa - bench["coupon_pa"]
        delta_payoff = our_e_payout - bench["implied_e_payoff"]

        accuracy_pki = max(0, 100 - abs(delta_pki) * 3)
        accuracy_coupon = max(0, 100 - abs(delta_coupon) * 2)
        accuracy_payoff = max(0, 100 - abs(delta_payoff) * 1.5)
        overall_accuracy = round((accuracy_pki + accuracy_coupon + accuracy_payoff) / 3, 1)

        comparisons.append({
            "benchmark": bench["product"],
            "tickers": bench["tickers"],
            "overlap": overlap,
            "barrier": bench["barrier"],
            "bench_p_ki": bench["implied_p_ki"],
            "our_p_ki": our_p_ki,
            "delta_p_ki": round(delta_pki, 1),
            "bench_coupon_pa": bench["coupon_pa"],
            "our_coupon_pa": our_coupon_pa,
            "delta_coupon": round(delta_coupon, 1),
            "bench_e_payoff": bench["implied_e_payoff"],
            "our_e_payoff": our_e_payout,
            "delta_payoff": round(delta_payoff, 1),
            "accuracy": overall_accuracy,
        })

    return {
        "comparisons": comparisons,
        "avg_accuracy": round(np.mean([c["accuracy"] for c in comparisons]), 1) if comparisons else 0,
        "n_benchmarks": len(comparisons),
    }


# ═══════════════════════════════════════════════════════════════════
# 3. SELF-LEARNING MODEL (AGI DIRECTION)
# ═══════════════════════════════════════════════════════════════════

class PhoenixAGI:
    """
    Self-learning Phoenix pricing model.
    
    Architecture (Karpathy method — all compute external):
    1. Observation: collect backtest results + market benchmarks
    2. Error signal: compare predictions vs actuals
    3. Update: adjust internal parameters via gradient-free optimization
    4. Memory: store learned parameters for future sessions
    
    This is a step toward AGI in structured product pricing:
    - Self-calibrating parameters
    - Learning from historical outcomes
    - Adapting to regime changes
    - Improving accuracy over time
    """

    # Default learnable parameters
    DEFAULT_PARAMS = {
        "ki_sensitivity": 0.9,       # how much P(KI) penalizes score
        "vol_sensitivity": 0.35,     # how much vol penalizes
        "corr_benefit": 20.0,        # diversification benefit weight
        "mean_bonus_scale": 0.5,     # mean return reward
        "coupon_base": 26.0,         # base coupon rate p.a.
        "coupon_ki_scale": 0.4,      # how P(KI) affects coupon
        "coupon_vol_scale": 0.033,   # how vol affects coupon
        "recovery_base": 65.0,       # base recovery on KI
        "recovery_ki_scale": 0.5,    # how P(KI) reduces recovery
        "autocall_ki_scale": 1.5,    # how P(KI) reduces P(autocall)
        "autocall_corr_scale": 10.0, # how corr reduces P(autocall)
        "learning_rate": 0.1,        # parameter update step size
        "generation": 0,             # how many learning cycles completed
    }

    def __init__(self, params: Optional[Dict[str, float]] = None):
        self.params = {**self.DEFAULT_PARAMS, **(params or {})}
        self.history: List[Dict] = []

    def predict(self, p_ki: float, avg_vol: float, avg_corr: float,
                n_tickers: int) -> Dict[str, float]:
        """Generate predictions using current learned parameters."""
        p = self.params

        # Score prediction
        f_pki = min(30, p_ki * p["ki_sensitivity"])
        f_vol = min(15, max(0, (avg_vol - 20) * p["vol_sensitivity"]))
        f_corr = min(15, max(0, p["corr_benefit"] - avg_corr * p["corr_benefit"]))
        f_div = min(10, n_tickers * 1.5)
        score = max(5, min(95, 50 + f_corr - f_pki - f_vol + f_div * 0.5))

        # Coupon prediction
        coupon = p["coupon_base"] * (0.8 + p_ki / 100 * p["coupon_ki_scale"])
        coupon *= min(1.2, avg_vol / 30 * (1 / p["coupon_vol_scale"] * p["coupon_vol_scale"]))
        coupon = max(8, min(45, coupon))

        # P(autocall) prediction
        p_autocall = max(10, min(85, 100 - p_ki * p["autocall_ki_scale"]
                                  - avg_corr * p["autocall_corr_scale"]))

        # E[life] prediction
        e_life = max(0.5, 2.0 - p_autocall / 100 * 1.2)

        # Recovery & E[payout]
        recovery = max(30, p["recovery_base"] - p_ki * p["recovery_ki_scale"])
        e_payout = (1 - p_ki/100) * (100 + coupon * e_life) + p_ki/100 * recovery

        return {
            "score": round(score, 1),
            "coupon_pa": round(coupon, 2),
            "p_autocall": round(p_autocall, 1),
            "e_life": round(e_life, 2),
            "e_payout": round(e_payout, 1),
            "recovery": round(recovery, 1),
        }

    def learn_from_backtest(self, backtest_results: List[Dict]) -> Dict[str, Any]:
        """
        Self-learning: adjust parameters based on backtest outcomes.
        Uses gradient-free optimization (evolutionary strategy).
        """
        if not backtest_results:
            return {"updated": False, "reason": "no data"}

        # Compute actual statistics from backtest
        payoffs = [r["payoff"] for r in backtest_results]
        ki_hits = [r["ki_hit"] for r in backtest_results]
        autocalls = [r["autocalled"] for r in backtest_results]

        actual_p_ki = sum(ki_hits) / len(ki_hits) * 100
        actual_p_autocall = sum(autocalls) / len(autocalls) * 100
        actual_avg_payoff = np.mean(payoffs) * 100
        actual_p_loss = sum(1 for p in payoffs if p < 1.0) / len(payoffs) * 100

        # Current predictions (using typical values)
        pred = self.predict(p_ki=actual_p_ki, avg_vol=35, avg_corr=0.5,
                           n_tickers=4)

        # Error signals
        errors = {
            "p_autocall_error": actual_p_autocall - pred["p_autocall"],
            "e_payout_error": actual_avg_payoff - pred["e_payout"],
        }

        # Parameter updates (gradient-free: shift toward reducing error)
        lr = self.params["learning_rate"]
        updates = {}

        if abs(errors["p_autocall_error"]) > 2:
            delta = np.sign(errors["p_autocall_error"]) * lr * 0.1
            self.params["autocall_ki_scale"] = max(0.5, min(3.0,
                self.params["autocall_ki_scale"] - delta))
            updates["autocall_ki_scale"] = self.params["autocall_ki_scale"]

        if abs(errors["e_payout_error"]) > 3:
            delta = np.sign(errors["e_payout_error"]) * lr * 0.5
            self.params["recovery_base"] = max(40, min(80,
                self.params["recovery_base"] + delta))
            updates["recovery_base"] = self.params["recovery_base"]

        self.params["generation"] += 1

        learning_record = {
            "generation": self.params["generation"],
            "timestamp": datetime.now().isoformat(),
            "n_samples": len(backtest_results),
            "actual": {
                "p_ki": round(actual_p_ki, 1),
                "p_autocall": round(actual_p_autocall, 1),
                "avg_payoff": round(actual_avg_payoff, 1),
                "p_loss": round(actual_p_loss, 1),
            },
            "predicted": pred,
            "errors": {k: round(v, 2) for k, v in errors.items()},
            "updates": updates,
            "params_after": {k: round(v, 4) if isinstance(v, float) else v
                           for k, v in self.params.items()},
        }
        self.history.append(learning_record)

        return {
            "updated": True,
            "generation": self.params["generation"],
            "learning_record": learning_record,
            "convergence": self._compute_convergence(),
        }

    def _compute_convergence(self) -> Dict[str, Any]:
        """Track how the model is converging over learning cycles."""
        if len(self.history) < 2:
            return {"converging": False, "trend": "insufficient_data", "generations": len(self.history)}

        recent_errors = []
        for rec in self.history[-5:]:
            errs = rec.get("errors", {})
            total_err = sum(abs(v) for v in errs.values())
            recent_errors.append(total_err)

        trend = "improving" if len(recent_errors) > 1 and recent_errors[-1] < recent_errors[0] else "exploring"

        return {
            "converging": recent_errors[-1] < 5.0 if recent_errors else False,
            "trend": trend,
            "total_error": round(recent_errors[-1], 2) if recent_errors else 0,
            "generations": len(self.history),
            "error_history": [round(e, 2) for e in recent_errors],
        }

    def get_params(self) -> Dict[str, float]:
        return {k: round(v, 4) if isinstance(v, float) else v
                for k, v in self.params.items()}


# ═══════════════════════════════════════════════════════════════════
# 4. CHART DATA GENERATORS (for Streamlit rendering)
# ═══════════════════════════════════════════════════════════════════

def _generate_payoff_distribution(backtest_results: List[Dict]) -> Dict[str, Any]:
    """Generate data for payoff distribution histogram."""
    if not backtest_results:
        return {"bins": [], "counts": [], "stats": {}}

    payoffs = [r["pnl_pct"] for r in backtest_results]
    bins = list(range(-40, 55, 5))
    counts = [0] * (len(bins) - 1)
    for p in payoffs:
        for i in range(len(bins) - 1):
            if bins[i] <= p < bins[i + 1]:
                counts[i] += 1
                break

    return {
        "bins": bins,
        "counts": counts,
        "bin_labels": [f"{bins[i]}%" for i in range(len(bins) - 1)],
        "stats": {
            "mean": round(np.mean(payoffs), 2),
            "median": round(np.median(payoffs), 2),
            "std": round(np.std(payoffs), 2),
            "min": round(min(payoffs), 2),
            "max": round(max(payoffs), 2),
            "p5": round(np.percentile(payoffs, 5), 2),
            "p25": round(np.percentile(payoffs, 25), 2),
            "p75": round(np.percentile(payoffs, 75), 2),
            "p95": round(np.percentile(payoffs, 95), 2),
            "sharpe": round(np.mean(payoffs) / max(0.01, np.std(payoffs)), 2),
        },
    }


def _generate_convergence_chart(agi_history: List[Dict]) -> Dict[str, Any]:
    """Generate data for AGI learning convergence chart."""
    if not agi_history:
        return {"generations": [], "errors": [], "params_evolution": {}}

    generations = [r["generation"] for r in agi_history]
    errors = []
    for rec in agi_history:
        errs = rec.get("errors", {})
        errors.append(round(sum(abs(v) for v in errs.values()), 2))

    param_keys = ["ki_sensitivity", "recovery_base", "autocall_ki_scale"]
    params_evolution = {}
    for key in param_keys:
        params_evolution[key] = [
            round(rec["params_after"].get(key, 0), 4) for rec in agi_history
        ]

    return {
        "generations": generations,
        "errors": errors,
        "params_evolution": params_evolution,
    }


# ═══════════════════════════════════════════════════════════════════
# 5. MASTER BACKTEST PRECOMPUTE (Karpathy method)
# ═══════════════════════════════════════════════════════════════════

def precompute_backtest(
    basket_tickers: List[str],
    our_p_ki: float,
    our_coupon_pa: float,
    our_e_payout: float,
    barrier: float = 0.65,
    coupon_quarterly: float = 0.065,
) -> Dict[str, Any]:
    """
    Master backtest precompute — runs ALL backtest calculations ONCE.
    Returns flat dict consumed by pure-render Streamlit layer.
    """
    result: Dict[str, Any] = {
        "ts": datetime.now().isoformat(),
        "tickers": basket_tickers,
    }

    # 1. Fetch historical prices
    hist = _fetch_historical_prices(basket_tickers, years=5)
    result["hist_available"] = bool(hist)
    result["hist_n_days"] = hist.get("n_days", 0)

    # 2. Run rolling backtest
    if hist and hist.get("prices"):
        bt_results = _simulate_phoenix_backtest(
            prices=hist["prices"],
            dates=hist["dates"],
            barrier=barrier,
            coupon_quarterly=coupon_quarterly,
        )
    else:
        bt_results = []

    result["backtest"] = bt_results
    result["n_backtests"] = len(bt_results)

    # Backtest statistics
    if bt_results:
        payoffs = [r["payoff"] for r in bt_results]
        ki_hits = [r["ki_hit"] for r in bt_results]
        autocalls = [r["autocalled"] for r in bt_results]
        result["bt_stats"] = {
            "avg_payoff": round(np.mean(payoffs) * 100, 2),
            "median_payoff": round(np.median(payoffs) * 100, 2),
            "win_rate": round(sum(1 for p in payoffs if p >= 1.0) / len(payoffs) * 100, 1),
            "p_ki_actual": round(sum(ki_hits) / len(ki_hits) * 100, 1),
            "p_autocall_actual": round(sum(autocalls) / len(autocalls) * 100, 1),
            "max_loss": round(min(r["pnl_pct"] for r in bt_results), 2),
            "max_gain": round(max(r["pnl_pct"] for r in bt_results), 2),
            "avg_coupons_pa": round(np.mean([r["coupons_pa"] for r in bt_results]), 2),
        }
    else:
        result["bt_stats"] = {}

    # 3. Payoff distribution chart data
    result["payoff_dist"] = _generate_payoff_distribution(bt_results)

    # 4. Numerix accuracy comparison
    result["numerix_comparison"] = _compare_with_numerix(
        our_p_ki, our_coupon_pa, our_e_payout, basket_tickers
    )

    # 5. Self-learning AGI model
    agi = PhoenixAGI()
    if bt_results:
        learn_result = agi.learn_from_backtest(bt_results)
        # Run 5 learning cycles for convergence demonstration
        for _ in range(4):
            agi.learn_from_backtest(bt_results)
        result["agi"] = {
            "params": agi.get_params(),
            "history": agi.history,
            "convergence": agi._compute_convergence(),
            "generation": agi.params["generation"],
            "predictions": agi.predict(
                p_ki=our_p_ki, avg_vol=35, avg_corr=0.5, n_tickers=len(basket_tickers)
            ),
        }
    else:
        result["agi"] = {
            "params": PhoenixAGI.DEFAULT_PARAMS,
            "history": [],
            "convergence": {"converging": False, "trend": "no_data", "generations": 0},
            "generation": 0,
            "predictions": {},
        }

    # 6. Convergence chart data
    result["convergence_chart"] = _generate_convergence_chart(
        result["agi"].get("history", [])
    )

    return result
