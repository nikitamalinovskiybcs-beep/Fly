"""Tests for src.autopilot — Autopilot Agent modules."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from src.autopilot.models import (
    HealthReport,
    HealthStatus,
    AlertLevel,
    AnalysisInsight,
    ParameterChange,
    DeploymentResult,
    DailyReport,
)
from src.autopilot.config import (
    TUNABLE_PARAMETERS,
    SAFETY_LIMITS,
    load_config,
    save_config,
    validate_parameter,
)
from src.autopilot.safety import SafetySystem
from src.autopilot.monitor import SystemMonitor
from src.autopilot.analyzer import PerformanceAnalyzer
from src.autopilot.optimizer import ParameterOptimizer
from src.autopilot.tester import ChangeValidator
from src.autopilot.deployer import SafeDeployer
from src.autopilot.reporter import AutopilotReporter
from src.autopilot.scheduler import AutopilotScheduler


# ── Models tests ──


class TestModels:
    def test_health_report_creation(self) -> None:
        report = HealthReport(
            timestamp=datetime.now(),
            status=HealthStatus.HEALTHY,
            sharpe_30d=1.5,
            win_rate_20=0.65,
            max_drawdown=0.05,
            open_positions=3,
            signals_quality=0.7,
            data_freshness_hours=2.0,
            disk_usage_pct=45.0,
        )
        assert report.status == HealthStatus.HEALTHY
        assert report.sharpe_30d == 1.5

    def test_health_status_values(self) -> None:
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.CRITICAL.value == "critical"
        assert HealthStatus.STOPPED.value == "stopped"

    def test_alert_level_values(self) -> None:
        assert AlertLevel.WARNING.value == "warning"
        assert AlertLevel.EMERGENCY.value == "emergency"

    def test_analysis_insight(self) -> None:
        insight = AnalysisInsight(
            timestamp=datetime.now(),
            category="signal_accuracy",
            finding="RSI win rate = 35%",
            metric_name="win_rate_rsi",
            metric_value=0.35,
            recommendation="Reduce weight for RSI signal",
            confidence=0.8,
            priority="high",
        )
        assert insight.priority == "high"
        assert insight.metric_value == 0.35

    def test_parameter_change(self) -> None:
        change = ParameterChange(
            parameter_name="confidence_threshold",
            current_value=0.65,
            proposed_value=0.60,
            change_pct=7.7,
            reason="test",
            backtest_sharpe_before=1.0,
            backtest_sharpe_after=1.2,
            improvement_pct=20.0,
            pbo_score=0.3,
            walk_forward_pass=True,
        )
        assert change.status == "proposed"
        assert change.proposed_value == 0.60

    def test_daily_report_defaults(self) -> None:
        report = DailyReport(
            date="2026-01-01",
            pnl_today=100.0,
            pnl_total=5000.0,
            trades_today=5,
            wins_today=3,
            losses_today=2,
            sharpe_30d=1.5,
            max_dd=0.08,
        )
        assert report.changes_today == []
        assert report.alerts_today == []


# ── Config tests ──


class TestConfig:
    def test_tunable_parameters_has_defaults(self) -> None:
        for name, spec in TUNABLE_PARAMETERS.items():
            assert "default" in spec, f"{name} missing default"
            assert "type" in spec, f"{name} missing type"

    def test_validate_parameter_float(self) -> None:
        assert validate_parameter("confidence_threshold", 0.65)
        assert validate_parameter("confidence_threshold", 0.40)
        assert validate_parameter("confidence_threshold", 0.90)
        assert not validate_parameter("confidence_threshold", 0.10)
        assert not validate_parameter("confidence_threshold", 1.5)

    def test_validate_parameter_bool(self) -> None:
        assert validate_parameter("trade_in_bear_regime", True)
        assert validate_parameter("trade_in_bear_regime", False)

    def test_validate_parameter_weights(self) -> None:
        good = {"regime": 0.20, "rsi_oversold": 0.10}
        assert validate_parameter("signal_weights", good)
        bad = {"regime": 0.01}
        assert not validate_parameter("signal_weights", bad)

    def test_validate_unknown_parameter(self) -> None:
        assert not validate_parameter("nonexistent_param", 42)

    def test_load_config_defaults(self, tmp_path: Path) -> None:
        import src.autopilot.config as cfg
        orig = cfg.CONFIG_FILE
        cfg.CONFIG_FILE = tmp_path / "nonexistent.json"
        config = load_config()
        assert "confidence_threshold" in config
        assert config["confidence_threshold"] == 0.65
        cfg.CONFIG_FILE = orig

    def test_save_and_load_config(self, tmp_path: Path) -> None:
        import src.autopilot.config as cfg
        orig_data = cfg.DATA_DIR
        orig_config = cfg.CONFIG_FILE
        cfg.DATA_DIR = tmp_path
        cfg.CONFIG_FILE = tmp_path / "config.json"

        config = {"confidence_threshold": 0.55, "kelly_fraction": 0.20}
        save_config(config)
        loaded = load_config()
        assert loaded["confidence_threshold"] == 0.55

        cfg.DATA_DIR = orig_data
        cfg.CONFIG_FILE = orig_config

    def test_safety_limits(self) -> None:
        assert SAFETY_LIMITS["max_changes_per_day"] == 3
        assert SAFETY_LIMITS["max_pbo_to_deploy"] == 0.50


# ── Safety tests ──


class TestSafety:
    def test_kill_switch_default_off(self, tmp_path: Path) -> None:
        import src.autopilot.safety as mod
        orig = mod.KILL_SWITCH_FILE
        mod.KILL_SWITCH_FILE = tmp_path / "KILL_SWITCH"
        safety = SafetySystem()
        assert not safety.check_kill_switch()
        mod.KILL_SWITCH_FILE = orig

    def test_kill_switch_engage_disengage(self, tmp_path: Path) -> None:
        import src.autopilot.safety as mod
        orig_data = mod.DATA_DIR
        orig_ks = mod.KILL_SWITCH_FILE
        mod.DATA_DIR = tmp_path
        mod.KILL_SWITCH_FILE = tmp_path / "KILL_SWITCH"

        safety = SafetySystem()
        safety.engage_kill_switch("test")
        assert safety.check_kill_switch()
        safety.disengage_kill_switch()
        assert not safety.check_kill_switch()

        mod.DATA_DIR = orig_data
        mod.KILL_SWITCH_FILE = orig_ks

    def test_max_drawdown_safe(self) -> None:
        safety = SafetySystem()
        assert safety.check_max_drawdown(0.05)
        assert safety.check_max_drawdown(0.15)

    def test_max_drawdown_unsafe(self) -> None:
        safety = SafetySystem()
        assert not safety.check_max_drawdown(0.25)

    def test_consecutive_losses_safe(self) -> None:
        safety = SafetySystem()
        results = [True, True, False, True, False, False]
        assert safety.check_consecutive_losses(results)

    def test_consecutive_losses_unsafe(self) -> None:
        safety = SafetySystem()
        results = [True, False, False, False, False, False]
        assert not safety.check_consecutive_losses(results)

    def test_validate_change_magnitude(self) -> None:
        safety = SafetySystem()
        assert safety.validate_change_magnitude("confidence_threshold", 0.65, 0.70)
        assert not safety.validate_change_magnitude("confidence_threshold", 0.65, 0.90)


# ── Monitor tests ──


class TestMonitor:
    def test_health_check_returns_report(self) -> None:
        monitor = SystemMonitor()
        health = monitor.check_health()
        assert isinstance(health, HealthReport)
        assert health.status in list(HealthStatus)

    def test_safe_to_trade_default(self) -> None:
        monitor = SystemMonitor()
        result = monitor.is_safe_to_trade()
        assert isinstance(result, bool)

    def test_disk_usage(self) -> None:
        monitor = SystemMonitor()
        pct = monitor._disk_usage_pct()
        assert 0 <= pct <= 100


# ── Analyzer tests ──


class TestAnalyzer:
    def test_daily_analysis_empty(self) -> None:
        analyzer = PerformanceAnalyzer()
        insights = analyzer.daily_analysis()
        assert isinstance(insights, list)

    def test_signal_accuracy_analysis(self) -> None:
        analyzer = PerformanceAnalyzer()
        trades = [
            {"signal_type": "rsi", "regime": "bull", "pnl": -10},
            {"signal_type": "rsi", "regime": "bull", "pnl": -5},
            {"signal_type": "rsi", "regime": "bull", "pnl": -3},
            {"signal_type": "rsi", "regime": "bull", "pnl": -8},
            {"signal_type": "rsi", "regime": "bull", "pnl": -2},
            {"signal_type": "rsi", "regime": "bull", "pnl": 1},
        ]
        insights = analyzer._analyze_signal_accuracy(trades)
        assert len(insights) >= 1
        assert any("rsi" in i.finding.lower() for i in insights)

    def test_ticker_performance_analysis(self) -> None:
        analyzer = PerformanceAnalyzer()
        trades = [{"ticker": "TSLA", "pnl": -5}] * 12
        insights = analyzer._analyze_ticker_performance(trades)
        assert len(insights) >= 1

    def test_regime_effectiveness(self) -> None:
        analyzer = PerformanceAnalyzer()
        trades = [{"regime": "bear", "pnl": -10}] * 10
        insights = analyzer._analyze_regime_effectiveness(trades)
        assert len(insights) >= 1


# ── Optimizer tests ──


class TestOptimizer:
    def test_optimize_empty_insights(self) -> None:
        optimizer = ParameterOptimizer()
        proposals = optimizer.optimize([])
        assert proposals == []

    def test_optimize_with_insight(self) -> None:
        optimizer = ParameterOptimizer()
        insight = AnalysisInsight(
            timestamp=datetime.now(),
            category="regime",
            finding="Bear regime Sharpe negative",
            metric_name="sharpe_bear",
            metric_value=-0.5,
            recommendation="Disable trading in bear regime",
            confidence=0.9,
            priority="high",
        )
        proposals = optimizer.optimize([insight])
        assert len(proposals) >= 1

    def test_optimize_continuous(self) -> None:
        optimizer = ParameterOptimizer()
        rng = np.random.default_rng(42)
        returns = rng.normal(0.001, 0.02, 100)
        result = optimizer.optimize_continuous("confidence_threshold", returns)
        assert 0.40 <= result <= 0.90

    def test_grid_search(self) -> None:
        optimizer = ParameterOptimizer()
        rng = np.random.default_rng(42)
        returns = rng.normal(0.001, 0.02, 100)
        result = optimizer.grid_search("sma_fast_period", [20, 50, 100], returns)
        assert result in [20, 50, 100]


# ── Tester tests ──


class TestTester:
    def test_validate_approved(self) -> None:
        tester = ChangeValidator()
        rng = np.random.default_rng(42)
        returns = rng.normal(0.002, 0.01, 100)

        change = ParameterChange(
            parameter_name="confidence_threshold",
            current_value=0.65,
            proposed_value=0.60,
            change_pct=7.7,
            reason="test",
            backtest_sharpe_before=0.0,
            backtest_sharpe_after=0.0,
            improvement_pct=0.0,
            pbo_score=0.0,
            walk_forward_pass=False,
        )
        result = tester.validate(change, returns)
        assert result.status in ("approved", "rejected")
        assert result.backtest_sharpe_before != 0.0 or result.backtest_sharpe_after != 0.0

    def test_validate_too_few_trades(self) -> None:
        tester = ChangeValidator()
        change = ParameterChange(
            parameter_name="confidence_threshold",
            current_value=0.65, proposed_value=0.60,
            change_pct=7.7, reason="test",
            backtest_sharpe_before=0.0, backtest_sharpe_after=0.0,
            improvement_pct=0.0, pbo_score=0.0, walk_forward_pass=False,
        )
        result = tester.validate(change, np.array([0.01, -0.01]))
        assert result.status == "rejected"

    def test_compute_sharpe(self) -> None:
        tester = ChangeValidator()
        rng = np.random.default_rng(42)
        returns = rng.normal(0.001, 0.01, 100)
        sr = tester._compute_sharpe(returns)
        assert isinstance(sr, float)


# ── Deployer tests ──


class TestDeployer:
    def test_deploy_creates_trial(self, tmp_path: Path) -> None:
        import src.autopilot.config as cfg
        import src.autopilot.deployer as dep
        import src.autopilot.safety as saf

        orig_data = cfg.DATA_DIR
        orig_config = cfg.CONFIG_FILE
        orig_snap = cfg.SNAPSHOT_DIR
        orig_trial = dep.TRIAL_FILE
        orig_deploy_log = saf.DEPLOY_LOG_FILE
        orig_saf_data = saf.DATA_DIR

        cfg.DATA_DIR = tmp_path
        cfg.CONFIG_FILE = tmp_path / "config.json"
        cfg.SNAPSHOT_DIR = tmp_path / "snapshots"
        dep.TRIAL_FILE = tmp_path / "trial.json"
        dep.DATA_DIR = tmp_path
        saf.DEPLOY_LOG_FILE = tmp_path / "deploy_log.json"
        saf.DATA_DIR = tmp_path

        save_config({"confidence_threshold": 0.65})

        deployer = SafeDeployer()
        change = ParameterChange(
            parameter_name="confidence_threshold",
            current_value=0.65, proposed_value=0.60,
            change_pct=7.7, reason="test",
            backtest_sharpe_before=1.0, backtest_sharpe_after=1.2,
            improvement_pct=20.0, pbo_score=0.3, walk_forward_pass=True,
            status="approved",
        )
        result = deployer.deploy(change)
        assert result.accepted

        cfg.DATA_DIR = orig_data
        cfg.CONFIG_FILE = orig_config
        cfg.SNAPSHOT_DIR = orig_snap
        dep.TRIAL_FILE = orig_trial
        saf.DEPLOY_LOG_FILE = orig_deploy_log
        saf.DATA_DIR = orig_saf_data


# ── Reporter tests ──


class TestReporter:
    def test_daily_report(self, tmp_path: Path) -> None:
        import src.autopilot.reporter as rep
        orig = rep.REPORTS_DIR
        rep.REPORTS_DIR = tmp_path / "reports"

        reporter = AutopilotReporter()
        trades = [{"date": datetime.now().strftime("%Y-%m-%d"), "pnl": 50}]
        equity = [100.0, 105.0, 110.0, 108.0]
        report = reporter.daily_report(trades, equity, [], [])
        assert isinstance(report, DailyReport)
        assert report.pnl_today >= 0

        rep.REPORTS_DIR = orig

    def test_format_telegram(self) -> None:
        reporter = AutopilotReporter()
        report = DailyReport(
            date="2026-01-01", pnl_today=100.0, pnl_total=5000.0,
            trades_today=5, wins_today=3, losses_today=2,
            sharpe_30d=1.5, max_dd=0.08,
        )
        msg = reporter._format_daily_telegram(report)
        assert "Fly Daily Report" in msg
        assert "100.00" in msg


# ── Scheduler tests ──


class TestScheduler:
    def test_scheduler_creation(self) -> None:
        scheduler = AutopilotScheduler()
        assert not scheduler.running
        assert scheduler.monitor is not None
        assert scheduler.analyzer is not None

    def test_run_once(self) -> None:
        scheduler = AutopilotScheduler()
        results = scheduler.run_once()
        assert "health" in results
        assert "analysis" in results
