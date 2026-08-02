from pathlib import Path
import pickle

from src.snapshot_cache import load_snapshot, save_snapshot


def test_snapshot_cache_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.pkl"
    payload = {"product": {"best": {"basket": ["AAPL", "MSFT", "JPM"]}}}

    save_snapshot(["AAPL", "MSFT", "JPM"], payload, path=path)
    snapshot = load_snapshot(["AAPL", "MSFT", "JPM"], path=path)

    assert snapshot is not None
    assert snapshot.fresh is True
    assert snapshot.payload == payload


def test_snapshot_cache_is_keyed_by_basket(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.pkl"
    save_snapshot(["AAPL"], {"value": 1}, path=path)

    assert load_snapshot(["MSFT"], path=path) is None


def test_snapshot_cache_rejects_old_schema(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.pkl"
    with path.open("wb") as handle:
        pickle.dump(
            {
                "version": 1,
                "tickers": ["AAPL"],
                "created_at": 0,
                "payload": {"value": 1},
            },
            handle,
        )

    assert load_snapshot(["AAPL"], path=path) is None
