from __future__ import annotations

from datetime import datetime, timezone

from app.ingestion.sports_feed_client import HistoricalSportsFeedClient


def test_mock_feed_provides_user_seeded_korcze_fixture_and_pre_kickoff_features() -> None:
    client = HistoricalSportsFeedClient()
    fixture = client.fixture_from_kalshi_event(
        event_ticker="KXWCGAME-26JUN11KORCZE",
        title="Korea Republic vs Czechia Winner?",
        kalshi_close_time=datetime(2026, 6, 12, 4, 0, tzinfo=timezone.utc),
        home_team="Korea Republic",
        away_team="Czechia",
    )
    feature = client.feature_snapshot(fixture)
    assert fixture.kickoff_at == datetime(2026, 6, 11, 19, 0, tzinfo=timezone.utc)
    assert fixture.venue == "Guadalajara Stadium"
    assert feature.observed_at < fixture.kickoff_at
    assert feature.home_stats.team == "Korea Republic"
    assert feature.data_quality == "mock_seeded_not_official"
