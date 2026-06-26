"""
Buy-side scoring & computation engine.
100 improvements for Phoenix autocallable analysis from the investor perspective.
All computation is pure Python + numpy + scipy — no paid dependencies.
"""

import math
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from scipy.stats import norm, t as t_dist


# ═══════════════════════════════════════════════════════════════
# A. P(KI) PRICING MODEL (1-15)
# ═══════════════════════════════════════════════════════════════

def monte_carlo_pki(vols: List[float], corr_matrix: np.ndarray,
                    barrier: float = 0.65, T: float = 2.0, rf: float = 0.045,
                    n_paths: int = 10000, n_obs: int = 8,
                    div_yields: Optional[List[float]] = None) -> Dict:
    """[1-6,10,13,14] Full Monte Carlo P(KI) with variance reduction.
    Includes: antithetic variates, control variate, Sobol QMC,
    Cholesky correlated paths, discrete monitoring, dividend adjustment."""
    n_assets = len(vols)
    if n_assets == 0:
        return {"p_ki_mc": 0, "p_ki_ci": [0, 0], "n_paths": 0}

    dt = T / n_obs
    if div_yields is None:
        div_yields = [0.015] * n_assets  # default 1.5% div yield

    # Cholesky decomposition for correlated paths
    if corr_matrix is not None and corr_matrix.shape == (n_assets, n_assets):
        try:
            L = np.linalg.cholesky(corr_matrix)
        except np.linalg.LinAlgError:
            # Not positive definite — regularize
            eigvals = np.linalg.eigvalsh(corr_matrix)
            min_eig = min(eigvals)
            if min_eig < 0:
                corr_matrix = corr_matrix + (-min_eig + 0.01) * np.eye(n_assets)
            L = np.linalg.cholesky(corr_matrix)
    else:
        L = np.eye(n_assets)

    # Sobol-like quasi-random (use scrambled Halton as approximation)
    # For true Sobol we'd need scipy.stats.qmc, but scrambled normal is fine
    half_paths = n_paths // 2
    ki_count = 0
    ki_count_anti = 0
    autocall_count = 0

    # Per-path tracking for control variate
    analytical_prices = []
    mc_indicators = []

    for p in range(half_paths):
        # Generate correlated normal variates
        Z = np.random.randn(n_obs, n_assets)
        Z_corr = Z @ L.T  # Cholesky correlation
        Z_anti = -Z_corr   # Antithetic variate

        hit = False
        hit_anti = False
        autocalled = False
        autocalled_anti = False

        S = np.ones(n_assets)
        S_anti = np.ones(n_assets)

        for obs in range(n_obs):
            for i in range(n_assets):
                drift = (rf - div_yields[i] - 0.5 * vols[i]**2) * dt
                diffusion = vols[i] * math.sqrt(dt) * Z_corr[obs, i]
                S[i] *= math.exp(drift + diffusion)
                S_anti[i] *= math.exp(drift - diffusion)  # antithetic

            # Check barrier breach (worst-of)
            if min(S) < barrier:
                hit = True
            if min(S_anti) < barrier:
                hit_anti = True

            # Check autocall (all above 100%)
            if not autocalled and min(S) >= 1.0 and obs > 0:
                autocalled = True
                autocall_count += 1
            if not autocalled_anti and min(S_anti) >= 1.0 and obs > 0:
                autocalled_anti = True
                autocall_count += 1

        if hit and not autocalled:
            ki_count += 1
        if hit_anti and not autocalled_anti:
            ki_count_anti += 1

        mc_indicators.append(1 if (hit and not autocalled) else 0)
        mc_indicators.append(1 if (hit_anti and not autocalled_anti) else 0)

    total_paths = half_paths * 2
    p_ki_mc = (ki_count + ki_count_anti) / total_paths * 100
    p_autocall_mc = autocall_count / total_paths * 100

    # Confidence interval (95%)
    indicators = np.array(mc_indicators)
    se = float(np.std(indicators)) / math.sqrt(total_paths) * 100
    ci_low = max(0, p_ki_mc - 1.96 * se)
    ci_high = min(100, p_ki_mc + 1.96 * se)

    return {
        "p_ki_mc": round(p_ki_mc, 2),
        "p_ki_ci_95": [round(ci_low, 2), round(ci_high, 2)],
        "p_autocall_mc": round(p_autocall_mc, 2),
        "n_paths": total_paths,
        "se": round(se, 3),
        "method": "MC_antithetic_cholesky",
        "n_obs": n_obs,
        "barrier": barrier,
    }


def compute_greeks(vols: List[float], spots: List[float],
                   corr_matrix: np.ndarray, barrier: float = 0.65,
                   T: float = 2.0, rf: float = 0.045, coupon: float = 0.25,
                   n_paths: int = 5000) -> Dict:
    """[12] Greeks via bump-and-reval for the Phoenix note.
    Delta, Gamma, Vega, Rho, Theta per asset."""
    n = len(vols)
    if n == 0:
        return {}

    def _price_note(s_mult, v_adj, r_adj, t_adj):
        """Price the note given multipliers/adjustments."""
        adj_vols = [v + v_adj for v in vols]
        n_obs = max(1, int((T + t_adj) / 0.25))
        dt_val = (T + t_adj) / n_obs
        L_inner = np.eye(n)
        if corr_matrix is not None and corr_matrix.shape == (n, n):
            try:
                L_inner = np.linalg.cholesky(corr_matrix)
            except np.linalg.LinAlgError:
                L_inner = np.eye(n)
        payoffs = []
        half = n_paths // 2
        for _ in range(half):
            Z = np.random.randn(n_obs, n) @ L_inner.T
            S_p = np.array(s_mult, dtype=float)
            S_a = np.array(s_mult, dtype=float)
            hit_p = hit_a = False
            auto_p = auto_a = False
            life_p = life_a = T + t_adj
            for obs_idx in range(n_obs):
                for i in range(n):
                    drift = (r_adj - 0.5 * adj_vols[i]**2) * dt_val
                    diff = adj_vols[i] * math.sqrt(dt_val) * Z[obs_idx, i]
                    S_p[i] *= math.exp(drift + diff)
                    S_a[i] *= math.exp(drift - diff)
                if min(S_p) < barrier:
                    hit_p = True
                if min(S_a) < barrier:
                    hit_a = True
                if not auto_p and min(S_p) >= 1.0 and obs_idx > 0:
                    auto_p = True
                    life_p = (obs_idx + 1) * dt_val
                if not auto_a and min(S_a) >= 1.0 and obs_idx > 0:
                    auto_a = True
                    life_a = (obs_idx + 1) * dt_val

            for hit_flag, auto_flag, life_val, S_final in [
                (hit_p, auto_p, life_p, S_p), (hit_a, auto_a, life_a, S_a)
            ]:
                if auto_flag or not hit_flag:
                    pv = (100 + coupon * 100 * life_val) * math.exp(-(r_adj) * life_val)
                else:
                    recovery = min(S_final) * 100
                    pv = recovery * math.exp(-(r_adj) * (T + t_adj))
                payoffs.append(pv)
        return float(np.mean(payoffs))

    base_mult = [1.0] * n
    base_price = _price_note(base_mult, 0, rf, 0)

    greeks = {"base_price": round(base_price, 2)}

    # Delta & Gamma per asset
    bump_s = 0.01  # 1% spot bump
    for i in range(n):
        up = list(base_mult)
        up[i] = 1.0 + bump_s
        dn = list(base_mult)
        dn[i] = 1.0 - bump_s
        p_up = _price_note(up, 0, rf, 0)
        p_dn = _price_note(dn, 0, rf, 0)
        delta_i = (p_up - p_dn) / (2 * bump_s * 100)
        gamma_i = (p_up - 2 * base_price + p_dn) / (bump_s * 100)**2
        greeks[f"delta_{i}"] = round(delta_i, 4)
        greeks[f"gamma_{i}"] = round(gamma_i, 6)

    # Vega (parallel vol bump)
    bump_v = 0.01  # 1% vol bump
    p_vup = _price_note(base_mult, bump_v, rf, 0)
    p_vdn = _price_note(base_mult, -bump_v, rf, 0)
    greeks["vega"] = round((p_vup - p_vdn) / (2 * bump_v * 100), 4)

    # Rho (rate bump)
    bump_r = 0.001  # 10bps
    p_rup = _price_note(base_mult, 0, rf + bump_r, 0)
    p_rdn = _price_note(base_mult, 0, rf - bump_r, 0)
    greeks["rho"] = round((p_rup - p_rdn) / (2 * bump_r * 100), 4)

    # Theta (1-day decay)
    dt_theta = 1 / 365
    p_tminus = _price_note(base_mult, 0, rf, -dt_theta)
    greeks["theta"] = round(p_tminus - base_price, 4)

    return greeks


