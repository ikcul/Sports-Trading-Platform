from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.domain.schemas import TeamStats


@dataclass(frozen=True)
class HistoricalFixture:
    event_ticker: str
    kickoff_at: datetime
    home_team: str
    away_team: str
    venue: str
    source_url: str
    data_quality: str = "mock_seeded_not_official"


@dataclass(frozen=True)
class HistoricalFeatureSnapshot:
    event_ticker: str
    observed_at: datetime
    home_stats: TeamStats
    away_stats: TeamStats
    formation_home: str
    formation_away: str
    weather_summary: str
    injury_summary: str
    lineup_summary: str
    source_url: str
    data_quality: str = "mock_seeded_not_official"


class HistoricalSportsFeedClient:
    """Local mock sports feed for validating replay plumbing.

    This client intentionally does not claim production data provenance. It provides deterministic
    point-in-time snapshots so the strict partition loader and replay pipeline can be exercised
    while preserving clear labels that the feature layer is mocked.
    """

    SOURCE_URL = "local://mock-historical-sports-feed/world-cup-2026"
    VENUES = [
        "Mexico City Stadium",
        "Guadalajara Stadium",
        "Monterrey Stadium",
        "Los Angeles Stadium",
        "New York New Jersey Stadium",
        "Dallas Stadium",
        "Atlanta Stadium",
        "Vancouver Stadium",
        "Toronto Stadium",
        "Miami Stadium",
    ]
    FORMATIONS = ["3-4-3", "4-3-3", "4-2-3-1", "5-2-3", "3-5-2"]

    FIXTURE_OVERRIDES = {
        "KXWCGAME-26JUN11KORCZE": {
            "kickoff_at": datetime(2026, 6, 11, 19, 0, tzinfo=timezone.utc),
            "venue": "Guadalajara Stadium",
        },
        "KXWCGAME-26JUN11MEXRSA": {
            "kickoff_at": datetime(2026, 6, 11, 19, 0, tzinfo=timezone.utc),
            "venue": "Mexico City Stadium",
        },
    }

    def fixture_from_kalshi_event(
        self,
        event_ticker: str,
        title: str,
        kalshi_close_time: datetime,
        home_team: str,
        away_team: str,
    ) -> HistoricalFixture:
        override = self.FIXTURE_OVERRIDES.get(event_ticker, {})
        kickoff_at = override.get("kickoff_at") or self._infer_kickoff_from_market_close(kalshi_close_time)
        venue = override.get("venue") or self._venue_for(event_ticker)
        return HistoricalFixture(
            event_ticker=event_ticker,
            kickoff_at=kickoff_at,
            home_team=home_team,
            away_team=away_team,
            venue=venue,
            source_url=self.SOURCE_URL,
        )

    def feature_snapshot(self, fixture: HistoricalFixture) -> HistoricalFeatureSnapshot:
        observed_at = fixture.kickoff_at - timedelta(hours=1)
        home_seed = self._unit_interval(f"{fixture.event_ticker}:home")
        away_seed = self._unit_interval(f"{fixture.event_ticker}:away")
        home_elo = 1500 + round(home_seed * 520)
        away_elo = 1500 + round(away_seed * 520)
        home_xg_for = round(0.85 + home_seed * 1.25, 3)
        away_xg_for = round(0.85 + away_seed * 1.25, 3)
        home_xg_against = round(0.80 + (1 - home_seed) * 0.95, 3)
        away_xg_against = round(0.80 + (1 - away_seed) * 0.95, 3)
        home_stats = TeamStats(
            team=fixture.home_team,
            elo_rating=home_elo,
            xg_for=home_xg_for,
            xg_against=home_xg_against,
            shots_for=round(8.0 + home_seed * 8.0, 2),
            shots_against=round(7.0 + (1 - home_seed) * 7.5, 2),
            ppda=round(7.5 + (1 - home_seed) * 6.5, 2),
        )
        away_stats = TeamStats(
            team=fixture.away_team,
            elo_rating=away_elo,
            xg_for=away_xg_for,
            xg_against=away_xg_against,
            shots_for=round(8.0 + away_seed * 8.0, 2),
            shots_against=round(7.0 + (1 - away_seed) * 7.5, 2),
            ppda=round(7.5 + (1 - away_seed) * 6.5, 2),
        )
        return HistoricalFeatureSnapshot(
            event_ticker=fixture.event_ticker,
            observed_at=observed_at,
            home_stats=home_stats,
            away_stats=away_stats,
            formation_home=self._choice(f"{fixture.event_ticker}:formation-home", self.FORMATIONS),
            formation_away=self._choice(f"{fixture.event_ticker}:formation-away", self.FORMATIONS),
            weather_summary="Mock pre-match weather snapshot: playable conditions, no severe weather flag.",
            injury_summary="Mock squad availability snapshot: no confirmed high-impact absence in local feed.",
            lineup_summary="Mock lineup matrix seeded one hour before kickoff for replay validation only.",
            source_url=self.SOURCE_URL,
        )

    @staticmethod
    def _infer_kickoff_from_market_close(kalshi_close_time: datetime) -> datetime:
        inferred = kalshi_close_time - timedelta(hours=2)
        return inferred.replace(minute=0, second=0, microsecond=0)

    def _venue_for(self, event_ticker: str) -> str:
        return self._choice(f"{event_ticker}:venue", self.VENUES)

    @staticmethod
    def _unit_interval(key: str) -> float:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return int(digest[:12], 16) / float(16**12 - 1)

    def _choice(self, key: str, values: list[str]) -> str:
        idx = int(self._unit_interval(key) * len(values))
        return values[min(idx, len(values) - 1)]
