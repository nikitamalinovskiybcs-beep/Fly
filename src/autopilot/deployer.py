"""Safe Deployer — deploys approved changes with trial mode and auto-rollback.

Each deployment:
1. Saves rollback snapshot
2. Applies new parameter
3. Enters trial mode (10 trades)
4. Auto-rollbacks if trial fails
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.autopilot.config import (
    SAFETY_LIMITS,
    load_config,
    save_config,
    save_snapshot,
)
from src.autopilot.models import DeploymentResult, ParameterChange
from src.autopilot.safety import SafetySystem

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
TRIAL_FILE = DATA_DIR / "trial_mode.json"


class SafeDeployer:
    """Deploys approved changes with trial mode and auto-rollback."""

    def __init__(self) -> None:
        self.safety = SafetySystem()

    def deploy(self, change: ParameterChange) -> DeploymentResult:
        """Deploy an approved parameter change in trial mode.

        Args:
            change: Approved ParameterChange to deploy.

        Returns:
            DeploymentResult with deployment status.
        """
        now = datetime.now()
        config = load_config()

        if not self.safety.check_change_limits():
            logger.warning("Daily change limit reached, cannot deploy")
            return DeploymentResult(
                timestamp=now, parameter_name=change.parameter_name,
                old_value=change.current_value, new_value=change.proposed_value,
                trial_trades=0, trial_sharpe=0.0, trial_win_rate=0.0,
                accepted=False, rollback_reason="daily change limit reached",
            )

        snapshot_path = save_snapshot(config, change.parameter_name)
        logger.info("Snapshot saved: %s", snapshot_path)

        if change.parameter_name in config:
            config[change.parameter_name] = change.proposed_value
        save_config(config)

        self._enter_trial_mode(change)
        self.safety.log_deployment(
            change.parameter_name, change.current_value, change.proposed_value,
        )

        logger.info(
            "Deployed %s: %.4f -> %.4f (trial mode)",
            change.parameter_name, change.current_value, change.proposed_value,
        )

        return DeploymentResult(
            timestamp=now, parameter_name=change.parameter_name,
            old_value=change.current_value, new_value=change.proposed_value,
            trial_trades=0, trial_sharpe=0.0, trial_win_rate=0.0,
            accepted=True, rollback_reason=None,
        )

    def rollback(self, change: ParameterChange, reason: str) -> None:
        """Restore previous parameter value.

        Args:
            change: The ParameterChange to roll back.
            reason: Why the rollback is happening.
        """
        config = load_config()
        config[change.parameter_name] = change.current_value
        save_config(config)
        self._clear_trial_mode()
        logger.warning(
            "ROLLBACK %s: %.4f -> %.4f (reason: %s)",
            change.parameter_name, change.proposed_value, change.current_value, reason,
        )

    def check_trial(self) -> Optional[DeploymentResult]:
        """Check if trial period is complete and evaluate results.

        Returns:
            DeploymentResult if trial concluded, None if still in progress.
        """
        trial = self._load_trial_mode()
        if trial is None:
            return None

        trades_since = trial.get("trades_since_deploy", 0)
        required = SAFETY_LIMITS["trial_mode_trades"]

        if trades_since < required:
            return None

        trial_pnls = trial.get("trial_pnls", [])
        now = datetime.now()

        if not trial_pnls:
            self._clear_trial_mode()
            return DeploymentResult(
                timestamp=now, parameter_name=trial["parameter_name"],
                old_value=trial["old_value"], new_value=trial["new_value"],
                trial_trades=0, trial_sharpe=0.0, trial_win_rate=0.0,
                accepted=True, rollback_reason=None,
            )

        import numpy as np
        pnls = np.array(trial_pnls)
        trial_sharpe = float(pnls.mean() / (pnls.std() + 1e-12) * np.sqrt(252))
        trial_wr = float((pnls > 0).sum() / len(pnls))

        if trial_sharpe > 0 and trial_wr >= 0.40:
            self._clear_trial_mode()
            logger.info(
                "Trial CONFIRMED for %s (Sharpe=%.2f, WR=%.0f%%)",
                trial["parameter_name"], trial_sharpe, trial_wr * 100,
            )
            return DeploymentResult(
                timestamp=now, parameter_name=trial["parameter_name"],
                old_value=trial["old_value"], new_value=trial["new_value"],
                trial_trades=len(pnls), trial_sharpe=trial_sharpe,
                trial_win_rate=trial_wr, accepted=True,
            )
        else:
            change = ParameterChange(
                parameter_name=trial["parameter_name"],
                current_value=trial["old_value"],
                proposed_value=trial["new_value"],
                change_pct=0.0, reason="", backtest_sharpe_before=0.0,
                backtest_sharpe_after=0.0, improvement_pct=0.0,
                pbo_score=0.0, walk_forward_pass=False,
            )
            self.rollback(change, f"trial failed (Sharpe={trial_sharpe:.2f}, WR={trial_wr:.0%})")
            return DeploymentResult(
                timestamp=now, parameter_name=trial["parameter_name"],
                old_value=trial["old_value"], new_value=trial["new_value"],
                trial_trades=len(pnls), trial_sharpe=trial_sharpe,
                trial_win_rate=trial_wr, accepted=False,
                rollback_reason=f"trial Sharpe={trial_sharpe:.2f}, WR={trial_wr:.0%}",
            )

    def _enter_trial_mode(self, change: ParameterChange) -> None:
        """Save trial state to disk.

        Args:
            change: The deployed ParameterChange.
        """
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        trial = {
            "parameter_name": change.parameter_name,
            "old_value": change.current_value,
            "new_value": change.proposed_value,
            "deployed_at": datetime.now().isoformat(),
            "trades_since_deploy": 0,
            "trial_pnls": [],
        }
        TRIAL_FILE.write_text(json.dumps(trial, indent=2))

    def _load_trial_mode(self) -> Optional[dict]:
        """Load trial state from disk."""
        if not TRIAL_FILE.exists():
            return None
        try:
            return json.loads(TRIAL_FILE.read_text())
        except Exception:
            return None

    def _clear_trial_mode(self) -> None:
        """Remove trial mode state."""
        if TRIAL_FILE.exists():
            TRIAL_FILE.unlink()