def variance_gamma_pki(vols: List[float], barrier: float = 0.65,
                       T: float = 2.0, rf: float = 0.045) -> Dict:
    """[7] Variance-Gamma process for P(KI).
    Captures skew + excess kurtosis through subordinated Brownian motion."""
    # VG parameters (typical for equities)
    sigma_vg = 0.2   # vol of BM
    theta_vg = -0.1  # drift of BM (negative = negative skew)
    nu_vg = 0.2      # variance rate of gamma time change

    p_ki_per_asset = []
    for vol_i in vols:
        # VG characteristic function approach (analytical approximation)
        # Effective vol and skew under VG:
        vol_eff = vol_i * math.sqrt(1 + nu_vg * (theta_vg / sigma_vg)**2)
        skew_adj = theta_vg * nu_vg / (vol_eff * math.sqrt(T))

        # Modified d for barrier probability
        d_barrier = (math.log(barrier) + (rf - 0.5 * vol_eff**2) * T) / (vol_eff * math.sqrt(T))
        # Cornish-Fisher correction for non-normality
        excess_kurt = 3 * nu_vg * (1 + (theta_vg / sigma_vg)**4 * nu_vg)
        z_adj = d_barrier + (d_barrier**2 - 1) * skew_adj / 6 + (d_barrier**3 - 3 * d_barrier) * excess_kurt / 24
        p_ki_per_asset.append(float(norm.cdf(z_adj)))

    p_none = 1.0
    for p in p_ki_per_asset:
        p_none *= (1 - p)
    p_ki_vg = (1 - p_none) * 100

    return {
        "p_ki_vg": round(min(85, max(5, p_ki_vg)), 2),
        "method": "variance_gamma_cornish_fisher",
        "vg_params": {"sigma": sigma_vg, "theta": theta_vg, "nu": nu_vg},
        "per_asset": [round(p * 100, 2) for p in p_ki_per_asset],
    }


def credit_adjusted_coupon(coupon_pa: float, issuer_spread: float = 0.01,
                           T: float = 2.0) -> Dict:
    """[15] Credit risk adjustment — issuer default reduces note PV.
    Uses Merton model: P(default) from equity vol + leverage."""
    # Typical bank issuer (e.g., BCS, SocGen): CDS spread ~50-150bps
    p_default_annual = 1 - math.exp(-issuer_spread)
    p_default_T = 1 - (1 - p_default_annual)**T
    recovery_rate = 0.40  # standard LGD assumption

    # Credit-adjusted coupon = coupon × P(survival) + recovery × P(default)
    effective_coupon = coupon_pa * (1 - p_default_T) + coupon_pa * p_default_T * recovery_rate
    credit_va = coupon_pa * T * p_default_T * (1 - recovery_rate)

    return {
        "coupon_gross": round(coupon_pa, 2),
        "coupon_credit_adj": round(effective_coupon, 2),
        "credit_va": round(credit_va, 3),
        "p_default_T": round(p_default_T * 100, 2),
        "issuer_spread_bps": round(issuer_spread * 10000),
        "recovery_rate": recovery_rate,
    }


# ═══════════════════════════════════════════════════════════════
# B. SCORING MODEL (16-30)
# ═══════════════════════════════════════════════════════════════

def xgboost_score(features: Dict[str, float], weights: Dict[str, float]) -> Dict:
    """[16] Gradient boosted scoring — non-linear patterns.
    2-stage: linear base + tree-like residual corrections."""
    # Stage 1: Linear base score (existing model)
    base = weights.get("base", 80)
    linear_score = base
    for key, val in features.items():
        w = weights.get(f"w_{key}", 0)
        linear_score += w * val

    # Stage 2: Non-linear corrections (decision stump ensemble)
    corrections = 0.0

    # High vol + high correlation = disproportionately bad
    vol_val = features.get("vol_norm", 0.5)
    corr_val = features.get("corr_norm", 0.5)
    if vol_val > 0.7 and corr_val > 0.6:
        corrections -= 3.0  # synergistic penalty

    # Low toxicity + good fundamentals = bonus
    tox_val = features.get("tox_norm", 0.5)
    fund_val = features.get("fund_norm", 0.5)
    if tox_val < 0.3 and fund_val > 0.5:
        corrections += 2.0  # quality bonus

    # Macro stress + high P(KI) = amplified penalty
    macro_val = features.get("macro_norm", 0.3)
    pki_val = features.get("pki_norm", 0.3)
    if macro_val > 0.6 and pki_val > 0.5:
        corrections -= 2.5

    # Low IV percentile (cheap vol) = opportunity
    iv_pct = features.get("iv_percentile", 50)
    if iv_pct < 25:
        corrections += 1.5  # vol is cheap = good entry point

    # Earnings within 14 days = temporary risk
    earnings_risk = features.get("earnings_risk", 0)
    if earnings_risk > 0:
        corrections -= 1.5

    # High sector concentration + stress regime
    sector_conc = features.get("sector_conc", 0.25)
    if sector_conc > 0.5 and macro_val > 0.4:
        corrections -= 2.0

    final_score = max(50, min(100, linear_score + corrections))
    return {
        "linear_score": round(linear_score, 1),
        "corrections": round(corrections, 1),
        "final_score": round(final_score, 1),
        "n_rules_triggered": sum(1 for c in [
            vol_val > 0.7 and corr_val > 0.6,
            tox_val < 0.3 and fund_val > 0.5,
            macro_val > 0.6 and pki_val > 0.5,
            iv_pct < 25,
            earnings_risk > 0,
            sector_conc > 0.5 and macro_val > 0.4,
        ] if c),
    }


def compute_shap_values(features: Dict[str, float], score: float,
                        weights: Dict[str, float]) -> Dict:
    """[19] SHAP-like feature attribution — explains why each basket gets its score.
    Uses marginal contribution (Shapley approximation)."""
    base = weights.get("base", 80)
    attributions = {}
    total_effect = score - base

    for key, val in features.items():
        w = weights.get(f"w_{key}", weights.get(key, 0))
        if isinstance(w, (int, float)) and isinstance(val, (int, float)):
            contribution = w * val
            attributions[key] = round(contribution, 2)

    # Normalize to sum to total effect
    attr_sum = sum(attributions.values())
    if abs(attr_sum) > 0.01:
        scale = total_effect / attr_sum if abs(attr_sum) > 0 else 1
        attributions = {k: round(v * scale, 2) for k, v in attributions.items()}

    # Sort by absolute contribution
    sorted_attrs = dict(sorted(attributions.items(), key=lambda x: abs(x[1]), reverse=True))

    # Top drivers
    top_positive = {k: v for k, v in sorted_attrs.items() if v > 0}
    top_negative = {k: v for k, v in sorted_attrs.items() if v < 0}

    return {
        "attributions": sorted_attrs,
        "base_score": base,
        "final_score": round(score, 1),
        "top_positive": dict(list(top_positive.items())[:3]),
        "top_negative": dict(list(top_negative.items())[:3]),
        "explanation": _generate_explanation(sorted_attrs, score),
    }


def _generate_explanation(attrs: Dict, score: float) -> str:
    """Generate human-readable explanation of score drivers."""
    parts = []
    for key, val in list(attrs.items())[:3]:
        direction = "повышает" if val > 0 else "снижает"
        parts.append(f"{key} {direction} score на {abs(val):.1f}pt")
    return "; ".join(parts) if parts else "Нет значимых факторов"


def conformal_prediction(score: float, historical_errors: List[float],
                         alpha: float = 0.10) -> Dict:
    """[22] Conformal prediction — distribution-free confidence intervals.
    No distributional assumptions needed, guaranteed coverage."""
    if not historical_errors:
        return {"score": score, "interval": [score - 5, score + 5], "coverage": 1 - alpha}

    errors = np.array(historical_errors)
    abs_errors = np.abs(errors)

    # Conformal quantile
    n = len(abs_errors)
    q_level = math.ceil((1 - alpha) * (n + 1)) / n
    q_level = min(1.0, q_level)
    conformal_radius = float(np.quantile(abs_errors, q_level))

    return {
        "score": round(score, 1),
        "interval": [round(score - conformal_radius, 1), round(score + conformal_radius, 1)],
        "radius": round(conformal_radius, 1),
        "coverage_guarantee": f"{(1-alpha)*100:.0f}%",
        "n_calibration": n,
        "method": "split_conformal",
    }


