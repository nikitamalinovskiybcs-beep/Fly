import src.data_module as data_module


def test_ticker_cache_reuses_data_until_expiry(monkeypatch) -> None:
    calls = []

    def fake_fetch(tickers, period):
        calls.append((tickers, period))
        return {"AAPL": {"source": "test", "is_real": True}}

    data_module.clear_ticker_data_cache()
    monkeypatch.setattr(data_module, "_fetch_ticker_data_uncached", fake_fetch)

    first = data_module.fetch_ticker_data(["AAPL"], period="2y")
    second = data_module.fetch_ticker_data(["AAPL"], period="2y")

    assert first is second
    assert len(calls) == 1
