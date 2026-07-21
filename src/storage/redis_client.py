"""Redis cache client (Upstash) — in-memory key-value store.

Free tier: 256MB, 10K commands/day.
Used for: price cache, IV cache, signal queue, rate limiting.

Environment variables:
    REDIS_URL=redis://xxx.upstash.io:6379
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RedisCache:
    """Cache layer for fast access to frequently used data.

    Keys:
        price:{ticker}       — latest price (TTL: 60s)
        iv:{ticker}          — implied vol (TTL: 3600s)
        regime:{ticker}      — current regime (TTL: 86400s)
        signal_queue         — list of pending signals
        rate_limit:{api}     — API call counter (TTL: 60s)
    """

    def __init__(self, redis_url: str = "") -> None:
        self._client = None
        self._enabled = False

        if not redis_url:
            logger.info("Redis not configured, caching disabled")
            return

        try:
            import redis
            self._client = redis.from_url(redis_url, decode_responses=True)
            self._client.ping()
            self._enabled = True
            logger.info("Redis connected")
        except ImportError:
            logger.info("redis package not installed, caching disabled")
        except Exception as exc:
            logger.warning("Redis init failed: %s", exc)

    @property
    def enabled(self) -> bool:
        """Whether Redis is available."""
        return self._enabled

    def set_price(self, ticker: str, price: float, ttl: int = 60) -> bool:
        """Cache a ticker price.

        Args:
            ticker: Ticker symbol.
            price: Current price.
            ttl: Time-to-live in seconds (default 60s).

        Returns:
            True if cached.
        """
        if not self._enabled:
            return False
        try:
            self._client.setex(f"price:{ticker}", ttl, str(price))
            return True
        except Exception as exc:
            logger.warning("Redis set price failed: %s", exc)
            return False

    def get_price(self, ticker: str) -> Optional[float]:
        """Get cached price for a ticker.

        Args:
            ticker: Ticker symbol.

        Returns:
            Cached price or None if expired/missing.
        """
        if not self._enabled:
            return None
        try:
            val = self._client.get(f"price:{ticker}")
            return float(val) if val else None
        except Exception:
            return None

    def set_iv(self, ticker: str, iv: float, ttl: int = 3600) -> bool:
        """Cache implied volatility.

        Args:
            ticker: Ticker symbol.
            iv: Implied volatility value.
            ttl: Time-to-live in seconds (default 1 hour).

        Returns:
            True if cached.
        """
        if not self._enabled:
            return False
        try:
            self._client.setex(f"iv:{ticker}", ttl, str(iv))
            return True
        except Exception as exc:
            logger.warning("Redis set IV failed: %s", exc)
            return False

    def get_iv(self, ticker: str) -> Optional[float]:
        """Get cached implied volatility.

        Args:
            ticker: Ticker symbol.

        Returns:
            Cached IV or None.
        """
        if not self._enabled:
            return None
        try:
            val = self._client.get(f"iv:{ticker}")
            return float(val) if val else None
        except Exception:
            return None

    def set_regime(self, ticker: str, regime: str, confidence: float, ttl: int = 86400) -> bool:
        """Cache detected regime for a ticker.

        Args:
            ticker: Ticker symbol.
            regime: Regime name (bull/bear/sideways).
            confidence: Detection confidence.
            ttl: Time-to-live in seconds (default 24h).

        Returns:
            True if cached.
        """
        if not self._enabled:
            return False
        try:
            data = json.dumps({"regime": regime, "confidence": confidence})
            self._client.setex(f"regime:{ticker}", ttl, data)
            return True
        except Exception as exc:
            logger.warning("Redis set regime failed: %s", exc)
            return False

    def get_regime(self, ticker: str) -> Optional[dict]:
        """Get cached regime for a ticker.

        Args:
            ticker: Ticker symbol.

        Returns:
            Dict with regime and confidence, or None.
        """
        if not self._enabled:
            return None
        try:
            val = self._client.get(f"regime:{ticker}")
            return json.loads(val) if val else None
        except Exception:
            return None

    def push_signal(self, signal: dict) -> bool:
        """Push a signal to the queue.

        Args:
            signal: Signal dict.

        Returns:
            True if pushed.
        """
        if not self._enabled:
            return False
        try:
            self._client.rpush("signal_queue", json.dumps(signal))
            return True
        except Exception as exc:
            logger.warning("Redis push signal failed: %s", exc)
            return False

    def pop_signal(self) -> Optional[dict]:
        """Pop next signal from the queue.

        Returns:
            Signal dict or None if empty.
        """
        if not self._enabled:
            return None
        try:
            val = self._client.lpop("signal_queue")
            return json.loads(val) if val else None
        except Exception:
            return None

    def queue_length(self) -> int:
        """Get number of signals in queue."""
        if not self._enabled:
            return 0
        try:
            return self._client.llen("signal_queue") or 0
        except Exception:
            return 0

    def check_rate_limit(self, api: str, max_calls: int = 60, window: int = 60) -> bool:
        """Check and increment rate limit counter.

        Args:
            api: API name (e.g. "yfinance", "numerai").
            max_calls: Maximum calls per window.
            window: Window size in seconds.

        Returns:
            True if within limit, False if exceeded.
        """
        if not self._enabled:
            return True
        try:
            key = f"rate_limit:{api}"
            count = self._client.incr(key)
            if count == 1:
                self._client.expire(key, window)
            return count <= max_calls
        except Exception:
            return True

    def set_json(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set arbitrary JSON value.

        Args:
            key: Cache key.
            value: JSON-serializable value.
            ttl: Optional TTL in seconds.

        Returns:
            True if set.
        """
        if not self._enabled:
            return False
        try:
            data = json.dumps(value)
            if ttl:
                self._client.setex(key, ttl, data)
            else:
                self._client.set(key, data)
            return True
        except Exception as exc:
            logger.warning("Redis set_json failed: %s", exc)
            return False

    def get_json(self, key: str) -> Optional[Any]:
        """Get arbitrary JSON value.

        Args:
            key: Cache key.

        Returns:
            Deserialized value or None.
        """
        if not self._enabled:
            return None
        try:
            val = self._client.get(key)
            return json.loads(val) if val else None
        except Exception:
            return None

    def cache_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dict with key count, memory usage info.
        """
        if not self._enabled:
            return {"enabled": False}
        try:
            info = self._client.info("memory")
            return {
                "enabled": True,
                "used_memory_mb": info.get("used_memory", 0) / 1024 / 1024,
                "keys": self._client.dbsize(),
            }
        except Exception:
            return {"enabled": True, "error": "stats unavailable"}
