"""Tests for the data layer (live feed, providers, data manager)."""

import pandas as pd
import pytest

from src.data import DataManager, LiveFeed
from src.data.providers import ProviderChain, YFinanceProvider


class _FakeProvider:
    name = "fake"

    def __init__(self, df=None, price=None):
        self._df = df if df is not None else pd.DataFrame()
        self._price = price

    def history(self, ticker, period="1y", interval="1d"):
        return self._df

    def last_price(self, ticker):
        return self._price


class TestLiveFeed:
    def test_subscribe_dedup(self):
        feed = LiveFeed()
        feed.subscribe(["AAPL", "AAPL", "MSFT"])
        assert feed.subscriptions == ["AAPL", "MSFT"]

    def test_emit_updates_latest_and_callbacks(self):
        feed = LiveFeed()
        received = {}
        feed.on_price(lambda t, p, ts: received.update({t: p}))
        feed._emit("AAPL", 150.0, 0)
        assert feed.get_latest("AAPL") == 150.0
        assert received["AAPL"] == 150.0

    def test_is_crypto(self):
        feed = LiveFeed()
        assert feed._is_crypto("BTCUSDT")
        assert not feed._is_crypto("AAPL")

    def test_start_without_ws_returns_false(self):
        feed = LiveFeed()
        feed._ws_available = False
        feed.subscribe(["AAPL"])
        assert feed.start() is False

    def test_callback_error_is_swallowed(self):
        feed = LiveFeed()

        def bad(t, p, ts):
            raise RuntimeError("boom")

        feed.on_price(bad)
        feed._emit("AAPL", 1.0, 0)  # must not raise
        assert feed.get_latest("AAPL") == 1.0


class TestProviderChain:
    def test_falls_through_to_working_provider(self):
        df = pd.DataFrame({"Close": [1, 2, 3]})
        chain = ProviderChain([_FakeProvider(), _FakeProvider(df=df)])
        assert not chain.history("AAPL").empty

    def test_last_price_first_hit(self):
        chain = ProviderChain([_FakeProvider(price=None), _FakeProvider(price=42.0)])
        assert chain.last_price("AAPL") == 42.0

    def test_yfinance_provider_name(self):
        assert YFinanceProvider().name == "yfinance"


class TestDataManager:
    def test_get_price_prefers_live(self):
        feed = LiveFeed()
        feed._emit("AAPL", 200.0, 0)
        dm = DataManager(providers=ProviderChain([_FakeProvider(price=100.0)]), live_feed=feed)
        assert dm.get_price("AAPL") == 200.0  # live wins

    def test_get_price_falls_back_to_provider(self):
        dm = DataManager(providers=ProviderChain([_FakeProvider(price=100.0)]), live_feed=LiveFeed())
        assert dm.get_price("AAPL") == 100.0

    def test_get_prices_filters_none(self):
        dm = DataManager(providers=ProviderChain([_FakeProvider(price=None)]), live_feed=LiveFeed())
        assert dm.get_prices(["AAPL", "MSFT"]) == {}

    def test_get_history(self):
        df = pd.DataFrame({"Close": [1, 2, 3]})
        dm = DataManager(providers=ProviderChain([_FakeProvider(df=df)]), live_feed=LiveFeed())
        assert len(dm.get_history("AAPL")) == 3

    def test_live_available_flag(self):
        dm = DataManager(live_feed=LiveFeed())
        assert isinstance(dm.live_available, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
