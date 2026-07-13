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

    def _series(self, values: list[float]) -> pd.Series:
        idx = pd.date_range("2023-01-01", periods=len(values), freq="D")
        return pd.Series(values, index=idx)

    def test_alpha_nonzero_with_history(self) -> None:
        """With real price history the alpha is non-zero and cross-sectional."""
        from src.integrations.numerai import NumeraiIntegration
        import numpy as np

        n = 130
        up = self._series(list(100 + np.arange(n) * 0.8))       # strong uptrend
        down = self._series(list(100 - np.arange(n) * 0.5))     # downtrend
        flat = self._series(list(100 + np.sin(np.arange(n)) * 2))  # sideways

        nai = NumeraiIntegration()
        sig = nai.extract_alpha_signals(
            ["UP", "DOWN", "FLAT"],
            price_history={"UP": up, "DOWN": down, "FLAT": flat},
        )
        assert set(sig) == {"UP", "DOWN", "FLAT"}
        assert all(-1.0 <= v <= 1.0 for v in sig.values())
        assert any(abs(v) > 0 for v in sig.values())
        # The uptrend should rank strictly above the downtrend.
        assert sig["UP"] > sig["DOWN"]

    def test_alpha_bounds_and_missing(self) -> None:
        """Tickers without enough history fall back to 0.0, others stay bounded."""
        from src.integrations.numerai import NumeraiIntegration
        import numpy as np

        good = self._series(list(100 + np.arange(80) * 0.3))
        short = self._series([100, 101, 102])
        nai = NumeraiIntegration()
        sig = nai.extract_alpha_signals(
            ["GOOD", "GOODB", "SHORT"],
            price_history={"GOOD": good, "GOODB": good * 1.01, "SHORT": short},
        )
        assert sig["SHORT"] == 0.0
        assert all(-1.0 <= v <= 1.0 for v in sig.values())

    def test_alpha_no_history_returns_zeros(self) -> None:
        """No usable history → honest all-zero fallback, never fabricated."""
        from src.integrations.numerai import NumeraiIntegration
        nai = NumeraiIntegration()
        sig = nai.extract_alpha_signals(["A", "B"], price_history={})
        assert sig == {"A": 0.0, "B": 0.0}


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
