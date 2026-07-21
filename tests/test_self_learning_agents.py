"""Tests for src.self_learning_agents — 8 self-learning agents cascade."""

import pytest

from src.self_learning_agents import (
    SentimentAgent,
    RegimeAgent,
    AlphaAgent,
    RiskAgent,
    TimingAgent,
    CorrelationAgent,
    OverfitGuardian,
    MetaAgent,
    run_all_self_learning_agents,
)


@pytest.fixture
def yf_data() -> dict:
    return {
        "MSFT": {
            "spot": 450, "iv30": 22, "beta": 1.1, "pe": 35,
            "ema200_above": True, "ema200_pct": 8.5, "rec_mean": 1.8,
            "sector": "Technology", "hist_vol": 20,
            "return_1m": 0.04, "return_3m": 0.12,
        },
        "GOOGL": {
            "spot": 180, "iv30": 28, "beta": 1.2, "pe": 25,
            "ema200_above": True, "ema200_pct": 12.0, "rec_mean": 1.9,
            "sector": "Technology", "hist_vol": 25,
            "return_1m": 0.06, "return_3m": 0.15,
        },
    }


@pytest.fixture
def features() -> dict:
    return {
        "pki_norm": 0.4, "vol_norm": 0.3, "corr_norm": 0.5,
        "tox_norm": 0.25, "fund_norm": 0.7, "macro_norm": 0.6,
    }


@pytest.fixture
def tickers() -> list[str]:
    return ["MSFT", "GOOGL"]


# ── Sentiment Agent ──

def test_sentiment_returns_dict(tickers: list[str], yf_data: dict) -> None:
    agent = SentimentAgent()
    result = agent.predict(tickers, yf_data)
    assert result["agent"] == "sentiment"
    assert "per_ticker" in result
    assert "label" in result


def test_sentiment_scores_bounded(tickers: list[str], yf_data: dict) -> None:
    agent = SentimentAgent()
    result = agent.predict(tickers, yf_data)
    for score in result["per_ticker"].values():
        assert -1.0 <= score <= 1.0


def test_sentiment_label_valid(tickers: list[str], yf_data: dict) -> None:
    agent = SentimentAgent()
    result = agent.predict(tickers, yf_data)
    assert result["label"] in ("BULLISH", "BEARISH", "NEUTRAL")


# ── Regime Agent ──

def test_regime_returns_dict(tickers: list[str], yf_data: dict) -> None:
    agent = RegimeAgent()
    result = agent.predict(tickers, yf_data)
    assert result["agent"] == "regime"
    assert result["regime"] in ("BULL", "BEAR", "SIDEWAYS")


def test_regime_probabilities_sum_to_1(tickers: list[str], yf_data: dict) -> None:
    agent = RegimeAgent()
    result = agent.predict(tickers, yf_data)
    prob_sum = sum(result["probabilities"].values())
    assert abs(prob_sum - 1.0) < 0.01


def test_regime_confidence_bounded(tickers: list[str], yf_data: dict) -> None:
    agent = RegimeAgent()
    result = agent.predict(tickers, yf_data)
    assert 0 <= result["confidence"] <= 1


# ── Alpha Agent ──

def test_alpha_returns_dict(tickers: list[str], yf_data: dict, features: dict) -> None:
    agent = AlphaAgent()
    result = agent.predict(tickers, yf_data, features)
    assert result["agent"] == "alpha"
    assert "candidates_tested" in result
    assert "signals_found" in result


def test_alpha_candidates_tested(tickers: list[str], yf_data: dict, features: dict) -> None:
    agent = AlphaAgent()
    result = agent.predict(tickers, yf_data, features)
    assert result["candidates_tested"] > 0


# ── Risk Agent ──

def test_risk_returns_dict(tickers: list[str], yf_data: dict) -> None:
    agent = RiskAgent()
    result = agent.predict(tickers, yf_data)
    assert result["agent"] == "risk"
    assert "portfolio_var_95" in result
    assert "final_allocation" in result


