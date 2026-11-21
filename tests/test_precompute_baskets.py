from pathlib import Path

from scripts.precompute_baskets import parse_baskets, precompute_baskets


def test_parse_baskets_deduplicates_and_normalizes() -> None:
    assert parse_baskets("aapl, MSFT, aapl; nvda, amd") == [
        ["AAPL", "MSFT"],
        ["NVDA", "AMD"],
    ]


def test_precompute_baskets_writes_independent_snapshots(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import scripts.precompute_baskets as batch

    monkeypatch.setattr(
        batch,
        "run_full_analysis",
        lambda tickers: {"generated_at": "now", "tickers": tickers},
    )
    manifest = precompute_baskets(
        [["AAPL", "MSFT"], ["NVDA"]],
        tmp_path,
    )

    assert [record["status"] for record in manifest["records"]] == [
        "completed",
        "completed",
    ]
    assert len(list(tmp_path.glob("phoenix-*.pkl"))) == 2
    assert (tmp_path / "manifest.json").exists()
