from scripts.replay_80_baskets import _build_baskets


def test_basket_builder_is_deterministic_and_unique() -> None:
    tickers = ["A", "B", "C", "D", "E", "F"]
    first = _build_baskets(tickers, count=20, seed=42)
    second = _build_baskets(tickers, count=20, seed=42)
    assert first == second
    assert all(len(set(basket)) == 3 for basket in first)