def test_risk_allocation_bounded(tickers: list[str], yf_data: dict) -> None:
    agent = RiskAgent()
    result = agent.predict(tickers, yf_data, regime="BEAR")
    assert 0 < result["final_allocation"] <= 1.0


# ── Timing Agent ──

def test_timing_returns_dict(tickers: list[str], yf_data: dict) -> None:
    agent = TimingAgent()
    result = agent.predict(tickers, yf_data)
    assert result["agent"] == "timing"
    assert result["basket_signal"] in ("ENTER", "WAIT", "EXIT")


def test_timing_per_ticker(tickers: list[str], yf_data: dict) -> None:
    agent = TimingAgent()
    result = agent.predict(tickers, yf_data)
    for t in tickers:
        assert t in result["per_ticker"]


# ── Correlation Agent ──

def test_correlation_returns_dict(tickers: list[str], yf_data: dict) -> None:
    agent = CorrelationAgent()
    result = agent.predict(tickers, yf_data)
    assert result["agent"] == "correlation"
    assert "avg_correlation" in result


def test_correlation_bounded(tickers: list[str], yf_data: dict) -> None:
    agent = CorrelationAgent()
    result = agent.predict(tickers, yf_data)
    assert 0 <= result["avg_correlation"] <= 1


# ── Overfit Guardian ──

def test_guardian_returns_dict() -> None:
    guardian = OverfitGuardian()
    result = guardian.predict({}, current_accuracy=80, current_win_rate=78)
    assert result["agent"] == "overfit_guardian"
    assert result["safety_ok"] is True


def test_guardian_detects_unsafe() -> None:
    guardian = OverfitGuardian()
    result = guardian.predict({}, current_accuracy=60, current_win_rate=65)
    assert result["safety_ok"] is False
    assert result["recommendation"] == "ROLLBACK"


# ── Meta Agent ──

def test_meta_returns_dict() -> None:
    meta = MetaAgent()
    agent_results = {
        "sentiment": {"scoring_adj": 1.0, "confidence": 0.7},
        "regime": {"scoring_adj": -2.0, "confidence": 0.8},
    }
    result = meta.predict(agent_results, base_score=75)
    assert result["agent"] == "meta"
    assert "final_score" in result
    assert "decision" in result


def test_meta_decision_valid() -> None:
    meta = MetaAgent()
    result = meta.predict({}, base_score=75)
    assert result["decision"] in ("BUY", "HOLD", "AVOID")


def test_meta_walk_forward_update() -> None:
    meta = MetaAgent()
    history = [
        {"agent_accuracies": {"sentiment": 80, "alpha": 55}},
        {"agent_accuracies": {"sentiment": 82, "alpha": 58}},
        {"agent_accuracies": {"sentiment": 84, "alpha": 52}},
        {"agent_accuracies": {"sentiment": 83, "alpha": 54}},
        {"agent_accuracies": {"sentiment": 85, "alpha": 53}},
    ]
    before = dict(meta.weights)
    meta.update_weights(history)
    assert meta.weights["sentiment"] != before["sentiment"]
    assert sum(meta.weights.values()) == pytest.approx(1.0, abs=0.01)


# ── Full cascade ──

def test_run_all_agents(tickers: list[str], yf_data: dict, features: dict) -> None:
    result = run_all_self_learning_agents(
        tickers=tickers,
        yf_data=yf_data,
        features=features,
        base_score=75.0,
    )
    assert result["agents_run"] == 8
    assert result["agents_ok"] == 8
    assert "decision" in result


def test_run_all_agents_empty_data() -> None:
    result = run_all_self_learning_agents(
        tickers=["AAPL"],
        yf_data={},
        features={},
        base_score=70.0,
    )
    assert result["agents_run"] == 8
    # Some agents may still work with empty data
    assert result["agents_ok"] >= 4