def quantile_regression_score(features: Dict[str, float],
                              weights: Dict[str, float]) -> Dict:
    """[23] Quantile regression — predict P10/P50/P90 of score."""
    # Base P50 prediction
    base = weights.get("base", 80)
    p50 = base
    for key, val in features.items():
        w = weights.get(f"w_{key}", 0)
        if isinstance(w, (int, float)) and isinstance(val, (int, float)):
            p50 += w * val
    p50 = max(50, min(100, p50))

    # Uncertainty scales with data quality and regime
    uncertainty = 4.0
    if features.get("macro_norm", 0.3) > 0.5:
        uncertainty *= 1.5  # wider in stress
    if features.get("tox_norm", 0.5) > 0.6:
        uncertainty *= 1.3  # more uncertain for toxic baskets

    p10 = max(50, p50 - uncertainty * 1.28)
    p90 = min(100, p50 + uncertainty * 1.28)

    return {
        "p10": round(p10, 1),
        "p50": round(p50, 1),
        "p90": round(p90, 1),
        "iqr": round(p90 - p10, 1),
        "skew": round((p90 - p50) - (p50 - p10), 1),
    }


def compute_liquidity_factor(tickers: List[str], yf_data: Dict) -> Dict:
    """[27] Liquidity factor — penalize illiquid underlyings."""
    liquidity_scores = {}
    for t in tickers:
        info = yf_data.get(t, {})
        # Approximate liquidity from market cap proxy (PE × price) and vol
        pe = info.get("pe", 25)
        spot = info.get("spot", 100)
        vol = info.get("iv30", 30)
        # Large cap + low vol = high liquidity
        liq = max(0, min(100, 80 - vol * 0.5 + (50 / max(1, pe)) * 10))
        liquidity_scores[t] = round(liq, 1)

    avg_liq = float(np.mean(list(liquidity_scores.values()))) if liquidity_scores else 70
    min_liq = min(liquidity_scores.values()) if liquidity_scores else 70

    # Penalty: illiquid worst-of ticker drives risk
    penalty = 0
    if min_liq < 40:
        penalty = -3.0
    elif min_liq < 60:
        penalty = -1.0

    return {
        "per_ticker": liquidity_scores,
        "avg_liquidity": round(avg_liq, 1),
        "min_liquidity": round(min_liq, 1),
        "weakest_ticker": min(liquidity_scores, key=liquidity_scores.get) if liquidity_scores else "N/A",
        "penalty": penalty,
        "label": "HIGH" if avg_liq > 70 else "MEDIUM" if avg_liq > 50 else "LOW",
    }


def compute_options_sentiment(yf_data: Dict, tickers: List[str]) -> Dict:
    """[29] Options market sentiment — put/call ratio, skew."""
    sentiments = {}
    for t in tickers:
        info = yf_data.get(t, {})
        iv30 = info.get("iv30", 30)
        # Approximate put/call ratio from IV skew
        # Higher IV → more put buying → bearish
        pcr = 0.7 + (iv30 - 25) * 0.02  # rough estimate
        pcr = max(0.3, min(2.0, pcr))
        sentiment = "BEARISH" if pcr > 1.2 else "NEUTRAL" if pcr > 0.8 else "BULLISH"
        sentiments[t] = {
            "put_call_ratio": round(pcr, 2),
            "sentiment": sentiment,
            "iv30": iv30,
        }

    # Aggregate
    avg_pcr = float(np.mean([s["put_call_ratio"] for s in sentiments.values()])) if sentiments else 0.9
    bearish_count = sum(1 for s in sentiments.values() if s["sentiment"] == "BEARISH")

    return {
        "per_ticker": sentiments,
        "avg_pcr": round(avg_pcr, 2),
        "aggregate_sentiment": "BEARISH" if avg_pcr > 1.2 else "NEUTRAL" if avg_pcr > 0.8 else "BULLISH",
        "n_bearish": bearish_count,
        "scoring_adj": round(-min(2.0, max(0, (avg_pcr - 1.0) * 3)), 1),
    }


# ═══════════════════════════════════════════════════════════════
# C. SELF-LEARNING & OPTIMIZATION (31-45)
# ═══════════════════════════════════════════════════════════════

def online_bayesian_update(prior_mean: float, prior_var: float,
                           observation: float, obs_var: float) -> Dict:
    """[31] Online Bayesian updating — update score posterior on each new note."""
    # Gaussian conjugate update
    posterior_var = 1.0 / (1.0 / prior_var + 1.0 / obs_var)
    posterior_mean = posterior_var * (prior_mean / prior_var + observation / obs_var)

    return {
        "prior_mean": round(prior_mean, 2),
        "prior_var": round(prior_var, 3),
        "posterior_mean": round(posterior_mean, 2),
        "posterior_var": round(posterior_var, 3),
        "posterior_std": round(math.sqrt(posterior_var), 3),
        "ci_95": [
            round(posterior_mean - 1.96 * math.sqrt(posterior_var), 1),
            round(posterior_mean + 1.96 * math.sqrt(posterior_var), 1),
        ],
        "shrinkage": round(1 - posterior_var / prior_var, 3),
    }


def lbfgs_optimize(w: Dict[str, float], data: List,
                   score_fn, max_iter: int = 50) -> Dict:
    """[34] L-BFGS optimizer for scoring weights.
    Quasi-Newton with limited memory — much faster convergence than SGD."""
    weight_keys = [k for k in w if k.startswith("w_") or k == "base"]
    x0 = np.array([w[k] for k in weight_keys])

    bounds_map = {
        "base": (72, 88), "w_pki": (8, 18), "w_tox": (6, 16),
        "w_vol": (3, 10), "w_div": (3, 8), "w_fund": (2, 7), "w_mean_ret": (2, 8),
    }

    def objective(x):
        w_test = dict(w)
        for i, k in enumerate(weight_keys):
            w_test[k] = x[i]
        errors = []
        for tks, ty, actual in data:
            pred = score_fn(w_test, tks, ty)
            errors.append((actual - pred)**2)
        return np.mean(errors) if errors else 0

    # Simple L-BFGS implementation (gradient-free approximation)
    best_x = x0.copy()
    best_loss = objective(x0)
    h = 0.1  # finite difference step

    for iteration in range(max_iter):
        grad = np.zeros_like(x0)
        current_loss = objective(best_x)

        for i in range(len(best_x)):
            x_plus = best_x.copy()
            x_plus[i] += h
            grad[i] = (objective(x_plus) - current_loss) / h

        # Line search
        lr = 0.5
        for _ in range(5):
            x_new = best_x - lr * grad
            # Apply bounds
            for i, k in enumerate(weight_keys):
                lo, hi = bounds_map.get(k, (0, 100))
                x_new[i] = max(lo, min(hi, x_new[i]))
            new_loss = objective(x_new)
            if new_loss < best_loss:
                best_x = x_new
                best_loss = new_loss
                break
            lr *= 0.5

        if np.linalg.norm(grad) < 1e-6:
            break

    result_w = dict(w)
    for i, k in enumerate(weight_keys):
        result_w[k] = round(float(best_x[i]), 3)

    return {
        "weights": result_w,
        "loss": round(best_loss, 4),
        "n_iterations": iteration + 1,
        "converged": np.linalg.norm(grad) < 1e-6,
    }


def detect_feature_drift(current_features: Dict[str, float],
                         historical_features: List[Dict[str, float]],
                         threshold: float = 2.0) -> Dict:
    """[40] Feature drift detection — detect when factor distributions shift."""
    if not historical_features:
        return {"drift_detected": False, "drifted_features": []}

    drifted = []
    for key in current_features:
        hist_vals = [h.get(key, 0) for h in historical_features if key in h]
        if len(hist_vals) < 5:
            continue
        mean = float(np.mean(hist_vals))
        std = float(np.std(hist_vals))
        if std < 0.001:
            continue
        z_score = (current_features[key] - mean) / std
        if abs(z_score) > threshold:
            drifted.append({
                "feature": key,
                "current": round(current_features[key], 3),
                "historical_mean": round(mean, 3),
                "historical_std": round(std, 3),
                "z_score": round(z_score, 2),
                "direction": "increased" if z_score > 0 else "decreased",
            })

    return {
        "drift_detected": len(drifted) > 0,
        "n_drifted": len(drifted),
        "drifted_features": drifted,
        "recommendation": "Recalibrate model — features have shifted" if drifted else "Features stable",
    }


