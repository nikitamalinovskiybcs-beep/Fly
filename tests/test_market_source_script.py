from src.data_module import fetch_stooq_prices


def test_stooq_fetch_handles_unavailable_ticker(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr("src.data_module.urllib.request.urlopen", fail)
    assert fetch_stooq_prices(["AAPL"]) == {}
