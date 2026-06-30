from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.domain.schemas import MarketSnapshot


@dataclass(frozen=True)
class KalshiConfig:
    base_url: str = "https://api.elections.kalshi.com/trade-api/v2"
    timeout_seconds: float = 10.0


class KalshiClient:
    def __init__(self, config: KalshiConfig | None = None) -> None:
        self.config = config or KalshiConfig()

    async def get_market_snapshot(self, market_ticker: str, match_id: str, outcome: str) -> MarketSnapshot:
        async with httpx.AsyncClient(base_url=self.config.base_url, timeout=self.config.timeout_seconds) as client:
            response = await client.get(f"/markets/{market_ticker}")
            response.raise_for_status()
        data = response.json().get("market", response.json())
        bid = self._cents_to_probability(data.get("yes_bid", data.get("bid", 1)))
        ask = self._cents_to_probability(data.get("yes_ask", data.get("ask", 99)))
        last = self._cents_to_probability(data.get("last_price", data.get("last", round((bid + ask) * 50))))
        return MarketSnapshot(market_id=market_ticker, match_id=match_id, outcome=outcome, bid=bid, ask=ask, last_price=last, volume=int(data.get("volume", 0)), liquidity=float(data.get("liquidity", 0)))

    @staticmethod
    def _cents_to_probability(value: int | float) -> float:
        probability = float(value) / 100 if float(value) > 1 else float(value)
        return max(0.001, min(0.999, probability))