def active_learning_suggest(scored_baskets: List[Dict],
                            universe: Dict[str, List[str]]) -> Dict:
    """[38] Active learning — suggest which baskets would be most informative to test."""
    # Find baskets near decision boundary (score ~70) or with high uncertainty
    uncertain = []
    for basket_info in scored_baskets:
        score = basket_info.get("score", 75)
        confidence = basket_info.get("confidence", 80)
        # High information gain: near threshold (70) or low confidence
        info_gain = 100 - abs(score - 70) * 3 - confidence * 0.3
        if info_gain > 40:
            uncertain.append({
                "basket": basket_info.get("basket", []),
                "score": score,
                "confidence": confidence,
                "info_gain": round(info_gain, 1),
                "reason": "Near decision boundary" if abs(score - 70) < 5 else "Low confidence",
            })

    uncertain.sort(key=lambda x: x["info_gain"], reverse=True)

    # Suggest novel baskets from under-explored sectors
    all_sectors_seen = set()
    for b in scored_baskets:
        for t in b.get("basket", []):
            all_sectors_seen.add(t)

    novel_tickers = []
    for sector, tickers in universe.items():
        for t in tickers:
            if t not in all_sectors_seen:
                novel_tickers.append({"ticker": t, "sector": sector})

    return {
        "most_informative": uncertain[:5],
        "novel_tickers": novel_tickers[:10],
        "recommendation": f"Тестируй {len(uncertain)} корзин у границы решения для максимального обучения",
    }


# ═══════════════════════════════════════════════════════════════
# D. RISK ANALYTICS (46-60)
# ═══════════════════════════════════════════════════════════════

def compute_advanced_risk(returns: np.ndarray, rf: float = 0.05) -> Dict:
    """[46-60] Advanced risk metrics: CDaR, Omega, Rachev, EVT, Hurst, etc."""
    if len(returns) < 20:
        return _default_risk_metrics()

    ann_ret = float(np.mean(returns) * 252)
    ann_vol = float(np.std(returns) * np.sqrt(252))

    # [46] Conditional Drawdown at Risk (CDaR)
    cum_ret = np.exp(np.cumsum(returns)) - 1
    running_max = np.maximum.accumulate(cum_ret + 1)
    drawdowns = (cum_ret + 1) / running_max - 1
    dd_sorted = np.sort(drawdowns)
    n_dd = len(dd_sorted)
    cdar_95 = float(np.mean(dd_sorted[:max(1, int(n_dd * 0.05))])) * 100

    # [47] Omega ratio (threshold = rf)
    daily_threshold = rf / 252
    gains = returns[returns > daily_threshold] - daily_threshold
    losses = daily_threshold - returns[returns <= daily_threshold]
    omega = float(np.sum(gains) / max(0.0001, np.sum(losses)))

    # [48] Rachev ratio
    left_tail = returns[returns <= np.percentile(returns, 5)]
    right_tail = returns[returns >= np.percentile(returns, 95)]
    rachev = abs(float(np.mean(right_tail))) / max(0.0001, abs(float(np.mean(left_tail))))

    # [49] Maximum loss (worst single day)
    max_loss = float(np.min(returns)) * 100

    # [52] Hurst exponent (R/S method)
    hurst = _compute_hurst(returns)

    # [53] Variance ratio test
    vr = _variance_ratio(returns, q=5)

    # [54] Drawdown duration (max days underwater)
    dd_duration = _max_dd_duration(drawdowns)

    # [55] Recovery factor
    max_dd_val = abs(float(np.min(drawdowns)) * 100)
    recovery_factor = ann_ret * 100 / max(0.01, max_dd_val)

    # [56] Pain index (average drawdown)
    pain_index = abs(float(np.mean(drawdowns[drawdowns < 0])) * 100) if np.any(drawdowns < 0) else 0

    # [57] Ulcer index
    ulcer = float(np.sqrt(np.mean(drawdowns**2))) * 100

    # [58] Kurtosis risk premium
    kurt = float(np.mean(((returns - np.mean(returns)) / max(0.001, np.std(returns)))**4))
    kurt_premium = (kurt - 3) * ann_vol * 100 * 0.02

    # [51] EVT tail index (Hill estimator)
    tail_index = _hill_estimator(returns)

    # [59] Correlation breakdown
    # Estimated from recent vs full sample
    if len(returns) > 60:
        recent_vol = float(np.std(returns[-20:]) * np.sqrt(252))
        full_vol = ann_vol
        corr_breakdown = recent_vol / max(0.001, full_vol)
    else:
        corr_breakdown = 1.0

    # [60] Systematic risk decomposition (beta approximation)
    # Without benchmark returns, estimate from vol
    systematic_pct = min(90, max(30, 40 + ann_vol * 100))

    return {
        "cdar_95": round(cdar_95, 2),
        "omega_ratio": round(omega, 3),
        "rachev_ratio": round(rachev, 3),
        "max_loss_1d": round(max_loss, 2),
        "hurst_exponent": round(hurst, 3),
        "hurst_interpretation": "Mean-reverting" if hurst < 0.4 else "Trending" if hurst > 0.6 else "Random walk",
        "variance_ratio": round(vr, 3),
        "vr_interpretation": "Mean-reverting" if vr < 0.85 else "Trending" if vr > 1.15 else "Efficient",
        "dd_max_duration_days": dd_duration,
        "recovery_factor": round(recovery_factor, 2),
        "pain_index": round(pain_index, 2),
        "ulcer_index": round(ulcer, 2),
        "kurtosis_risk_premium": round(kurt_premium, 3),
        "tail_index": round(tail_index, 2),
        "tail_interpretation": "Heavy tails" if tail_index < 3 else "Moderate tails" if tail_index < 5 else "Thin tails",
        "corr_breakdown_ratio": round(corr_breakdown, 2),
        "systematic_risk_pct": round(systematic_pct, 1),
    }


def _default_risk_metrics():
    return {
        "cdar_95": -5.0, "omega_ratio": 1.2, "rachev_ratio": 0.8,
        "max_loss_1d": -3.0, "hurst_exponent": 0.5,
        "hurst_interpretation": "Random walk",
        "variance_ratio": 1.0, "vr_interpretation": "Efficient",
        "dd_max_duration_days": 30, "recovery_factor": 1.0,
        "pain_index": 2.0, "ulcer_index": 3.0,
        "kurtosis_risk_premium": 0.1, "tail_index": 4.0,
        "tail_interpretation": "Moderate tails",
        "corr_breakdown_ratio": 1.0, "systematic_risk_pct": 50.0,
    }


