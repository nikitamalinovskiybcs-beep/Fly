"""Fly data layer — unified live + historical market data access.

    from src.data import DataManager
    dm = DataManager()
    price = dm.get_price("AAPL")            # latest (live if available, else last close)
    hist = dm.get_history("AAPL", "6mo")    # historical OHLCV
"""

from .data_manager import DataManager
from .live_feed import LiveFeed

__all__ = ["DataManager", "LiveFeed"]
