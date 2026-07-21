"""Phoenix Analytics — bank-grade structured product pricing and risk.

Modules:
    models       — dataclass models for Greeks, vol surface, barrier risk
    implied_vol  — extract IV from yfinance options chains
    implied_corr — dispersion-based implied correlation
    local_vol    — Dupire local volatility surface
    barrier_risk — barrier-specific risk analysis
    dividend     — dividend forecasting and barrier impact
    pricing      — full MC pricing engine
    greeks       — numerical bump-and-reprice Greeks
"""
