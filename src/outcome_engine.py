"""Structured-note outcome engine.

The engine keeps three data classes separate:

* ``replay_historical`` returns ``source="historical_replay"`` for a
  historical path.
* ``simulate_monte_carlo`` returns ``source="simulated"`` for model paths.
* ``PaperOutcomeTracker`` stores open notes and only marks realized notes as
  eligible for learning.

The implementation is deliberately small and deterministic when a seed is
provided. It is a payoff engine, not a claim that simulated outcomes are
market facts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping, Optional

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTCOME_PATH = DATA_DIR / "structured_note_outcomes.json"
REALIZED_FEEDBACK_PATH = DATA_DIR / "realized_outcome_feedback.json"
QUALITY_REPORT_PATH = DATA_DIR / "outcome_quality_report.json"


def build_decision_record(
    product: Mapping,
    market_data: Optional[Mapping] = None,
    evidence_gate: Optional[Mapping] = None,
    generated_at: Optional[str] = None,
) -> dict:
    """Create one auditable record linking data, selection, and outcomes."""
    market_data = market_data or {}
    evidence_gate = dict(evidence_gate or {})
    observed_dates = sorted(
        str(item.get("as_of"))
        for item in market_data.values()
        if item.get("as_of")
    )
    market_data_as_of = observed_dates[-1] if observed_dates else None
    payload = {
        "basket": list(product.get("basket", [])),
        "barrier": product.get("barrier"),
        "tenor_months": product.get("tenor_months"),
        "coupon": product.get("coupon"),
        "final_objective": product.get("final_objective"),
        "market_data_as_of": market_data_as_of,
        "evidence_gate": evidence_gate,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode(),
    ).hexdigest()[:16]
    return {
        "decision_id": f"decision_{digest}",
        "generated_at": generated_at or _utc_now(),
        "market_data_as_of": market_data_as_of,
        "freshness_status": (
            "verified" if market_data_as_of else "unverified"
        ),
        "evidence_gate": evidence_gate,
        "selection": payload,
        "outcome_source": "paper_until_realized",
    }


@dataclass(frozen=True)
class StructuredNoteSpec:
    basket: list[str]
    barrier: float = 0.60
    autocall_level: float = 1.00
    coupon_barrier: float = 0.60
    coupon_rate: float = 0.065
    term_months: int = 24
    observations_per_year: int = 4

    @property
    def observation_count(self) -> int:
        return max(1, round(self.term_months / 12 * self.observations_per_year))


def _observation_positions(length: int, count: int) -> np.ndarray:
    if length < 2:
        return np.array([], dtype=int)
    return np.unique(np.linspace(1, length - 1, count, dtype=int))


def replay_historical(
    prices: Mapping[str, pd.Series | list[float]],
    spec: StructuredNoteSpec,
) -> dict:
    """Replay one note on observed historical prices.

    This is a historical replay, not a claim that a note was issued.
    """
    frame = pd.concat(
        {
            ticker: pd.Series(values, dtype=float)
            for ticker, values in prices.items()
            if ticker in spec.basket
        },
        axis=1,
    ).dropna()
    if frame.shape[1] != len(spec.basket) or len(frame) < 2:
        return {
            "source": "historical_replay",
            "status": "insufficient_data",
            "learning_eligible": False,
        }

    performance = frame / frame.iloc[0]
    observations = _observation_positions(
        len(performance), spec.observation_count,
    )
    coupons_paid = 0
    memory = 0
    autocall_observation: Optional[int] = None

    for obs_idx in observations:
        worst = float(performance.iloc[obs_idx].min())
        if worst >= spec.coupon_barrier:
            coupons_paid += memory + 1
            memory = 0
        else:
            memory += 1
        if worst >= spec.autocall_level:
            autocall_observation = int(obs_idx)
            break

    monitor_end = autocall_observation + 1 if autocall_observation is not None else len(performance)
    barrier_breached = bool(
        (performance.iloc[:monitor_end].min(axis=1) < spec.barrier).any()
    )

    if autocall_observation is not None:
        principal = 1.0
        outcome_type = "autocall"
    else:
        final = performance.iloc[-1]
        worst_final = float(final.min())
        principal = worst_final if barrier_breached else 1.0
        outcome_type = "knock_in_loss" if principal < 1.0 else "maturity_no_loss"

    payoff = principal + coupons_paid * spec.coupon_rate
    final_row = performance.iloc[-1]
    return {
        "source": "historical_replay",
        "status": "historical_replay",
        "learning_eligible": False,
        "outcome_type": outcome_type,
        "basket": list(spec.basket),
        "start": str(frame.index[0]),
        "end": str(frame.index[-1]),
        "barrier_breached": barrier_breached,
        "autocall_observation": autocall_observation,
        "coupons_paid": int(coupons_paid),
        "principal_return": round(principal, 6),
        "payoff": round(payoff, 6),
        "return_pct": round((payoff - 1.0) * 100, 4),
        "worst_of": str(final_row.idxmin()),
        "worst_final_pct": round(float(final_row.min()) * 100, 4),
    }


def _correlation_matrix(
    returns: Optional[pd.DataFrame],
    n_assets: int,
    correlation: Optional[np.ndarray],
) -> np.ndarray:
    if correlation is not None:
        matrix = np.asarray(correlation, dtype=float)
    elif returns is not None and returns.shape[1] == n_assets:
        matrix = returns.corr().to_numpy(dtype=float)
    else:
        matrix = np.full((n_assets, n_assets), 0.35)
        np.fill_diagonal(matrix, 1.0)
    matrix = np.nan_to_num(matrix, nan=0.0)
    matrix = (matrix + matrix.T) / 2
    np.fill_diagonal(matrix, 1.0)
    eigenvalue = float(np.min(np.linalg.eigvalsh(matrix)))
    if eigenvalue <= 0:
        matrix += np.eye(n_assets) * (-eigenvalue + 1e-6)
    return matrix


def simulate_monte_carlo(
    spec: StructuredNoteSpec,
    n_paths: int = 2_000,
    seed: int = 42,
    daily_vols: Optional[list[float]] = None,
    correlation: Optional[np.ndarray] = None,
    drift: float = 0.04,
    vol_multiplier: float = 1.0,
    drift_shift: float = 0.0,
) -> dict:
    """Simulate payoff distribution and label it ``source="simulated"``."""
    if n_paths < 100:
        raise ValueError("n_paths must be at least 100")
    n_assets = len(spec.basket)
    n_days = max(21, round(spec.term_months / 12 * 252))
    vols = np.asarray(daily_vols or [0.30] * n_assets, dtype=float) / np.sqrt(252)
    if len(vols) != n_assets:
        raise ValueError("daily_vols must match basket size")
    vols = vols * max(0.01, vol_multiplier)
    corr = _correlation_matrix(None, n_assets, correlation)
    chol = np.linalg.cholesky(corr)
    rng = np.random.default_rng(seed)
    shocks = rng.standard_normal((n_paths, n_days, n_assets))
    correlated = np.einsum("ij,sdj->sdi", chol, shocks)
    increments = (
        (drift + drift_shift - 0.5 * vols**2) / 252
        + correlated * vols
    )
    performance = np.exp(np.cumsum(increments, axis=1))
    observations = _observation_positions(n_days, spec.observation_count)
    alive = np.ones(n_paths, dtype=bool)
    coupons = np.zeros(n_paths)
    memory = np.zeros(n_paths, dtype=int)
    autocall = np.zeros(n_paths, dtype=bool)

    for obs_idx in observations:
        worst = performance[:, obs_idx, :].min(axis=1)
        coupon_eligible = alive
        coupon_paid = coupon_eligible & (worst >= spec.coupon_barrier)
        coupons[coupon_paid] += (memory[coupon_paid] + 1) * spec.coupon_rate
        memory[coupon_paid] = 0
        memory[coupon_eligible & ~coupon_paid] += 1
        new_autocall = alive & (worst >= spec.autocall_level)
        autocall |= new_autocall
        alive &= ~new_autocall

    first_autocall = np.full(n_paths, n_days, dtype=int)
    for obs_idx in observations:
        eligible = first_autocall == n_days
        worst = performance[:, obs_idx, :].min(axis=1)
        first_autocall[eligible & (worst >= spec.autocall_level)] = obs_idx
    barrier_breached = np.zeros(n_paths, dtype=bool)
    daily_worst = performance.min(axis=2)
    for day in range(n_days):
        barrier_breached |= (
            (first_autocall >= day) & (daily_worst[:, day] < spec.barrier)
        )

    final_worst = performance[:, -1, :].min(axis=1)
    principal = np.where(barrier_breached, np.minimum(1.0, final_worst), 1.0)
    principal[autocall] = 1.0
    payoffs = principal + coupons
    loss = payoffs < 1.0
    return {
        "source": "simulated",
        "status": "simulated",
        "scenario": {
            "vol_multiplier": vol_multiplier,
            "drift_shift": drift_shift,
        },
        "basket": list(spec.basket),
        "n_paths": int(n_paths),
        "seed": seed,
        "p_autocall": round(float(autocall.mean()), 6),
        "p_barrier_breach": round(float(barrier_breached.mean()), 6),
        "p_loss": round(float(loss.mean()), 6),
        "mean_payoff": round(float(payoffs.mean()), 6),
        "var_95": round(float(np.percentile(payoffs, 5)), 6),
        "cvar_95": round(float(payoffs[payoffs <= np.percentile(payoffs, 5)].mean()), 6),
        "mean_return_pct": round(float((payoffs.mean() - 1) * 100), 4),
    }


def simulate_stress_suite(
    spec: StructuredNoteSpec,
    n_paths: int = 2_000,
    seed: int = 42,
) -> dict:
    """Run base, volatility, bearish-drift, and high-correlation scenarios."""
    n_assets = len(spec.basket)
    high_corr = np.full((n_assets, n_assets), 0.85)
    np.fill_diagonal(high_corr, 1.0)
    scenarios = {
        "base": {},
        "volatility_up": {"vol_multiplier": 1.25},
        "bearish": {"drift_shift": -0.08},
        "correlation_up": {"correlation": high_corr},
    }
    results = {}
    for index, (name, overrides) in enumerate(scenarios.items()):
        results[name] = simulate_monte_carlo(
            spec, n_paths=n_paths, seed=seed + index, **overrides,
        )
    return {
        "source": "simulated",
        "status": "simulated",
        "basket": list(spec.basket),
        "scenarios": results,
    }


def replay_historical_windows(
    prices: Mapping[str, pd.Series | list[float]],
    spec: StructuredNoteSpec,
    window_days: int = 252,
    step_days: int = 21,
    max_windows: int = 50,
    predicted_p_loss: Optional[float] = None,
) -> dict:
    """Replay rolling historical windows and report realized replay metrics."""
    series = {
        ticker: pd.Series(values, dtype=float)
        for ticker, values in prices.items()
        if ticker in spec.basket
    }
    lengths = [len(value) for value in series.values()]
    if len(series) != len(spec.basket) or not lengths or min(lengths) < window_days:
        return {
            "source": "historical_replay",
            "status": "insufficient_data",
            "windows": [],
        }
    n_windows = min(max_windows, 1 + (min(lengths) - window_days) // step_days)
    results = []
    for index in range(n_windows):
        start = index * step_days
        window = {ticker: value.iloc[start:start + window_days] for ticker, value in series.items()}
        result = replay_historical(window, spec)
        result["window_index"] = index
        results.append(result)
    losses = [item["outcome_type"] == "knock_in_loss" for item in results]
    autocalls = [item["outcome_type"] == "autocall" for item in results]
    realized_loss = float(np.mean(losses)) if losses else 0.0
    report = {
        "source": "historical_replay",
        "status": "historical_replay",
        "basket": list(spec.basket),
        "n_windows": len(results),
        "realized_replay_loss_rate": round(realized_loss, 6),
        "autocall_rate": round(float(np.mean(autocalls)), 6) if autocalls else 0.0,
        "mean_return_pct": round(float(np.mean([item["return_pct"] for item in results])), 4),
        "windows": results,
    }
    if predicted_p_loss is not None:
        report["predicted_p_loss"] = float(predicted_p_loss)
        report["loss_rate_error"] = round(abs(realized_loss - predicted_p_loss), 6)
    return report


def evaluate_product_safety(
    product: dict,
    stress_report: Optional[dict] = None,
    quality_report: Optional[dict] = None,
    max_p_loss: float = 0.35,
    max_cvar: float = 0.65,
    min_baseline_lift: float = 0.0,
) -> dict:
    """Return a conservative recommendation gate for a product."""
    reasons: list[str] = []
    warnings: list[str] = []
    p_loss = float(product.get("p_loss_pct", 0.0)) / 100.0
    if p_loss > max_p_loss:
        reasons.append("model_p_loss_above_limit")
    if float(product.get("selected_vs_baseline", 0.0)) < min_baseline_lift:
        reasons.append("baseline_lift_below_limit")
    if stress_report:
        scenarios = stress_report.get("scenarios", {})
        worst_loss = max(float(item.get("p_loss", 0.0)) for item in scenarios.values())
        worst_cvar = min(float(item.get("cvar_95", 1.0)) for item in scenarios.values())
        if worst_loss > max_p_loss:
            reasons.append("stress_p_loss_above_limit")
        if worst_cvar < max_cvar:
            reasons.append("stress_cvar_below_limit")
    if quality_report:
        warnings.extend(quality_report.get("warnings", []))
        if quality_report.get("loss_rate_error") is not None and float(
            quality_report["loss_rate_error"]
        ) > 0.20:
            reasons.append("historical_loss_miscalibration")
    return {
        "passed": not reasons,
        "reasons": reasons,
        "warnings": warnings,
        "limits": {
            "max_p_loss": max_p_loss,
            "max_cvar": max_cvar,
            "min_baseline_lift": min_baseline_lift,
        },
    }


def build_quality_report(
    replay_report: dict,
    realized_outcomes: int = 0,
) -> dict:
    """Turn replay and realized sample sizes into an honest quality report."""
    windows = int(replay_report.get("n_windows", 0))
    replay_error = replay_report.get("loss_rate_error")
    warnings: list[str] = []
    if windows < 20:
        warnings.append("historical_sample_below_20_windows")
    if realized_outcomes < 5:
        warnings.append("realized_sample_below_5_notes")
    if replay_error is not None and float(replay_error) > 0.20:
        warnings.append("loss_probability_miscalibrated")
    if realized_outcomes >= 5 and windows >= 20:
        confidence = 0.85
    elif windows >= 20:
        confidence = 0.60
    else:
        confidence = 0.35
    if replay_error is not None:
        confidence *= max(0.25, 1.0 - min(float(replay_error), 0.75))
    return {
        "status": "calibrated" if not warnings else "limited_evidence",
        "confidence": round(confidence, 4),
        "confidence_pct": round(confidence * 100, 1),
        "historical_windows": windows,
        "realized_notes": int(realized_outcomes),
        "loss_rate_error": replay_error,
        "warnings": warnings,
        "source": "historical_replay_and_realized_only",
    }


def load_quality_report(path: Path = QUALITY_REPORT_PATH) -> dict:
    """Load the latest persisted quality report without triggering data access."""
    if not path.exists():
        return {"status": "not_available"}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {"status": "invalid"}


class PaperOutcomeTracker:
    """Persist paper notes and resolve them from supplied historical paths."""

    def __init__(self, path: Path = OUTCOME_PATH) -> None:
        self.path = path
        self.notes = self._load()

    def open_note(
        self,
        spec: StructuredNoteSpec,
        note_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        if note_id:
            for existing in self.notes:
                if existing.get("id") == note_id:
                    return existing
        note = {
            "id": note_id or f"{'_'.join(spec.basket)}_{_utc_now()}",
            "decision_id": (metadata or {}).get("decision_record", {}).get(
                "decision_id"
            ),
            "source": "paper",
            "status": "open",
            "spec": asdict(spec),
            "opened_at": _utc_now(),
            "maturity_date": (
                datetime.now(timezone.utc) + timedelta(days=spec.term_months * 30)
            ).date().isoformat(),
            "metadata": metadata or {},
        }
        self.notes.append(note)
        self._save()
        return note

    def resolve(self, note_id: str, prices: Mapping[str, pd.Series | list[float]]) -> dict:
        for note in self.notes:
            if note.get("id") != note_id:
                continue
            spec = StructuredNoteSpec(**note["spec"])
            outcome = replay_historical(prices, spec)
            if outcome.get("status") == "historical_replay":
                outcome = {
                    **outcome,
                    "source": "realized",
                    "status": "realized",
                    "learning_eligible": True,
                    "decision_id": note.get("decision_id"),
                }
                note["status"] = "realized"
                note["outcome"] = outcome
                note["learning_eligible"] = True
                self._save()
            return outcome
        return {"status": "not_found", "note_id": note_id}

    def refresh(
        self,
        note_id: str,
        prices: Mapping[str, pd.Series | list[float]],
        as_of: Optional[str] = None,
    ) -> dict:
        """Mark an open note to market, or realize it on termination/maturity."""
        for note in self.notes:
            if note.get("id") != note_id:
                continue
            spec = StructuredNoteSpec(**note["spec"])
            replay = replay_historical(prices, spec)
            if replay.get("status") == "insufficient_data":
                return {"source": "paper", "status": "insufficient_data", "note_id": note_id}
            observation_date = as_of or str(replay["end"])[:10]
            matured = observation_date >= note.get("maturity_date", observation_date)
            terminated = replay.get("outcome_type") == "autocall"
            if matured or terminated:
                return self.resolve(note_id, prices)
            paper_state = {
                "source": "paper",
                "status": "paper",
                "note_id": note_id,
                "decision_id": note.get("decision_id"),
                "basket": list(spec.basket),
                "as_of": observation_date,
                "barrier_breached": replay["barrier_breached"],
                "coupons_paid": replay["coupons_paid"],
                "worst_of": replay["worst_of"],
                "worst_final_pct": replay["worst_final_pct"],
                "learning_eligible": False,
            }
            note["current_state"] = paper_state
            self._save()
            return paper_state
        return {"status": "not_found", "note_id": note_id}

    def apply_realized_feedback(self, note_id: str) -> dict:
        """Feed a resolved note to learning components exactly once."""
        for note in self.notes:
            if note.get("id") != note_id:
                continue
            outcome = note.get("outcome", {})
            if note.get("status") != "realized" or not outcome.get("learning_eligible"):
                return {"status": "ignored", "reason": "not_realized"}
            if note.get("feedback_applied"):
                return {"status": "already_applied"}
            from src.basket.evolution import BasketEvolutionAgent

            spec = StructuredNoteSpec(**note["spec"])
            predicted_prob = float(note.get("metadata", {}).get("predicted_autocall_prob", 0.5))
            BasketEvolutionAgent().record_outcome(
                tickers=list(spec.basket),
                date=note["opened_at"],
                autocall_triggered=outcome.get("outcome_type") == "autocall",
                worst_of_asset=str(outcome.get("worst_of", "")),
                predicted_score=float(note.get("metadata", {}).get("predicted_score", 0.0)),
                predicted_prob=predicted_prob,
            )
            feedback = self._load_feedback()
            feedback.append({
                "note_id": note_id,
                "source": "realized",
                "learning_eligible": True,
                "outcome_type": outcome.get("outcome_type"),
                "agent_accuracies": note.get("metadata", {}).get("agent_accuracies", {}),
            })
            REALIZED_FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
            REALIZED_FEEDBACK_PATH.write_text(json.dumps(feedback[-500:], indent=2))
            calibration = {"status": "no_agent_accuracy_observations"}
            agent_history = [
                item for item in feedback
                if item.get("learning_eligible") and item.get("agent_accuracies")
            ]
            if len(agent_history) >= 5:
                from src.self_learning_agents import MetaAgent

                MetaAgent().update_weights(agent_history)
                calibration = {
                    "status": "updated",
                    "observations": len(agent_history),
                }
            note["feedback_applied"] = True
            self._save()
            return {
                "status": "applied",
                "note_id": note_id,
                "decision_id": note.get("decision_id"),
                "agent_calibration": calibration,
            }
        return {"status": "not_found", "note_id": note_id}

    def _load_feedback(self) -> list[dict]:
        if not REALIZED_FEEDBACK_PATH.exists():
            return []
        try:
            return json.loads(REALIZED_FEEDBACK_PATH.read_text())
        except Exception:
            return []
    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text()).get("notes", [])
        except Exception:
            return []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"notes": self.notes[-500:]}, indent=2))


def _main() -> None:
    parser = argparse.ArgumentParser(description="Structured-note outcome engine")
    parser.add_argument("--basket", nargs="+", default=["AAPL", "MSFT", "GOOGL"])
    parser.add_argument("--paths", type=int, default=2_000)
    args = parser.parse_args()
    spec = StructuredNoteSpec(basket=args.basket)
    print(json.dumps(simulate_stress_suite(spec, n_paths=args.paths), indent=2))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    _main()
