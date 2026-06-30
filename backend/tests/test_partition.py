from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.backtesting.engine import BacktestEngine, LookAheadBiasError
from app.backtesting.partition import FeatureSnapshot, FixtureSnapshot, KalshiCandle, PreMatchSnapshotMapper
from app.domain.schemas import TeamStats


def _stats(team: str) -> TeamStats:
    return TeamStats(
        team=team,
        elo_rating=1800,
        xg_for=1.5,
        xg_against=1.1,
        shots_for=12,
        shots_against=10,
        ppda=9,
    )


def test_mapper_builds_replay_snapshot_from_pre_cutoff_inputs() -> None:
    kickoff = datetime(2026, 6, 11, 21, 0, tzinfo=timezone.utc)
    fixture = FixtureSnapshot(
        event_ticker="KXWCGAME-26JUN11MEXRSA",
        title="Mexico vs South Africa Winner?",
        kickoff_at=kickoff,
        home_team="Mexico",
        away_team="South Africa",
        home_market_ticker="KXWCGAME-26JUN11MEXRSA-MEX",
        away_market_ticker="KXWCGAME-26JUN11MEXRSA-RSA",
        draw_market_ticker="KXWCGAME-26JUN11MEXRSA-TIE",
        actual_outcome="home_win",
    )
    feature = FeatureSnapshot(
        event_ticker=fixture.event_ticker,
        observed_at=kickoff - timedelta(hours=2),
        home_stats=_stats("Mexico"),
        away_stats=_stats("South Africa"),
        facts=["Point-in-time feature snapshot loaded before cutoff."],
    )
    candles = {
        fixture.home_market_ticker: [
            KalshiCandle(
                market_ticker=fixture.home_market_ticker,
                end_period=kickoff - timedelta(hours=1),
                yes_bid=0.69,
                yes_ask=0.70,
                close_price=0.70,
                volume=10000,
            )
        ]
    }
    snapshot = PreMatchSnapshotMapper(cutoff_minutes_before_kickoff=30).build(fixture, feature, candles)
    report = BacktestEngine(simulations=100).run([snapshot])
    assert report.replay_count == 1
    assert report.records[0].market_probability == 0.695


def test_mapper_rejects_feature_after_cutoff() -> None:
    kickoff = datetime(2026, 6, 11, 21, 0, tzinfo=timezone.utc)
    fixture = FixtureSnapshot(
        event_ticker="KXWCGAME-26JUN11MEXRSA",
        title="Mexico vs South Africa Winner?",
        kickoff_at=kickoff,
        home_team="Mexico",
        away_team="South Africa",
        home_market_ticker="KXWCGAME-26JUN11MEXRSA-MEX",
        away_market_ticker="KXWCGAME-26JUN11MEXRSA-RSA",
        draw_market_ticker="KXWCGAME-26JUN11MEXRSA-TIE",
        actual_outcome="home_win",
    )
    feature = FeatureSnapshot(
        event_ticker=fixture.event_ticker,
        observed_at=kickoff - timedelta(minutes=10),
        home_stats=_stats("Mexico"),
        away_stats=_stats("South Africa"),
        facts=["This feature leaks after the cutoff."],
    )
    candles = {
        fixture.home_market_ticker: [
            KalshiCandle(
                market_ticker=fixture.home_market_ticker,
                end_period=kickoff - timedelta(hours=1),
                yes_bid=0.69,
                yes_ask=0.70,
                close_price=0.70,
                volume=10000,
            )
        ]
    }
    with pytest.raises(LookAheadBiasError):
        PreMatchSnapshotMapper(cutoff_minutes_before_kickoff=30).build(fixture, feature, candles)
