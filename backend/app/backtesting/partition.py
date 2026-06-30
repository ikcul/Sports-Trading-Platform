from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.backtesting.engine import LookAheadBiasError
from app.backtesting.schemas import HistoricalReplaySnapshot
from app.domain.schemas import AgentKind, EvidenceItem, MarketSnapshot, Match, SourceType, TeamStats


class SnapshotPartitionError(ValueError):
    pass


@dataclass(frozen=True)
class FixtureSnapshot:
    event_ticker: str
    title: str
    kickoff_at: datetime
    home_team: str
    away_team: str
    home_market_ticker: str
    away_market_ticker: str
    draw_market_ticker: str
    actual_outcome: str
    under_2_5_market_ticker: str | None = None
    over_2_5_market_ticker: str | None = None


@dataclass(frozen=True)
class FeatureSnapshot:
    event_ticker: str
    observed_at: datetime
    home_stats: TeamStats
    away_stats: TeamStats
    facts: list[str]
    source_name: str = "historical feature snapshot"
    source_type: SourceType = SourceType.analytics_provider
    confidence: float = 0.90


@dataclass(frozen=True)
class KalshiCandle:
    market_ticker: str
    end_period: datetime
    yes_bid: float
    yes_ask: float
    close_price: float
    volume: float


class PreMatchSnapshotMapper:
    def __init__(self, cutoff_minutes_before_kickoff: int = 30) -> None:
        if cutoff_minutes_before_kickoff <= 0:
            raise ValueError("cutoff must be strictly before kickoff")
        self.cutoff = timedelta(minutes=cutoff_minutes_before_kickoff)

    def build(
        self,
        fixture: FixtureSnapshot,
        feature: FeatureSnapshot,
        candles_by_market: dict[str, list[KalshiCandle]],
        market_outcome: str = "home_win",
    ) -> HistoricalReplaySnapshot:
        as_of = fixture.kickoff_at - self.cutoff
        if feature.observed_at > as_of:
            raise LookAheadBiasError("feature snapshot was observed after replay cutoff")

        market_ticker = self._market_ticker_for_outcome(fixture, market_outcome)
        market_candle = self._latest_candle_before(candles_by_market.get(market_ticker, []), as_of)
        closing_candle = self._latest_candle_before(candles_by_market.get(market_ticker, []), fixture.kickoff_at)
        evidence = [
            EvidenceItem(
                match_id=fixture.event_ticker,
                agent=AgentKind.news,
                source_name=feature.source_name,
                source_type=feature.source_type,
                observed_at=feature.observed_at,
                extracted_facts=feature.facts,
                reasoning="Historical feature snapshot was timestamp-gated before the replay cutoff.",
                confidence=feature.confidence,
            )
        ]
        snapshot = HistoricalReplaySnapshot(
            match=Match(
                id=fixture.event_ticker,
                competition="FIFA World Cup 2026",
                kickoff_at=fixture.kickoff_at,
                home_team=fixture.home_team,
                away_team=fixture.away_team,
            ),
            as_of=as_of,
            home_stats=feature.home_stats,
            away_stats=feature.away_stats,
            market=MarketSnapshot(
                market_id=market_ticker,
                match_id=fixture.event_ticker,
                outcome=market_outcome,
                bid=market_candle.yes_bid,
                ask=market_candle.yes_ask,
                last_price=market_candle.close_price,
                volume=int(market_candle.volume),
                liquidity=market_candle.volume,
                captured_at=market_candle.end_period,
            ),
            closing_market_probability=closing_candle.close_price,
            actual_outcome=fixture.actual_outcome,
            evidence=evidence,
        )
        self._assert_snapshot_complete(snapshot)
        return snapshot

    @staticmethod
    def _market_ticker_for_outcome(fixture: FixtureSnapshot, outcome: str) -> str:
        lookup = {
            "home_win": fixture.home_market_ticker,
            "away_win": fixture.away_market_ticker,
            "draw": fixture.draw_market_ticker,
            "under_2_5": fixture.under_2_5_market_ticker,
            "over_2_5": fixture.over_2_5_market_ticker,
        }
        ticker = lookup.get(outcome)
        if not ticker:
            raise SnapshotPartitionError(f"no market ticker configured for outcome {outcome}")
        return ticker

    @staticmethod
    def _latest_candle_before(candles: list[KalshiCandle], cutoff: datetime) -> KalshiCandle:
        eligible = [candle for candle in candles if candle.end_period <= cutoff]
        if not eligible:
            raise SnapshotPartitionError("no Kalshi candle exists at or before cutoff")
        return max(eligible, key=lambda c: c.end_period)

    @staticmethod
    def _assert_snapshot_complete(snapshot: HistoricalReplaySnapshot) -> None:
        if snapshot.as_of >= snapshot.match.kickoff_at:
            raise LookAheadBiasError("as_of must be strictly before kickoff")
        if snapshot.market.captured_at > snapshot.as_of:
            raise LookAheadBiasError("market candle leaks after as_of")
        for evidence in snapshot.evidence:
            if evidence.observed_at > snapshot.as_of:
                raise LookAheadBiasError("evidence leaks after as_of")


def kalshi_candle_from_api(market_ticker: str, raw: dict[str, Any]) -> KalshiCandle:
    return KalshiCandle(
        market_ticker=market_ticker,
        end_period=datetime.fromtimestamp(int(raw["end_period_ts"]), tz=timezone.utc),
        yes_bid=float(raw["yes_bid"]["close_dollars"]),
        yes_ask=float(raw["yes_ask"]["close_dollars"]),
        close_price=float(raw["price"]["close_dollars"]),
        volume=float(raw.get("volume_fp") or 0.0),
    )