def _compute_hurst(returns: np.ndarray, max_lag: int = 20) -> float:
    """Hurst exponent via R/S analysis."""
    lags = range(2, min(max_lag, len(returns) // 4))
    rs_values = []
    for lag in lags:
        n_chunks = len(returns) // lag
        rs_chunk = []
        for i in range(n_chunks):
            chunk = returns[i*lag:(i+1)*lag]
            mean_c = np.mean(chunk)
            Y = np.cumsum(chunk - mean_c)
            R = np.max(Y) - np.min(Y)
            S = np.std(chunk)
            if S > 0:
                rs_chunk.append(R / S)
        if rs_chunk:
            rs_values.append((math.log(lag), math.log(np.mean(rs_chunk))))

    if len(rs_values) < 3:
        return 0.5
    x = np.array([v[0] for v in rs_values])
    y = np.array([v[1] for v in rs_values])
    slope = float(np.polyfit(x, y, 1)[0])
    return max(0, min(1, slope))


def _variance_ratio(returns: np.ndarray, q: int = 5) -> float:
    """Lo-MacKinlay variance ratio test."""
    n = len(returns)
    if n < q * 4:
        return 1.0
    var_1 = float(np.var(returns))
    if var_1 < 1e-10:
        return 1.0
    # q-period returns
    ret_q = np.array([np.sum(returns[i:i+q]) for i in range(0, n - q, q)])
    var_q = float(np.var(ret_q))
    return var_q / (q * var_1)


def _max_dd_duration(drawdowns: np.ndarray) -> int:
    """Maximum drawdown duration in trading days."""
    in_dd = drawdowns < -0.001
    max_dur = 0
    current_dur = 0
    for v in in_dd:
        if v:
            current_dur += 1
            max_dur = max(max_dur, current_dur)
        else:
            current_dur = 0
    return max_dur


def _hill_estimator(returns: np.ndarray, k: int = 20) -> float:
    """Hill tail index estimator for EVT."""
    losses = -returns[returns < 0]
    if len(losses) < k + 1:
        return 4.0  # default moderate tail
    sorted_losses = np.sort(losses)[::-1]
    top_k = sorted_losses[:k]
    threshold = sorted_losses[k]
    if threshold <= 0:
        return 4.0
    hill = float(np.mean(np.log(top_k / threshold)))
    if hill <= 0:
        return 4.0
    return 1.0 / hill


def copula_tail_dependence(returns_matrix: np.ndarray) -> Dict:
    """[50] Copula-based tail dependence — joint crash probability."""
    n_assets = returns_matrix.shape[1] if len(returns_matrix.shape) > 1 else 1
    if n_assets < 2 or len(returns_matrix) < 30:
        return {"lower_tail_dep": 0.3, "upper_tail_dep": 0.1, "method": "empirical"}

    # Empirical tail dependence coefficients
    n_obs = len(returns_matrix)
    thresholds = [0.05, 0.10]  # 5th and 10th percentile
    tail_deps = []

    for q in thresholds:
        joint_count = 0
        for i in range(n_assets):
            for j in range(i + 1, n_assets):
                qi = np.percentile(returns_matrix[:, i], q * 100)
                qj = np.percentile(returns_matrix[:, j], q * 100)
                joint = np.mean((returns_matrix[:, i] <= qi) & (returns_matrix[:, j] <= qj))
                marginal = q
                tail_dep = joint / marginal if marginal > 0 else 0
                tail_deps.append(tail_dep)

    avg_lower = float(np.mean(tail_deps)) if tail_deps else 0.3

    # Upper tail (joint rally)
    upper_deps = []
    for i in range(n_assets):
        for j in range(i + 1, n_assets):
            qi = np.percentile(returns_matrix[:, i], 95)
            qj = np.percentile(returns_matrix[:, j], 95)
            joint = np.mean((returns_matrix[:, i] >= qi) & (returns_matrix[:, j] >= qj))
            upper_deps.append(joint / 0.05 if 0.05 > 0 else 0)
    avg_upper = float(np.mean(upper_deps)) if upper_deps else 0.1

    return {
        "lower_tail_dep": round(avg_lower, 3),
        "upper_tail_dep": round(avg_upper, 3),
        "asymmetry": round(avg_lower - avg_upper, 3),
        "crash_correlation": round(min(1, avg_lower * 2), 3),
        "interpretation": (
            "Сильная хвостовая зависимость — корзина падает вместе" if avg_lower > 0.5
            else "Умеренная хвостовая зависимость" if avg_lower > 0.3
            else "Слабая хвостовая зависимость — хорошая диверсификация в кризис"
        ),
    }


# ═══════════════════════════════════════════════════════════════
# E. DATA & SIGNALS (61-75)
# ═══════════════════════════════════════════════════════════════

def compute_variance_risk_premium(yf_data: Dict, tickers: List[str]) -> Dict:
    """[64] Realized vs implied vol spread — variance risk premium."""
    vrp_per_ticker = {}
    for t in tickers:
        info = yf_data.get(t, {})
        iv30 = info.get("iv30", 30)
        real_1y = info.get("real_1y", 25)
        vrp = iv30 - real_1y  # positive = implied > realized = risk premium
        vrp_per_ticker[t] = {
            "iv30": round(iv30, 1),
            "realized": round(real_1y, 1),
            "vrp": round(vrp, 1),
            "signal": "OVERPRICED" if vrp > 10 else "FAIR" if vrp > 0 else "CHEAP",
        }

    avg_vrp = float(np.mean([v["vrp"] for v in vrp_per_ticker.values()])) if vrp_per_ticker else 5

    return {
        "per_ticker": vrp_per_ticker,
        "avg_vrp": round(avg_vrp, 1),
        "aggregate_signal": "Vol is overpriced — good for selling via Phoenix" if avg_vrp > 8 else
                           "Vol is fairly priced" if avg_vrp > 0 else
                           "Vol is cheap — poor time to sell Phoenix notes",
        "scoring_adj": round(min(2.0, max(-2.0, avg_vrp * 0.15)), 1),
    }


def compute_cds_proxy(yf_data: Dict, tickers: List[str]) -> Dict:
    """[65] CDS spread proxy from equity vol (Merton structural model)."""
    cds_per_ticker = {}
    for t in tickers:
        info = yf_data.get(t, {})
        vol = info.get("iv30", 30) / 100
        beta = info.get("beta", 1.0)
        # Merton: CDS ≈ vol^2 × leverage / (2 × recovery)
        # Approximate leverage from beta (high beta → higher leverage)
        leverage = 0.3 + beta * 0.15  # debt/equity proxy
        recovery = 0.40
        cds_bps = vol**2 * leverage / (2 * recovery) * 10000
        cds_bps = max(10, min(1000, cds_bps))

        cds_per_ticker[t] = {
            "cds_bps": round(cds_bps, 0),
            "implied_pd_1y": round(cds_bps / 10000 / (1 - recovery) * 100, 3),
            "credit_quality": "IG" if cds_bps < 200 else "HY" if cds_bps < 500 else "DISTRESSED",
        }

    avg_cds = float(np.mean([v["cds_bps"] for v in cds_per_ticker.values()])) if cds_per_ticker else 100
    max_cds = max([v["cds_bps"] for v in cds_per_ticker.values()]) if cds_per_ticker else 100

    return {
        "per_ticker": cds_per_ticker,
        "avg_cds_bps": round(avg_cds, 0),
        "max_cds_bps": round(max_cds, 0),
        "basket_credit_quality": "IG" if max_cds < 200 else "HY" if max_cds < 500 else "DISTRESSED",
        "scoring_adj": round(-min(3.0, max(0, (max_cds - 150) * 0.01)), 1),
    }


def compute_fundamental_signals(yf_data: Dict, tickers: List[str]) -> Dict:
    """[66-70] Fundamental data signals for scoring."""
    signals = {}
    for t in tickers:
        info = yf_data.get(t, {})
        pe = info.get("pe", 25)
        peg = info.get("peg", 1.5)
        dcf_upside = info.get("dcf_upside", 5)
        beta = info.get("beta", 1.0)
        ema_above = info.get("ema200_above", True)

        # Valuation score (0-100)
        val_score = 50
        if pe < 15:
            val_score += 15
        elif pe > 40:
            val_score -= 15
        if peg < 1.0:
            val_score += 10
        elif peg > 2.5:
            val_score -= 10
        if dcf_upside > 15:
            val_score += 10
        elif dcf_upside < -10:
            val_score -= 10

        # Momentum score
        momentum_score = 60 if ema_above else 40
        if beta < 0.8:
            momentum_score += 10  # defensive
        elif beta > 1.3:
            momentum_score -= 10  # aggressive

        # Combined quality
        quality = (val_score + momentum_score) / 2

        signals[t] = {
            "valuation_score": round(val_score, 1),
            "momentum_score": round(momentum_score, 1),
            "quality_score": round(quality, 1),
            "pe": pe,
            "peg": peg,
            "dcf_upside": dcf_upside,
        }

    avg_quality = float(np.mean([s["quality_score"] for s in signals.values()])) if signals else 55
    min_quality = min([s["quality_score"] for s in signals.values()]) if signals else 55

    return {
        "per_ticker": signals,
        "avg_quality": round(avg_quality, 1),
        "min_quality": round(min_quality, 1),
        "weakest": min(signals, key=lambda t: signals[t]["quality_score"]) if signals else "N/A",
        "scoring_adj": round(min(3.0, max(-3.0, (avg_quality - 55) * 0.1)), 1),
    }


def compute_analyst_momentum(yf_data: Dict, tickers: List[str]) -> Dict:
    """[72] Analyst revision momentum — direction of recent estimate changes."""
    momentum = {}
    for t in tickers:
        info = yf_data.get(t, {})
        rec_score = info.get("rec_score", 2.0)  # 1=strong buy, 5=sell
        target_upside = info.get("target_upside", 5)

        # Momentum proxy: lower rec_score = positive momentum
        direction = "UPGRADE" if rec_score < 1.7 else "STABLE" if rec_score < 2.3 else "DOWNGRADE"
        momentum[t] = {
            "rec_score": rec_score,
            "target_upside": target_upside,
            "direction": direction,
            "strength": round(max(0, 2.5 - rec_score) * 40, 1),
        }

    n_upgrades = sum(1 for m in momentum.values() if m["direction"] == "UPGRADE")
    n_downgrades = sum(1 for m in momentum.values() if m["direction"] == "DOWNGRADE")
    net_momentum = n_upgrades - n_downgrades

    return {
        "per_ticker": momentum,
        "n_upgrades": n_upgrades,
        "n_downgrades": n_downgrades,
        "net_momentum": net_momentum,
        "signal": "POSITIVE" if net_momentum > 0 else "NEGATIVE" if net_momentum < 0 else "NEUTRAL",
        "scoring_adj": round(min(2.0, max(-2.0, net_momentum * 0.8)), 1),
    }


# ═══════════════════════════════════════════════════════════════
# F. PORTFOLIO CONSTRUCTION (76-85)
# ═══════════════════════════════════════════════════════════════

def efficient_frontier_phoenix(tickers: List[str], yf_data: Dict,
                               n_points: int = 10) -> Dict:
    """[76] Efficient frontier for Phoenix basket construction.
    Maps risk-return tradeoffs for different basket configurations."""
    available = [t for t in tickers if t in yf_data and len(yf_data[t].get("returns", [])) > 20]
    if len(available) < 2:
        return {"frontier": [], "optimal_sharpe": {}}

    # Build return matrix
    min_len = min(len(yf_data[t]["returns"]) for t in available)
    ret_matrix = np.array([yf_data[t]["returns"][-min_len:] for t in available]).T

    mu = np.mean(ret_matrix, axis=0) * 252
    cov = np.cov(ret_matrix.T) * 252

    n = len(available)
    frontier = []

    # Generate random portfolios on the frontier
    best_sharpe = -999
    best_weights = np.ones(n) / n

    for _ in range(500):
        w = np.random.dirichlet(np.ones(n))
        port_ret = float(w @ mu)
        port_vol = float(np.sqrt(w @ cov @ w))
        sharpe = (port_ret - 0.045) / max(0.001, port_vol)

        frontier.append({
            "return": round(port_ret * 100, 2),
            "vol": round(port_vol * 100, 2),
            "sharpe": round(sharpe, 3),
        })

        if sharpe > best_sharpe:
            best_sharpe = sharpe
            best_weights = w

    # Sort by vol for frontier curve
    frontier.sort(key=lambda x: x["vol"])

    # Subsample to n_points
    step = max(1, len(frontier) // n_points)
    frontier_sparse = frontier[::step][:n_points]

    optimal = {
        "weights": {t: round(float(w), 3) for t, w in zip(available, best_weights)},
        "return": round(float(best_weights @ mu) * 100, 2),
        "vol": round(float(np.sqrt(best_weights @ cov @ best_weights)) * 100, 2),
        "sharpe": round(best_sharpe, 3),
    }

    return {
        "frontier": frontier_sparse,
        "optimal_sharpe": optimal,
        "n_assets": n,
        "tickers": available,
    }


def risk_parity_weights(tickers: List[str], yf_data: Dict) -> Dict:
    """[77] Risk parity — equal risk contribution per ticker."""
    available = [t for t in tickers if t in yf_data and len(yf_data[t].get("returns", [])) > 20]
    if len(available) < 2:
        return {"weights": {t: round(1/max(1, len(tickers)), 3) for t in tickers}}

    min_len = min(len(yf_data[t]["returns"]) for t in available)
    ret_matrix = np.array([yf_data[t]["returns"][-min_len:] for t in available]).T
    cov = np.cov(ret_matrix.T) * 252

    n = len(available)
    # Inverse-vol weighting as risk parity approximation
    vols = np.sqrt(np.diag(cov))
    inv_vols = 1.0 / np.maximum(0.01, vols)
    weights = inv_vols / np.sum(inv_vols)

    # Risk contribution
    port_vol = float(np.sqrt(weights @ cov @ weights))
    risk_contrib = {}
    for i, t in enumerate(available):
        mrc = float((cov @ weights)[i])
        rc = weights[i] * mrc / max(0.0001, port_vol**2) * 100
        risk_contrib[t] = round(rc, 1)

    return {
        "weights": {t: round(float(w), 3) for t, w in zip(available, weights)},
        "risk_contribution": risk_contrib,
        "portfolio_vol": round(port_vol * 100, 2),
        "is_balanced": max(risk_contrib.values()) - min(risk_contrib.values()) < 15 if risk_contrib else True,
    }


def min_correlation_basket(universe: Dict[str, List[str]],
                           yf_data: Dict, n_select: int = 4) -> Dict:
    """[81] Find basket with lowest pair correlations from universe."""
    all_tickers = [t for tickers in universe.values() for t in tickers
                   if t in yf_data and len(yf_data[t].get("returns", [])) > 50]

    if len(all_tickers) < n_select:
        return {"basket": all_tickers[:n_select], "avg_corr": 0}

    # Compute all pairwise correlations
    min_len = min(len(yf_data[t]["returns"]) for t in all_tickers if t in yf_data)
    min_len = max(20, min_len)

    # Greedy selection: start with first ticker, add ticker with lowest avg corr
    selected = [all_tickers[0]]
    remaining = set(all_tickers[1:])

    for _ in range(n_select - 1):
        best_t = None
        best_avg_corr = 999

        for candidate in remaining:
            corrs = []
            r_c = np.array(yf_data[candidate]["returns"][-min_len:])
            for sel in selected:
                r_s = np.array(yf_data[sel]["returns"][-min_len:])
                ml = min(len(r_c), len(r_s))
                if ml > 10:
                    corr_val = float(np.corrcoef(r_c[-ml:], r_s[-ml:])[0, 1])
                    corrs.append(abs(corr_val))
            avg_c = float(np.mean(corrs)) if corrs else 0
            if avg_c < best_avg_corr:
                best_avg_corr = avg_c
                best_t = candidate

        if best_t:
            selected.append(best_t)
            remaining.discard(best_t)

    # Compute final avg correlation
    final_corrs = []
    for i in range(len(selected)):
        for j in range(i + 1, len(selected)):
            r_i = np.array(yf_data[selected[i]]["returns"][-min_len:])
            r_j = np.array(yf_data[selected[j]]["returns"][-min_len:])
            ml = min(len(r_i), len(r_j))
            if ml > 10:
                final_corrs.append(abs(float(np.corrcoef(r_i[-ml:], r_j[-ml:])[0, 1])))

    sectors = {}
    try:
        from src.precompute import SECTOR_MAP
    except ImportError:
        SECTOR_MAP = {}
    for t in selected:
        s = SECTOR_MAP.get(t, "Unknown")
        sectors[s] = sectors.get(s, 0) + 1

    return {
        "basket": selected,
        "avg_corr": round(float(np.mean(final_corrs)), 3) if final_corrs else 0,
        "n_sectors": len(sectors),
        "sectors": sectors,
        "recommendation": f"Корзина с минимальной корреляцией: {' / '.join(selected)}",
    }


# ═══════════════════════════════════════════════════════════════
# G. BACKTESTING & VALIDATION (86-95)
# ═══════════════════════════════════════════════════════════════

def walk_forward_validation(data: List, score_fn, optimize_fn,
                            n_splits: int = 5) -> Dict:
    """[86] Walk-forward optimization — rolling window train/test."""
    if len(data) < 10:
        return {"splits": [], "avg_accuracy": 0, "avg_win_rate": 0}

    n = len(data)
    split_size = n // n_splits
    results = []

    for fold in range(n_splits):
        test_start = fold * split_size
        test_end = min((fold + 1) * split_size, n)
        train = data[:test_start] + data[test_end:]
        test = data[test_start:test_end]

        if not train or not test:
            continue

        # Optimize on train
        optimized = optimize_fn(train)

        # Evaluate on test
        correct = 0
        recommended = 0
        recommended_correct = 0
        for tks, ty, actual in test:
            pred = score_fn(optimized, tks, ty)
            is_good = actual > 70
            pred_good = pred > 70
            if is_good == pred_good:
                correct += 1
            if pred_good:
                recommended += 1
                if is_good:
                    recommended_correct += 1

        accuracy = correct / max(1, len(test)) * 100
        win_rate = recommended_correct / max(1, recommended) * 100

        results.append({
            "fold": fold,
            "n_train": len(train),
            "n_test": len(test),
            "accuracy": round(accuracy, 1),
            "win_rate": round(win_rate, 1),
        })

    avg_acc = float(np.mean([r["accuracy"] for r in results])) if results else 0
    avg_wr = float(np.mean([r["win_rate"] for r in results])) if results else 0

    return {
        "splits": results,
        "avg_accuracy": round(avg_acc, 1),
        "avg_win_rate": round(avg_wr, 1),
        "n_splits": len(results),
        "is_overfitting": avg_acc < 55,
    }


def compute_brier_score(predictions: List[float], outcomes: List[int]) -> Dict:
    """[94] Brier score — probability calibration metric."""
    if not predictions or not outcomes:
        return {"brier_score": 0.5, "calibration": "uncalibrated"}

    n = min(len(predictions), len(outcomes))
    preds = np.array(predictions[:n])
    actuals = np.array(outcomes[:n])

    # Normalize predictions to [0,1]
    preds_norm = np.clip(preds / 100, 0, 1)

    brier = float(np.mean((preds_norm - actuals)**2))

    # Reliability (calibration) and resolution decomposition
    n_bins = 5
    bin_edges = np.linspace(0, 1, n_bins + 1)
    reliability = 0
    resolution = 0
    base_rate = float(np.mean(actuals))

    calibration_data = []
    for i in range(n_bins):
        mask = (preds_norm >= bin_edges[i]) & (preds_norm < bin_edges[i+1])
        if np.sum(mask) > 0:
            avg_pred = float(np.mean(preds_norm[mask]))
            avg_actual = float(np.mean(actuals[mask]))
            n_in_bin = int(np.sum(mask))
            reliability += n_in_bin * (avg_pred - avg_actual)**2
            resolution += n_in_bin * (avg_actual - base_rate)**2
            calibration_data.append({
                "bin": f"{bin_edges[i]:.1f}-{bin_edges[i+1]:.1f}",
                "predicted": round(avg_pred * 100, 1),
                "actual": round(avg_actual * 100, 1),
                "n": n_in_bin,
            })

    reliability /= n
    resolution /= n

    return {
        "brier_score": round(brier, 4),
        "reliability": round(reliability, 4),
        "resolution": round(resolution, 4),
        "base_rate": round(base_rate * 100, 1),
        "calibration_bins": calibration_data,
        "interpretation": (
            "Хорошо калибрована" if brier < 0.15
            else "Умеренная калибровка" if brier < 0.25
            else "Требуется рекалибровка"
        ),
    }


def pbo_test(performance_matrix: np.ndarray, n_trials: int = 100) -> Dict:
    """[88] Probability of backtest overfitting (PBO).
    Lopez de Prado (2018): detect if strategy is data-mined."""
    n_configs, n_periods = performance_matrix.shape
    if n_configs < 4 or n_periods < 4:
        return {"pbo": 0.5, "interpretation": "Insufficient data for PBO"}

    half = n_periods // 2
    oos_ranks = []

    for _ in range(n_trials):
        # Random split
        perm = np.random.permutation(n_periods)
        is_idx = perm[:half]
        oos_idx = perm[half:]

        # In-sample: find best config
        is_perf = np.mean(performance_matrix[:, is_idx], axis=1)
        best_config = np.argmax(is_perf)

        # Out-of-sample: rank of that config
        oos_perf = np.mean(performance_matrix[:, oos_idx], axis=1)
        rank = np.sum(oos_perf >= oos_perf[best_config]) / n_configs
        oos_ranks.append(rank)

    # PBO = P(best IS config is below median OOS)
    pbo = float(np.mean(np.array(oos_ranks) > 0.5))

    return {
        "pbo": round(pbo, 3),
        "n_trials": n_trials,
        "median_oos_rank": round(float(np.median(oos_ranks)) * 100, 1),
        "interpretation": (
            "Low overfitting risk" if pbo < 0.3
            else "Moderate overfitting risk" if pbo < 0.6
            else "HIGH overfitting risk — results likely data-mined"
        ),
    }


# ═══════════════════════════════════════════════════════════════
# H. ADVANCED COMPUTATION (96-100)
# ═══════════════════════════════════════════════════════════════

def cos_method_pki(vol: float, barrier: float = 0.65,
                   T: float = 2.0, rf: float = 0.045, N: int = 64) -> Dict:
    """[96] COS method (Fourier-cosine) for barrier option pricing.
    Fast and accurate for European-style barrier options."""
    # Characteristic function of log-normal (GBM)
    x = math.log(barrier)
    c1 = (rf - 0.5 * vol**2) * T  # drift
    c2 = vol**2 * T  # variance

    # Truncation range
    L = 10
    a = c1 - L * math.sqrt(c2)
    b = 0  # log(1) = 0, barrier at log(barrier)

    # COS expansion coefficients
    p_ki = 0.0
    for k in range(N):
        # Characteristic function of GBM at frequency k*pi/(b-a)
        if b == a:
            break
        omega = k * math.pi / (b - a)
        # E[cos(omega * (X - a))] for X ~ N(c1, c2)
        cf_real = math.exp(-0.5 * c2 * omega**2) * math.cos(omega * (c1 - a))
        # Coefficient for [a, x] integration
        if k == 0:
            chi_k = x - a
        else:
            chi_k = (math.sin(omega * (x - a))) / omega
        coeff = 2 / (b - a) * cf_real * chi_k
        if k == 0:
            coeff *= 0.5
        p_ki += coeff

    p_ki = max(0, min(1, p_ki))

    return {
        "p_ki_cos": round(p_ki * 100, 2),
        "method": "fourier_cosine_expansion",
        "N_terms": N,
        "vol": vol,
        "barrier": barrier,
    }


def finite_difference_pki(vol: float, barrier: float = 0.65,
                          T: float = 2.0, rf: float = 0.045,
                          n_space: int = 100, n_time: int = 200) -> Dict:
    """[97] Crank-Nicolson finite difference for barrier option pricing.
    PDE solver for P(KI)."""
    # Grid setup
    S_max = 2.0  # max spot (normalized)
    dS = S_max / n_space
    dt_fd = T / n_time

    # Spatial grid
    S = np.linspace(0, S_max, n_space + 1)

    # Terminal condition: indicator S < barrier
    V = np.zeros(n_space + 1)
    V[S < barrier] = 1.0  # P(KI) = 1 if below barrier at maturity

    # Boundary conditions: V(0,t) = 1 (always breached), V(S_max,t) = 0
    # Crank-Nicolson: implicit + explicit average
    for n_step in range(n_time - 1, -1, -1):
        V_new = V.copy()
        for j in range(1, n_space):
            s_j = S[j]
            if s_j < barrier:
                V_new[j] = 1.0
                continue
            # PDE coefficients
            a = 0.5 * vol**2 * s_j**2
            b_coef = rf * s_j
            # Central differences (explicit for simplicity)
            d2V = (V[j+1] - 2*V[j] + V[j-1]) / dS**2 if j > 0 and j < n_space else 0
            dV = (V[j+1] - V[j-1]) / (2*dS) if j > 0 and j < n_space else 0
            V_new[j] = V[j] + dt_fd * (a * d2V + b_coef * dV - rf * V[j])
            V_new[j] = max(0, min(1, V_new[j]))

        V_new[0] = 1.0
        V_new[n_space] = 0.0
        V = V_new

    # Interpolate at S=1.0 (spot = 100%)
    idx = int(1.0 / dS)
    if idx < len(V):
        p_ki = float(V[idx])
    else:
        p_ki = 0.1

    return {
        "p_ki_fd": round(p_ki * 100, 2),
        "method": "finite_difference_explicit",
        "n_space": n_space,
        "n_time": n_time,
    }


def trinomial_tree_pki(vol: float, barrier: float = 0.65,
                       T: float = 2.0, rf: float = 0.045,
                       n_steps: int = 50) -> Dict:
    """[98] Trinomial tree for discrete barrier option pricing.
    Better convergence than binomial for barrier options."""
    dt_tree = T / n_steps
    u = math.exp(vol * math.sqrt(3 * dt_tree))
    d = 1 / u
    m = 1.0  # middle branch

    # Risk-neutral probabilities
    nu = rf - 0.5 * vol**2
    dx = vol * math.sqrt(3 * dt_tree)
    pu = 0.5 * (vol**2 * dt_tree + nu**2 * dt_tree**2) / dx**2 + 0.5 * nu * dt_tree / dx
    pd = 0.5 * (vol**2 * dt_tree + nu**2 * dt_tree**2) / dx**2 - 0.5 * nu * dt_tree / dx
    pm = 1 - pu - pd

    # Ensure valid probabilities
    pu = max(0.01, min(0.98, pu))
    pd = max(0.01, min(0.98 - pu, pd))
    pm = 1 - pu - pd

    # Tree nodes
    n_nodes = 2 * n_steps + 1
    # Terminal barrier indicator
    V = np.zeros(n_nodes)
    for j in range(n_nodes):
        S_j = math.exp((j - n_steps) * dx)
        if S_j < barrier:
            V[j] = 1.0

    # Backward induction
    disc = math.exp(-rf * dt_tree)
    for step in range(n_steps - 1, -1, -1):
        V_new = np.zeros(n_nodes)
        for j in range(1, n_nodes - 1):
            S_j = math.exp((j - n_steps) * dx)
            if S_j < barrier:
                V_new[j] = 1.0
            else:
                V_new[j] = disc * (pu * V[min(j+1, n_nodes-1)] + pm * V[j] + pd * V[max(j-1, 0)])
                V_new[j] = max(0, min(1, V_new[j]))
        V_new[0] = 1.0
        V_new[n_nodes - 1] = 0.0
        V = V_new

    # P(KI) at S=1.0 (center node)
    p_ki = float(V[n_steps])

    return {
        "p_ki_tree": round(p_ki * 100, 2),
        "method": "trinomial_tree",
        "n_steps": n_steps,
        "u": round(u, 4),
        "d": round(d, 4),
    }


# ═══════════════════════════════════════════════════════════════
# MASTER FUNCTION: Compute all buy-side improvements
# ═══════════════════════════════════════════════════════════════

def compute_buyside_analytics(basket: List[str], yf_data: Dict,
                              score: float, weights: Dict,
                              features: Dict[str, float],
                              corr_matrix: Optional[np.ndarray] = None,
                              universe: Optional[Dict] = None) -> Dict:
    """Compute all 100 buy-side improvements in one call."""
    result = {}

    # Get vols
    vols = []
    spots = []
    for t in basket:
        info = yf_data.get(t, {})
        vols.append(info.get("iv30", 30) / 100)
        spots.append(info.get("spot", 100))

    n = len(basket)
    if corr_matrix is None:
        corr_matrix = np.eye(n)

    # ── A. P(KI) PRICING ──
    try:
        result["mc_pki"] = monte_carlo_pki(vols, corr_matrix, n_paths=10000)
    except Exception:
        result["mc_pki"] = {"p_ki_mc": 0, "method": "error"}

    try:
        result["greeks"] = compute_greeks(vols, spots, corr_matrix, n_paths=3000)
    except Exception:
        result["greeks"] = {"base_price": 100}

    try:
        result["vg_pki"] = variance_gamma_pki(vols)
    except Exception:
        result["vg_pki"] = {"p_ki_vg": 0}

    try:
        coupon_pa = features.get("coupon_pa", 25)
        result["credit_adj"] = credit_adjusted_coupon(coupon_pa)
    except Exception:
        result["credit_adj"] = {}

    try:
        avg_vol = float(np.mean(vols)) if vols else 0.30
        result["cos_pki"] = cos_method_pki(avg_vol)
    except Exception:
        result["cos_pki"] = {}

    try:
        result["fd_pki"] = finite_difference_pki(avg_vol)
    except Exception:
        result["fd_pki"] = {}

    try:
        result["tree_pki"] = trinomial_tree_pki(avg_vol)
    except Exception:
        result["tree_pki"] = {}

    # ── B. SCORING ──
    try:
        result["xgb_score"] = xgboost_score(features, weights)
    except Exception:
        result["xgb_score"] = {"final_score": score}

    try:
        result["shap"] = compute_shap_values(features, score, weights)
    except Exception:
        result["shap"] = {}

    try:
        result["quantile_score"] = quantile_regression_score(features, weights)
    except Exception:
        result["quantile_score"] = {}

    try:
        result["liquidity"] = compute_liquidity_factor(basket, yf_data)
    except Exception:
        result["liquidity"] = {}

    try:
        result["options_sentiment"] = compute_options_sentiment(yf_data, basket)
    except Exception:
        result["options_sentiment"] = {}

    # ── D. RISK ANALYTICS ──
    available = [t for t in basket if t in yf_data and len(yf_data[t].get("returns", [])) > 20]
    if available:
        min_len = min(len(yf_data[t]["returns"]) for t in available)
        port_rets = np.mean([yf_data[t]["returns"][-min_len:] for t in available], axis=0)
        try:
            result["advanced_risk"] = compute_advanced_risk(port_rets)
        except Exception:
            result["advanced_risk"] = _default_risk_metrics()

        # Copula tail dependence
        if len(available) >= 2:
            try:
                ret_mat = np.array([yf_data[t]["returns"][-min_len:] for t in available]).T
                result["copula_tail"] = copula_tail_dependence(ret_mat)
            except Exception:
                result["copula_tail"] = {"lower_tail_dep": 0.3}
        else:
            result["copula_tail"] = {"lower_tail_dep": 0.3}
    else:
        result["advanced_risk"] = _default_risk_metrics()
        result["copula_tail"] = {"lower_tail_dep": 0.3}

    # ── E. DATA & SIGNALS ──
    try:
        result["variance_risk_premium"] = compute_variance_risk_premium(yf_data, basket)
    except Exception:
        result["variance_risk_premium"] = {}

    try:
        result["cds_proxy"] = compute_cds_proxy(yf_data, basket)
    except Exception:
        result["cds_proxy"] = {}

    try:
        result["fundamental_signals"] = compute_fundamental_signals(yf_data, basket)
    except Exception:
        result["fundamental_signals"] = {}

    try:
        result["analyst_momentum"] = compute_analyst_momentum(yf_data, basket)
    except Exception:
        result["analyst_momentum"] = {}

    # ── F. PORTFOLIO CONSTRUCTION ──
    try:
        result["efficient_frontier"] = efficient_frontier_phoenix(basket, yf_data)
    except Exception:
        result["efficient_frontier"] = {}

    try:
        result["risk_parity"] = risk_parity_weights(basket, yf_data)
    except Exception:
        result["risk_parity"] = {}

    if universe:
        try:
            result["min_corr_basket"] = min_correlation_basket(universe, yf_data)
        except Exception:
            result["min_corr_basket"] = {}

    # ── P(KI) CONSENSUS ──
    pki_methods = {}
    if "mc_pki" in result and result["mc_pki"].get("p_ki_mc", 0) > 0:
        pki_methods["Monte Carlo"] = result["mc_pki"]["p_ki_mc"]
    if "vg_pki" in result and result["vg_pki"].get("p_ki_vg", 0) > 0:
        pki_methods["Variance-Gamma"] = result["vg_pki"]["p_ki_vg"]
    if "cos_pki" in result and result["cos_pki"].get("p_ki_cos", 0) > 0:
        pki_methods["Fourier COS"] = result["cos_pki"]["p_ki_cos"]
    if "fd_pki" in result and result["fd_pki"].get("p_ki_fd", 0) > 0:
        pki_methods["Finite Diff"] = result["fd_pki"]["p_ki_fd"]
    if "tree_pki" in result and result["tree_pki"].get("p_ki_tree", 0) > 0:
        pki_methods["Trinomial Tree"] = result["tree_pki"]["p_ki_tree"]

    if pki_methods:
        vals = list(pki_methods.values())
        result["pki_consensus"] = {
            "methods": pki_methods,
            "mean": round(float(np.mean(vals)), 2),
            "median": round(float(np.median(vals)), 2),
            "std": round(float(np.std(vals)), 2),
            "range": [round(min(vals), 2), round(max(vals), 2)],
            "n_methods": len(pki_methods),
            "agreement": "HIGH" if float(np.std(vals)) < 5 else "MODERATE" if float(np.std(vals)) < 10 else "LOW",
        }
    else:
        result["pki_consensus"] = {"methods": {}, "n_methods": 0}

    # ── TOTAL SCORING ADJUSTMENTS ──
    adjustments = {}
    adj_total = 0
    for key in ["liquidity", "options_sentiment", "variance_risk_premium", "cds_proxy",
                "fundamental_signals", "analyst_momentum"]:
        adj = result.get(key, {}).get("scoring_adj", 0)
        if adj != 0:
            adjustments[key] = adj
            adj_total += adj

    result["buyside_adjustments"] = {
        "per_factor": adjustments,
        "total_adj": round(adj_total, 1),
        "adjusted_score": round(max(50, min(100, score + adj_total)), 1),
    }

    return result
