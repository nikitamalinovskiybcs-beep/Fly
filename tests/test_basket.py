"""Tests for src.basket — scoring, copula, autocall, evolution, alerts."""

import json
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


class TestBasketModels:
    """Tests for basket data models."""

    def test_basket_grade_enum(self) -> None:
        from src.basket.models import BasketGrade
        assert BasketGrade.A_PLUS.value == "A+"
        assert BasketGrade.F.value == "F"

    def test_red_flag(self) -> None:
        from src.basket.models import RedFlag
        flag = RedFlag(severity="critical", asset="AAPL", flag_type="micro_cap",
                      description="Market cap < $1B", value=0.5e9)
        assert flag.severity == "critical"

    def test_asset_profile(self) -> None:
        from src.basket.models import AssetProfile
        ap = AssetProfile(ticker="MSFT", price=400.0, market_cap=3e12)
        assert ap.is_profitable
        assert ap.sector == "Unknown"

    def test_criterion_score(self) -> None:
        from src.basket.models import CriterionScore
        cs = CriterionScore(name="liquidity", weight=0.10, raw_score=80, weighted_score=8.0)
        assert cs.weighted_score == 8.0

    def test_basket_report(self) -> None:
        from src.basket.models import BasketReport, BasketGrade
        report = BasketReport(basket_name="test", tickers=["AAPL"])
        assert report.grade == BasketGrade.C
        assert report.red_flag_count == 0

    def test_evolution_log(self) -> None:
        from src.basket.models import EvolutionLog
        log = EvolutionLog(timestamp="2024-01-01", trigger="scheduled")
        assert not log.prediction_correct


class TestBasketScorer:
    """Tests for the main basket scorer."""

    def test_weights_sum_to_one(self) -> None:
        from src.basket.scorer import BasketScorer
        scorer = BasketScorer()
        total = sum(scorer.WEIGHTS.values())
        assert abs(total - 1.0) < 0.01

    def test_criterion_scores_0_to_100(self) -> None:
        from src.basket.models import AssetProfile
        from src.basket.scorer import BasketScorer
        scorer = BasketScorer()
        assets = [AssetProfile(ticker="TEST", price=100, market_cap=50e9,
                               daily_volume_usd=100e6, atr_pct=0.02, evt_var_95=-0.03,
                               max_drawdown_60d=-0.10, is_profitable=True)]
        score = scorer._score_liquidity(assets)
        assert 0 <= score.raw_score <= 100

    def test_grade_map(self) -> None:
        from src.basket.models import BasketGrade, RedFlag
        from src.basket.scorer import BasketScorer
        scorer = BasketScorer()
        assert scorer._assign_grade(95, []) == BasketGrade.A_PLUS
        assert scorer._assign_grade(75, []) == BasketGrade.B_PLUS
        assert scorer._assign_grade(35, []) == BasketGrade.F

    def test_critical_flags_cap_grade(self) -> None:
        from src.basket.models import BasketGrade, RedFlag
        from src.basket.scorer import BasketScorer
        scorer = BasketScorer()
        flags = [RedFlag("critical", "AAPL", "micro_cap", "too small")]
        grade = scorer._assign_grade(95, flags)
        assert grade == BasketGrade.D

    def test_detect_red_flags_micro_cap(self) -> None:
        from src.basket.models import AssetProfile
        from src.basket.scorer import BasketScorer
        scorer = BasketScorer()
        assets = [AssetProfile(ticker="SMALL", market_cap=500e6)]
        flags = scorer._detect_red_flags(assets)
        assert any(f.flag_type == "micro_cap" for f in flags)

    def test_detect_red_flags_unprofitable(self) -> None:
        from src.basket.models import AssetProfile
        from src.basket.scorer import BasketScorer
        scorer = BasketScorer()
        assets = [AssetProfile(ticker="LOSS", market_cap=10e9, is_profitable=False)]
        flags = scorer._detect_red_flags(assets)
        assert any(f.flag_type == "unprofitable" for f in flags)

    def test_detect_red_flags_extreme_dd(self) -> None:
        from src.basket.models import AssetProfile
        from src.basket.scorer import BasketScorer
        scorer = BasketScorer()
        assets = [AssetProfile(ticker="DROP", market_cap=10e9, max_drawdown_60d=-0.40)]
        flags = scorer._detect_red_flags(assets)
        assert any(f.flag_type == "extreme_drawdown" for f in flags)

    def test_recommendation_avoid(self) -> None:
        from src.basket.models import BasketGrade, RedFlag
        from src.basket.scorer import BasketScorer
        scorer = BasketScorer()
        flags = [RedFlag("critical", "X", "test", "test")]
        rec = scorer._make_recommendation(90, BasketGrade.D, flags)
        assert "AVOID" in rec

    def test_recommendation_buy(self) -> None:
        from src.basket.models import BasketGrade
        from src.basket.scorer import BasketScorer
        scorer = BasketScorer()
        rec = scorer._make_recommendation(85, BasketGrade.A, [])
        assert "STRONG BUY" in rec


