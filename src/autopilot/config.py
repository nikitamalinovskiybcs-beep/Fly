"""All tunable parameters with safety bounds.

Autopilot can ONLY change values within these bounds.
Each parameter has a default, min, max, and max daily change limit.
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
CONFIG_FILE = DATA_DIR / "autopilot_config.json"
SNAPSHOT_DIR = DATA_DIR / "config_snapshots"

TUNABLE_PARAMETERS: dict[str, dict[str, Any]] = {
    "confidence_threshold": {
        "default": 0.65,
        "min": 0.40,
        "max": 0.90,
        "max_change_per_day": 0.10,
        "type": "float",
        "description": "Minimum confidence to execute trade",
    },
    "stop_loss_atr_mult": {
        "default": 2.0,
        "min": 1.0,
        "max": 4.0,
        "max_change_per_day": 0.5,
        "type": "float",
        "description": "Stop loss = ATR x this multiplier",
    },
    "take_profit_atr_mult": {
        "default": 3.0,
        "min": 1.5,
        "max": 6.0,
        "max_change_per_day": 0.5,
        "type": "float",
        "description": "Take profit = ATR x this multiplier",
    },
    "kelly_fraction": {
        "default": 0.25,
        "min": 0.10,
        "max": 0.50,
        "max_change_per_day": 0.05,
        "type": "float",
        "description": "Kelly criterion fraction for position sizing",
    },
    "max_position_pct": {
        "default": 0.10,
        "min": 0.05,
        "max": 0.25,
        "max_change_per_day": 0.03,
        "type": "float",
        "description": "Maximum portfolio pct per position",
    },
    "rsi_buy_threshold": {
        "default": 30,
        "min": 15,
        "max": 45,
        "max_change_per_day": 5,
        "type": "int",
        "description": "Buy when RSI drops below this",
    },
    "rsi_sell_threshold": {
        "default": 70,
        "min": 55,
        "max": 85,
        "max_change_per_day": 5,
        "type": "int",
        "description": "Sell when RSI rises above this",
    },
    "sma_fast_period": {
        "default": 50,
        "min": 10,
        "max": 100,
        "max_change_per_day": 10,
        "type": "int",
        "description": "Fast SMA period",
    },
    "sma_slow_period": {
        "default": 200,
        "min": 100,
        "max": 400,
        "max_change_per_day": 20,
        "type": "int",
        "description": "Slow SMA period",
    },
    "trade_in_bear_regime": {
        "default": False,
        "type": "bool",
        "description": "Allow trading in bear regime",
    },
    "signal_weights": {
        "default": {
            "regime": 0.20,
            "rsi_oversold": 0.10,
            "rsi_overbought": 0.10,
            "sma_crossover": 0.15,
            "evt_var_safe": 0.10,
            "momentum_30d": 0.15,
            "mean_reversion": 0.10,
            "volume_confirmation": 0.10,
        },
        "min_per_weight": 0.03,
        "max_per_weight": 0.40,
        "type": "weights_dict",
        "description": "Signal weights for composite score",
    },
    "basket_scoring_weights": {
        "default": {
            "liquidity": 0.10,
            "fundamental": 0.15,
            "worst_of_tail_risk": 0.15,
            "crisis_correlation": 0.12,
            "max_drawdown_worst_of": 0.10,
            "sector_diversification": 0.10,
            "implied_vol_risk": 0.13,
            "greeks_exposure": 0.15,
        },
        "min_per_weight": 0.05,
        "max_per_weight": 0.30,
        "type": "weights_dict",
        "description": "Basket scoring criteria weights",
    },
}

SAFETY_LIMITS: dict[str, Any] = {
    "max_changes_per_day": 3,
    "max_changes_per_week": 10,
    "min_trades_for_optimization": 30,
    "trial_mode_trades": 10,
    "rollback_if_dd_exceeds": 0.10,
    "stop_trading_if_dd_exceeds": 0.20,
    "stop_trading_if_consecutive_losses": 5,
    "stop_optimization_after_rollbacks": 3,
    "stop_optimization_cooldown_days": 7,
    "min_improvement_to_deploy": 0.05,
    "max_pbo_to_deploy": 0.50,
}


def load_config() -> dict[str, Any]:
    """Load current config from disk, falling back to defaults.

    Returns:
        Dict of parameter_name -> current_value.
    """
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            logger.warning("Failed to load config, using defaults")
    return {k: v["default"] for k, v in TUNABLE_PARAMETERS.items()}


def save_config(config: dict[str, Any]) -> None:
    """Persist config to disk.

    Args:
        config: Dict of parameter_name -> current_value.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    logger.info("Config saved to %s", CONFIG_FILE)


def save_snapshot(config: dict[str, Any], label: str) -> Path:
    """Save a rollback snapshot of the current config.

    Args:
        config: Dict of parameter_name -> current_value.
        label: Descriptive label for the snapshot.

    Returns:
        Path to the saved snapshot file.
    """
    from datetime import datetime as _dt
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = int(_dt.now().timestamp())
    path = SNAPSHOT_DIR / f"{ts}_{label}.json"
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    return path


def validate_parameter(name: str, value: Any) -> bool:
    """Check that a parameter value is within allowed bounds.

    Args:
        name: Parameter name.
        value: Proposed value.

    Returns:
        True if valid, False otherwise.
    """
    spec = TUNABLE_PARAMETERS.get(name)
    if spec is None:
        return False
    ptype = spec["type"]
    if ptype in ("float", "int"):
        return spec["min"] <= value <= spec["max"]
    if ptype == "bool":
        return isinstance(value, bool)
    if ptype == "weights_dict":
        if not isinstance(value, dict):
            return False
        lo = spec.get("min_per_weight", 0)
        hi = spec.get("max_per_weight", 1)
        return all(lo <= v <= hi for v in value.values())
    return True
