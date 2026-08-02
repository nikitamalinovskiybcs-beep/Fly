"""Tests for src.phoenix — models, barrier risk, pricing, greeks."""

import pytest


class TestPhoenixModels:
    """Tests for Phoenix dataclass models."""

    def test_greeks_report(self) -> None:
        from src.phoenix.models import GreeksReport
        gr = GreeksReport(ticker="AAPL", delta=0.5, gamma=0.01, vega=0.1,
                         theta=-0.05, rho=0.02, barrier_delta=0.03, digital_risk=0.05)
        assert gr.ticker == "AAPL"
        assert gr.delta == 0.5

    def test_vol_surface(self) -> None:
        from src.phoenix.models import VolSurface, VolPoint
        vs = VolSurface(ticker="MSFT", atm_iv=0.30, skew_25d=1.1,
                        term_structure=[VolPoint(strike=100, expiry_days=30, iv=0.32)])
        assert vs.atm_iv == 0.30
        assert len(vs.term_structure) == 1

    def test_barrier_risk_report(self) -> None:
        from src.phoenix.models import BarrierRiskReport
        br = BarrierRiskReport(ticker="AAPL", spot=150, barrier=90, distance_pct=0.667,
                               barrier_delta=0.02, gap_risk_overnight=0.001, digital_risk_pct=0.03)
        assert br.distance_pct == 0.667

    def test_pricing_result(self) -> None:
        from src.phoenix.models import PhoenixPricingResult
        pr = PhoenixPricingResult(fair_value_pct=98.5)
        assert pr.fair_value_pct == 98.5
        assert pr.worst_of_asset == ""

    def test_dividend_forecast(self) -> None:
        from src.phoenix.models import DividendForecast
        df = DividendForecast(ticker="JNJ", current_yield=0.028, forward_yield=0.030)
        assert df.current_yield == 0.028

    def test_implied_correlation(self) -> None:
        from src.phoenix.models import ImpliedCorrelationResult
        ic = ImpliedCorrelationResult(realized_correlation=0.6, implied_correlation=0.7,
                                       correlation_risk_premium=0.1, is_overpriced=True)
        assert ic.is_overpriced


class TestBarrierRiskAnalyzer:
    """Tests for barrier risk analysis."""

    def test_analyze_basic(self) -> None:
        from src.phoenix.barrier_risk import BarrierRiskAnalyzer
        analyzer = BarrierRiskAnalyzer()
        report = analyzer.analyze("TEST", spot=150.0, barrier=90.0, iv=0.30, days_to_next_obs=30)
        assert report.ticker == "TEST"
        assert report.distance_pct > 0.5
        assert report.gap_risk_overnight >= 0.0
        assert report.digital_risk_pct >= 0.0

    def test_analyze_near_barrier(self) -> None:
        from src.phoenix.barrier_risk import BarrierRiskAnalyzer
        analyzer = BarrierRiskAnalyzer()
        report = analyzer.analyze("TEST", spot=92.0, barrier=90.0, iv=0.30)
        assert report.distance_pct < 0.05

    def test_analyze_zero_spot(self) -> None:
        from src.phoenix.barrier_risk import BarrierRiskAnalyzer
        analyzer = BarrierRiskAnalyzer()
        report = analyzer.analyze("TEST", spot=0.0, barrier=90.0)
        assert report.barrier_delta == 0.0


class TestPhoenixPricing:
    """Tests for Phoenix MC pricing engine."""

    def test_price_basic(self) -> None:
        from src.phoenix.pricing import PhoenixPricingEngine
        engine = PhoenixPricingEngine()
        result = engine.price(
            tickers=["AAPL", "MSFT"],
            strikes={"AAPL": 150.0, "MSFT": 300.0},
            barrier_pct=0.60,
            observation_dates=["2027-03-01", "2027-06-01", "2027-09-01", "2027-12-01"],
            coupon_rate=0.10,
            notional=100.0,
            n_simulations=1000,
        )
        assert result.fair_value_pct > 0
        assert len(result.autocall_probabilities) == 4

    def test_price_empty(self) -> None:
        from src.phoenix.pricing import PhoenixPricingEngine
        engine = PhoenixPricingEngine()
        result = engine.price(tickers=[], strikes={}, observation_dates=[])
        assert result.fair_value_pct == 0.0

    def test_price_rejects_non_monotonic_observations(self) -> None:
        from src.phoenix.pricing import PhoenixPricingEngine
        with pytest.raises(ValueError, match="strictly increasing"):
            PhoenixPricingEngine().price(
                tickers=["AAPL"],
                strikes={"AAPL": 150.0},
                observation_dates=["2027-06-01", "2027-03-01"],
                n_simulations=100,
            )


class TestPhoenixGreeks:
    """Tests for Phoenix Greeks engine."""

    def test_greeks_empty(self) -> None:
        from src.phoenix.greeks import PhoenixGreeksEngine
        engine = PhoenixGreeksEngine()
        result = engine.calculate_all(tickers=[], strikes={}, observation_dates=[])
        assert result == []


class TestImpliedVolEngine:
    """Tests for implied vol engine — fallback behavior."""

    def test_historical_vol_estimate(self) -> None:
        from src.phoenix.implied_vol import ImpliedVolEngine
        engine = ImpliedVolEngine()
        estimate = engine._historical_vol_estimate("INVALID_TICKER_XYZ123")
        assert estimate == 0.30 or estimate > 0

    def test_skew_default(self) -> None:
        from src.phoenix.implied_vol import ImpliedVolEngine
        engine = ImpliedVolEngine()
        skew = engine.get_skew("INVALID_TICKER_XYZ123")
        assert skew == 1.0

    def test_iv_percentile_default(self) -> None:
        from src.phoenix.implied_vol import ImpliedVolEngine
        engine = ImpliedVolEngine()
        pct = engine.get_iv_percentile("INVALID_TICKER_XYZ123")
        assert 0.0 <= pct <= 1.0


class TestImpliedCorrelation:
    """Tests for implied correlation engine."""

    def test_single_ticker(self) -> None:
        from src.phoenix.implied_corr import ImpliedCorrelationEngine
        engine = ImpliedCorrelationEngine()
        result = engine.calculate(["AAPL"])
        assert result.realized_correlation == 0.0
        assert result.implied_correlation == 0.0


class TestLocalVolSurface:
    """Tests for local vol surface."""

    def test_default_get_local_vol(self) -> None:
        from src.phoenix.local_vol import LocalVolSurface
        surface = LocalVolSurface()
        vol = surface.get_local_vol(100.0, 0.5)
        assert vol == 0.30
