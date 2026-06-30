from __future__ import annotations

from decimal import Decimal

import pytest

from app.ingestion.kalshi_order_client import OrderRequest, generate_order_idempotency_key
from app.ingestion.market_stream import MarketStreamCache, MarketStreamReconnector


def test_order_idempotency_key_is_deterministic() -> None:
    request = OrderRequest(
        market_id="KXWCGAME-26JUN11KORCZE",
        side="yes",
        quantity=Decimal("2.5"),
        price=Decimal("0.43"),
        portfolio_run_id="run-1",
    )
    assert generate_order_idempotency_key(request) == generate_order_idempotency_key(request)


@pytest.mark.asyncio
async def test_market_stream_run_once_updates_cache() -> None:
    async def reader() -> dict[str, object]:
        return {"ticker": "KXWCTOTAL-2.5", "yes_bid": 45}

    cache = MarketStreamCache()
    payload = await MarketStreamReconnector(reader, cache=cache).run_once()
    assert payload["ticker"] in cache.snapshots
    assert cache.last_updated_at is not None
