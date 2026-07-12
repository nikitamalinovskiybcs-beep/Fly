"""Real-time data via free WebSocket sources (graceful fallback)."""

import json
import logging
import threading

logger = logging.getLogger(__name__)

FINNHUB_WS = "wss://ws.finnhub.io"
BINANCE_WS = "wss://stream.binance.com:9443/ws"


class LiveFeed:
    """Aggregates real-time prices from free WebSocket sources.

    Providers (all free):
      1. Finnhub WebSocket  — real-time US stocks (needs FINNHUB_TOKEN)
      2. Binance WebSocket  — unlimited crypto (no token)

    Degrades gracefully: if `websocket-client` isn't installed the feed
    stays idle and callers should fall back to polled/historical data.

    Usage:
        feed = LiveFeed(finnhub_token="...")
        feed.subscribe(["AAPL", "MSFT", "BTCUSDT"])
        feed.on_price(lambda t, p, ts: print(t, p))
        feed.start()
    """

    def __init__(self, finnhub_token: str = ""):
        self.finnhub_token = finnhub_token
        self.callbacks: list = []
        self.latest_prices: dict[str, float] = {}
        self.subscriptions: list[str] = []
        self.running = False
        self._threads: list[threading.Thread] = []
        self._ws_available = self._check_ws()

    @staticmethod
    def _check_ws() -> bool:
        try:
            import websocket  # noqa: F401

            return True
        except ImportError:
            logger.info("websocket-client not installed — LiveFeed disabled (use polled data)")
            return False

    @property
    def available(self) -> bool:
        return self._ws_available

    def subscribe(self, tickers: list[str]) -> None:
        for t in tickers:
            if t not in self.subscriptions:
                self.subscriptions.append(t)

    def on_price(self, callback) -> None:
        """Register callback(ticker, price, timestamp)."""
        self.callbacks.append(callback)

    def _emit(self, ticker: str, price: float, timestamp) -> None:
        self.latest_prices[ticker] = price
        for cb in self.callbacks:
            try:
                cb(ticker, price, timestamp)
            except Exception as exc:  # noqa: BLE001
                logger.warning("LiveFeed callback error: %s", exc)

    @staticmethod
    def _is_crypto(ticker: str) -> bool:
        return ticker.upper().endswith(("USDT", "USD", "BTC", "ETH")) and len(ticker) > 5

    def start(self) -> bool:
        """Start feed threads. Returns False if websocket unavailable."""
        if not self._ws_available:
            logger.info("LiveFeed.start(): websocket unavailable, no-op")
            return False
        self.running = True
        crypto = [t for t in self.subscriptions if self._is_crypto(t)]
        stocks = [t for t in self.subscriptions if not self._is_crypto(t)]
        if crypto:
            self._spawn(self._run_binance, crypto)
        if stocks and self.finnhub_token:
            self._spawn(self._run_finnhub, stocks)
        return True

    def stop(self) -> None:
        self.running = False

    def _spawn(self, target, tickers) -> None:
        th = threading.Thread(target=target, args=(tickers,), daemon=True)
        th.start()
        self._threads.append(th)

    def _run_binance(self, tickers: list[str]) -> None:
        import websocket

        streams = "/".join(f"{t.lower()}@trade" for t in tickers)
        url = f"{BINANCE_WS}/{streams}"

        def on_message(_ws, message):
            data = json.loads(message)
            if "s" in data and "p" in data:
                self._emit(data["s"], float(data["p"]), data.get("T"))

        ws = websocket.WebSocketApp(url, on_message=on_message)
        while self.running:
            ws.run_forever()

    def _run_finnhub(self, tickers: list[str]) -> None:
        import websocket

        url = f"{FINNHUB_WS}?token={self.finnhub_token}"

        def on_open(ws):
            for t in tickers:
                ws.send(json.dumps({"type": "subscribe", "symbol": t}))

        def on_message(_ws, message):
            data = json.loads(message)
            for tick in data.get("data", []):
                self._emit(tick["s"], float(tick["p"]), tick.get("t"))

        ws = websocket.WebSocketApp(url, on_open=on_open, on_message=on_message)
        while self.running:
            ws.run_forever()

    def get_latest(self, ticker: str) -> float | None:
        return self.latest_prices.get(ticker)
