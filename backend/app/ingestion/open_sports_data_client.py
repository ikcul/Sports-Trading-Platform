from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from app.domain.schemas import TeamStats


class APIFootballProviderError(RuntimeError):
    def __init__(self, errors: Any) -> None:
        self.errors = errors
        super().__init__(f"API-Football provider returned errors: {errors}")


@dataclass(frozen=True)
class OpenFixture:
    provider: str
    provider_match_id: str
    kickoff_at: datetime
    home_team: str
    away_team: str
    venue: str | None
    source_url: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OpenPerformanceSnapshot:
    provider: str
    provider_match_id: str
    observed_at: datetime
    home_stats: TeamStats
    away_stats: TeamStats
    source_url: str


class OpenSportsDataClient(ABC):
    @abstractmethod
    async def fixtures(self, competition: str, season: int, date_from: str, date_to: str) -> list[OpenFixture]:
        """Fetch fixtures with UTC kickoff timestamps."""

    @abstractmethod
    async def performance_snapshot(self, fixture: OpenFixture, as_of: datetime) -> OpenPerformanceSnapshot:
        """Fetch point-in-time performance metrics available before as_of."""


class APIFootballClient(OpenSportsDataClient):
    def __init__(self, api_key: str, base_url: str = "https://v3.football.api-sports.io") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def fixtures(self, competition: str, season: int, date_from: str, date_to: str) -> list[OpenFixture]:
        params = {"league": competition, "season": season, "from": date_from, "to": date_to, "timezone": "UTC"}
        payload = await self._get("/fixtures", params)
        return [
            OpenFixture(
                provider="api-football",
                provider_match_id=str(item["fixture"]["id"]),
                kickoff_at=datetime.fromisoformat(item["fixture"]["date"].replace("Z", "+00:00")),
                home_team=item["teams"]["home"]["name"],
                away_team=item["teams"]["away"]["name"],
                venue=(item["fixture"].get("venue") or {}).get("name"),
                source_url=f"{self.base_url}/fixtures",
                metadata=APIFootballClient._fixture_metadata(item),
            )
            for item in payload.get("response", [])
        ]

    async def performance_snapshot(self, fixture: OpenFixture, as_of: datetime) -> OpenPerformanceSnapshot:
        if as_of >= fixture.kickoff_at:
            raise ValueError("as_of must be strictly before fixture kickoff")
        missing = {"home_team_id", "away_team_id", "season"} - fixture.metadata.keys()
        if missing:
            raise ValueError(f"fixture metadata missing API-Football identifiers: {sorted(missing)}")
        home_rows = await self._completed_team_fixtures_before(
            int(fixture.metadata["home_team_id"]), int(fixture.metadata["season"]), as_of
        )
        away_rows = await self._completed_team_fixtures_before(
            int(fixture.metadata["away_team_id"]), int(fixture.metadata["season"]), as_of
        )
        return OpenPerformanceSnapshot(
            provider="api-football",
            provider_match_id=fixture.provider_match_id,
            observed_at=as_of,
            home_stats=self._rolling_stats_from_completed_fixtures(fixture.home_team, home_rows),
            away_stats=self._rolling_stats_from_completed_fixtures(fixture.away_team, away_rows),
            source_url=f"{self.base_url}/fixtures",
        )

    @staticmethod
    def parse_fixture_payload(payload: dict[str, Any]) -> list[OpenFixture]:
        return [
            OpenFixture(
                provider="api-football",
                provider_match_id=str(item["fixture"]["id"]),
                kickoff_at=datetime.fromisoformat(item["fixture"]["date"].replace("Z", "+00:00")),
                home_team=item["teams"]["home"]["name"],
                away_team=item["teams"]["away"]["name"],
                venue=(item["fixture"].get("venue") or {}).get("name"),
                source_url="sample://api-football/fixtures",
                metadata=APIFootballClient._fixture_metadata(item),
            )
            for item in payload.get("response", [])
        ]

    @staticmethod
    def parse_performance_snapshot_payload(payload: dict[str, Any], fixture: OpenFixture, as_of: datetime) -> OpenPerformanceSnapshot:
        observed_at = datetime.fromisoformat(payload["observed_at"].replace("Z", "+00:00"))
        if observed_at > as_of:
            raise ValueError("API-Football performance payload leaks after as_of")
        teams = payload["teams"]
        home = teams["home"]
        away = teams["away"]
        return OpenPerformanceSnapshot(
            provider="api-football",
            provider_match_id=fixture.provider_match_id,
            observed_at=observed_at,
            home_stats=TeamStats(
                team=fixture.home_team,
                elo_rating=float(home["elo_rating"]),
                xg_for=float(home["xg_for"]),
                xg_against=float(home["xg_against"]),
                shots_for=float(home["shots_for"]),
                shots_against=float(home["shots_against"]),
                ppda=float(home["ppda"]),
            ),
            away_stats=TeamStats(
                team=fixture.away_team,
                elo_rating=float(away["elo_rating"]),
                xg_for=float(away["xg_for"]),
                xg_against=float(away["xg_against"]),
                shots_for=float(away["shots_for"]),
                shots_against=float(away["shots_against"]),
                ppda=float(away["ppda"]),
            ),
            source_url=payload.get("source_url", "sample://api-football/team-statistics"),
        )

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, headers={"x-apisports-key": self.api_key}, timeout=30) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            payload = response.json()
        if payload.get("errors"):
            raise APIFootballProviderError(payload["errors"])
        return payload

    async def _completed_team_fixtures_before(self, team_id: int, season: int, as_of: datetime) -> list[dict[str, Any]]:
        payload = await self._get(
            "/fixtures",
            {"team": team_id, "season": season, "to": as_of.date().isoformat(), "timezone": "UTC"},
        )
        return self.completed_fixtures_before(payload, team_id, as_of)

    @staticmethod
    def _fixture_metadata(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "fixture_id": item["fixture"]["id"],
            "home_team_id": item["teams"]["home"].get("id"),
            "away_team_id": item["teams"]["away"].get("id"),
            "league_id": (item.get("league") or {}).get("id"),
            "season": (item.get("league") or {}).get("season"),
        }

    @staticmethod
    def completed_fixtures_before(payload: dict[str, Any], team_id: int, as_of: datetime) -> list[dict[str, Any]]:
        completed_statuses = {"FT", "AET", "PEN"}
        rows: list[dict[str, Any]] = []
        for item in payload.get("response", []):
            played_at = datetime.fromisoformat(item["fixture"]["date"].replace("Z", "+00:00"))
            if played_at >= as_of:
                continue
            if (item["fixture"].get("status") or {}).get("short") not in completed_statuses:
                continue
            if item["teams"]["home"].get("id") != team_id and item["teams"]["away"].get("id") != team_id:
                continue
            rows.append(item)
        return sorted(rows, key=lambda row: row["fixture"]["date"])[-10:]

    @staticmethod
    def _rolling_stats_from_completed_fixtures(team_name: str, rows: list[dict[str, Any]]) -> TeamStats:
        if not rows:
            return TeamStats(
                team=team_name,
                elo_rating=1500.0,
                xg_for=1.0,
                xg_against=1.0,
                shots_for=10.0,
                shots_against=10.0,
                ppda=11.0,
            )

        goals_for = 0
        goals_against = 0
        wins = 0
        losses = 0
        clean_sheets = 0
        team_id: int | None = None
        for row in rows:
            home_id = row["teams"]["home"].get("id")
            away_id = row["teams"]["away"].get("id")
            if team_id is None:
                team_id = home_id if row["teams"]["home"].get("name") == team_name else away_id
            is_home = home_id == team_id
            team_goals = int(row["goals"]["home"] if is_home else row["goals"]["away"])
            opponent_goals = int(row["goals"]["away"] if is_home else row["goals"]["home"])
            goals_for += team_goals
            goals_against += opponent_goals
            clean_sheets += int(opponent_goals == 0)
            wins += int(team_goals > opponent_goals)
            losses += int(team_goals < opponent_goals)

        count = len(rows)
        gf_avg = goals_for / count
        ga_avg = goals_against / count
        win_rate = wins / count
        loss_rate = losses / count
        clean_sheet_rate = clean_sheets / count
        elo_rating = 1500.0 + (gf_avg - ga_avg) * 70.0 + win_rate * 90.0 - loss_rate * 45.0
        return TeamStats(
            team=team_name,
            elo_rating=round(max(1200.0, min(2100.0, elo_rating)), 2),
            xg_for=round(max(0.25, gf_avg * 0.92 + 0.1), 3),
            xg_against=round(max(0.25, ga_avg * 0.92 + 0.1), 3),
            shots_for=round(max(4.0, 7.0 + gf_avg * 3.0 + win_rate), 3),
            shots_against=round(max(4.0, 7.0 + ga_avg * 3.0 + (1.0 - clean_sheet_rate)), 3),
            ppda=round(max(7.0, min(18.0, 11.0 - win_rate * 2.0 + loss_rate * 2.0)), 3),
        )


class UnderstatFBrefSnapshotClient(OpenSportsDataClient):
    async def fixtures(self, competition: str, season: int, date_from: str, date_to: str) -> list[OpenFixture]:
        raise NotImplementedError("FBref/Understat ingestion should run through cached parsers with source snapshots.")

    async def performance_snapshot(self, fixture: OpenFixture, as_of: datetime) -> OpenPerformanceSnapshot:
        raise NotImplementedError("Implement parser-specific xG/form extraction with archived page timestamps.")


class EntitySportClient(OpenSportsDataClient):
    def __init__(self, token: str, base_url: str = "https://rest.entitysport.com/v2") -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")

    async def fixtures(self, competition: str, season: int, date_from: str, date_to: str) -> list[OpenFixture]:
        raise NotImplementedError("Map EntitySport competition IDs and response schema before production use.")

    async def performance_snapshot(self, fixture: OpenFixture, as_of: datetime) -> OpenPerformanceSnapshot:
        raise NotImplementedError("Map EntitySport team/player stats to TeamStats before production use.")
