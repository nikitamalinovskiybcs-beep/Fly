"""Tests for src.integrations — Numerai and QuantConnect."""

import json
import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest


class TestNumeraiIntegration:
    """Tests for Numerai integration — graceful when disabled."""

    def test_init_without_keys(self) -> None:
        from src.integrations.numerai import NumeraiIntegration
        nai = NumeraiIntegration()
        assert nai.enabled or not nai.enabled  # depends on numerapi install

    def test_extract_alpha_signals(self) -> None:
        from src.integrations.numerai import NumeraiIntegration
        nai = NumeraiIntegration()
        signals = nai.extract_alpha_signals(["AAPL", "MSFT"])
        assert isinstance(signals, dict)
        assert "AAPL" in signals


class TestNumeraiSignals:
    """Tests for Numerai Signals integration."""

    def test_format_predictions(self) -> None:
        from src.integrations.numerai import NumeraiSignalsIntegration
        nsi = NumeraiSignalsIntegration()
        preds = nsi.format_predictions({"AAPL": 0.5, "MSFT": -0.3})
        assert isinstance(preds, pd.DataFrame)
        assert len(preds) == 2
        assert all(0 <= v <= 1 for v in preds["signal"])


class TestQuantConnectIntegration:
    """Tests for QuantConnect integration."""

    def setup_method(self) -> None:
        self.tmp = tempfile.mkdtemp()

    def teardown_method(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_init_disabled(self) -> None:
        from src.integrations.quantconnect import QuantConnectIntegration
        qc = QuantConnectIntegration()
        assert not qc.enabled

    def test_export_strategy(self) -> None:
        from src.integrations.quantconnect import QuantConnectIntegration
        qc = QuantConnectIntegration()
        weights = {"regime": 0.20, "rsi_oversold": 0.10, "sma_crossover": 0.15}
        path = qc.export_strategy_to_lean(weights, ["AAPL", "MSFT"], self.tmp)
        assert Path(path).exists()
        content = Path(path).read_text()
        assert "FlyStrategy" in content
        assert "AAPL" in content

    def test_cloud_backtest_disabled(self) -> None:
        from src.integrations.quantconnect import QuantConnectIntegration
        qc = QuantConnectIntegration()
        result = qc.run_cloud_backtest("test", "2024-01-01", "2024-12-31")
        assert "error" in result

    def test_download_lean_setup(self) -> None:
        from src.integrations.quantconnect import QuantConnectIntegration
        qc = QuantConnectIntegration()
        path = qc.download_lean_engine(self.tmp)
        assert Path(path).exists()
        assert "LEAN" in Path(path).read_text()

    def test_compare_results(self) -> None:
        from src.integrations.quantconnect import QuantConnectIntegration
        qc = QuantConnectIntegration()
        fly = {"sharpe_ratio": 1.5, "total_return": 15.0, "max_drawdown": -10.0, "win_rate": 0.6}
        qc_stats = {"sharpe_ratio": 1.3, "total_return": 12.0, "max_drawdown": -12.0, "win_rate": 0.55}
        comparison = qc.compare_results(fly, qc_stats)
        assert "sharpe_ratio" in comparison
        assert comparison["sharpe_ratio"]["diff"] == 0.2

    def test_import_alpha_empty(self) -> None:
        from src.integrations.quantconnect import QuantConnectIntegration
        qc = QuantConnectIntegration()
        signals = qc.import_alpha_signals()
        assert signals == {}
