import pandas as pd

from scripts.ingest_ohlcv import _normalise_history


def test_normalise_history_accepts_yfinance_columns() -> None:
    source = pd.DataFrame(
        {
            "Open": [10.0],
            "High": [11.0],
            "Low": [9.0],
            "Close": [10.5],
            "Volume": [1000],
        },
        index=pd.DatetimeIndex(["2026-01-02"], name="Date"),
    )

    result = _normalise_history(source)

    assert list(result["date"]) == [pd.Timestamp("2026-01-02").date()]
    assert result.loc[0, "adj_close"] == 10.5
    assert result.loc[0, "volume"] == 1000


def test_normalise_history_rejects_incomplete_data() -> None:
    result = _normalise_history(pd.DataFrame({"Close": [10.0]}))

    assert result.empty
