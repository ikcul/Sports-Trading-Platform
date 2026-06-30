from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

StreamReader = Callable[[], Awaitable[dict[str, Any]]]


@dataclass
class MarketStreamCache:
    snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_updated_at: datetime | None = None

    def update(self, ticker: str, payload: dict[str, Any]) -> None:
        self.snapshots[ticker] = payload
        self.last_updated_at = datetime.now(timezone.utc)


class MarketStreamReconnector:
    """Reconnect/backoff scaffold for live market streams.

    The reader function should perform one websocket read and return a decoded
    market payload containing a ticker. This class owns retry cadence and cache
    updates without requiring live credentials during tests.
    """

    def __init__(self, reader: StreamReader, cache: MarketStreamCache | None = None, max_backoff_seconds: float = 30.0) -> None:
        self.reader = reader
        self.cache = cache or MarketStreamCache()
        self.max_backoff_seconds = max_backoff_seconds
        self.reconnects = 0
        self.last_error: str | None = None

    async def run_once(self) -> dict[str, Any]:
        payload = await self.reader()
        ticker = str(payload.get("ticker") or payload.get("market_id") or "")
        if ticker:
            self.cache.update(ticker, payload)
        return payload

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        backoff = 1.0
        while not stop_event.is_set():
            try:
                await self.run_once()
                backoff = 1.0
                self.last_error = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.reconnects += 1
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("market_stream_reconnect_scheduled", extra={"error": self.last_error, "backoff": backoff})
                await asyncio.sleep(backoff)
                backoff = min(self.max_backoff_seconds, backoff * 2)