class TestCopulaAnalyzer:
    """Tests for copula analysis."""

    def test_fit_basic(self) -> None:
        from src.basket.copula import CopulaAnalyzer
        rng = np.random.default_rng(42)
        df = pd.DataFrame({
            "A": rng.standard_normal(100) * 0.02,
            "B": rng.standard_normal(100) * 0.02,
        })
        result = CopulaAnalyzer().fit(df)
        assert "normal_corr" in result
        assert "crisis_corr" in result

    def test_fit_too_short(self) -> None:
        from src.basket.copula import CopulaAnalyzer
        df = pd.DataFrame({"A": [0.01], "B": [-0.01]})
        result = CopulaAnalyzer().fit(df)
        assert result["normal_corr"] == 0.0


class TestAutocallEngine:
    """Tests for autocall MC engine."""

    def test_basic_probabilities(self) -> None:
        from src.basket.autocall import AutocallEngine
        engine = AutocallEngine()
        result = engine.calculate_probabilities(
            tickers=["AAPL", "MSFT"],
            strikes={"AAPL": 150.0, "MSFT": 300.0},
            observation_dates=["2027-06-01", "2027-12-01"],
            n_sims=1000,
        )
        assert "total_autocall_prob" in result
        assert "worst_of_prediction" in result

    def test_empty_input(self) -> None:
        from src.basket.autocall import AutocallEngine
        engine = AutocallEngine()
        result = engine.calculate_probabilities([], {}, observation_dates=[])
        assert "error" in result


class TestWorstOfPredictor:
    """Tests for worst-of prediction."""

    def test_predict_basic(self) -> None:
        from src.basket.models import AssetProfile
        from src.basket.worst_of import WorstOfPredictor
        assets = [
            AssetProfile(ticker="SAFE", distance_to_barrier_pct=0.40, atr_pct=0.02, max_drawdown_60d=-0.05),
            AssetProfile(ticker="RISKY", distance_to_barrier_pct=0.08, atr_pct=0.06, max_drawdown_60d=-0.35),
        ]
        probs = WorstOfPredictor().predict(assets)
        assert probs["RISKY"] > probs["SAFE"]

    def test_predict_empty(self) -> None:
        from src.basket.worst_of import WorstOfPredictor
        assert WorstOfPredictor().predict([]) == {}


class TestSector:
    """Tests for sector classification."""

    def test_unique_count(self) -> None:
        from src.basket.sector import unique_sector_count
        assert unique_sector_count(["Technology", "Healthcare", "Technology"]) == 2

    def test_is_mainstream(self) -> None:
        from src.basket.sector import is_mainstream
        assert is_mainstream("Technology")
        assert not is_mainstream("Crypto")


class TestBasketAlerts:
    """Tests for alert system."""

    def test_near_barrier_alert(self) -> None:
        from src.basket.alerts import BasketAlertSystem
        from src.basket.models import AssetProfile, BasketReport
        report = BasketReport(
            basket_name="test", tickers=["X"],
            assets=[AssetProfile(ticker="X", distance_to_barrier_pct=0.03)],
        )
        alerts = BasketAlertSystem().check_alerts(report)
        assert any(a["type"] == "near_barrier" for a in alerts)

    def test_no_alerts_safe(self) -> None:
        from src.basket.alerts import BasketAlertSystem
        from src.basket.models import AssetProfile, BasketReport
        report = BasketReport(
            basket_name="test", tickers=["X"],
            assets=[AssetProfile(ticker="X", distance_to_barrier_pct=0.50)],
        )
        alerts = BasketAlertSystem().check_alerts(report)
        assert len(alerts) == 0


class TestEvolution:
    """Tests for evolution agent."""

    def setup_method(self) -> None:
        self.tmp = tempfile.mkdtemp()

    def teardown_method(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_default_weights(self) -> None:
        from src.basket.evolution import BasketEvolutionAgent
        agent = BasketEvolutionAgent()
        agent.WEIGHTS_PATH = Path(self.tmp) / "w.json"
        agent.LOG_PATH = Path(self.tmp) / "l.json"
        weights = agent.weights
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_weights_within_bounds(self) -> None:
        from src.basket.evolution import BasketEvolutionAgent
        agent = BasketEvolutionAgent()
        for v in agent.weights.values():
            assert 0.05 <= v <= 0.40

    def test_evolve_insufficient(self) -> None:
        from src.basket.evolution import BasketEvolutionAgent
        agent = BasketEvolutionAgent()
        agent.WEIGHTS_PATH = Path(self.tmp) / "w.json"
        agent.LOG_PATH = Path(self.tmp) / "l.json"
        agent._outcomes = []
        result = agent.evolve()
        assert result["status"] == "insufficient_data"

    def test_record_outcome(self) -> None:
        from src.basket.evolution import BasketEvolutionAgent
        agent = BasketEvolutionAgent()
        agent.WEIGHTS_PATH = Path(self.tmp) / "w.json"
        agent.LOG_PATH = Path(self.tmp) / "l.json"
        agent.record_outcome(["AAPL", "MSFT"], "2024-01-01", True, "MSFT", 75.0, 0.8)
        assert len(agent._outcomes) >= 1


class TestMacroOverlay:
    """Tests for macro overlay."""

    def test_impact_sectors(self) -> None:
        from src.basket.macro import MacroOverlay
        overlay = MacroOverlay()
        impacts = overlay.impact_on_basket(["Technology", "Energy", "Utilities"])
        assert "Technology" in impacts
        assert "Utilities" in impacts
