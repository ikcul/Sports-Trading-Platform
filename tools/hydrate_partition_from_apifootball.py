from __future__ import annotations

import asyncio
import csv
import json
import os
import sys
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND = PROJECT_ROOT / "backend"
SOURCE_PARTITION = PROJECT_ROOT / "data" / "world_cup_2026_jun11_jun28"
REAL_PARTITION = PROJECT_ROOT / "data" / "world_cup_2026_jun11_jun28_real"
STATUS_PATH = REAL_PARTITION / "hydration_status.json"
EXPECTED_MATCH_COUNT = 73
DATE_FROM = "2026-06-11"
DATE_TO = "2026-06-28"

sys.path.insert(0, str(BACKEND))

from app.ingestion.open_sports_data_client import APIFootballClient, OpenFixture  # noqa: E402


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_status(payload: dict[str, object]) -> None:
    REAL_PARTITION.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps(payload, indent=2, default=str))


def repo_path(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def iso(dt) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def normalize_team(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalnum())


def market_key(row: dict[str, str]) -> tuple[str, str]:
    teams = sorted([normalize_team(row["home_team"]), normalize_team(row["away_team"])])
    return (row["official_kickoff_utc"][:10], "|".join(teams))


def fixture_key(fixture: OpenFixture) -> tuple[str, str]:
    teams = sorted([normalize_team(fixture.home_team), normalize_team(fixture.away_team)])
    return (fixture.kickoff_at.date().isoformat(), "|".join(teams))


async def main() -> None:
    api_key = os.getenv("APIFOOTBALL_API_KEY", "").strip()
    competition = os.getenv("APIFOOTBALL_WORLD_CUP_LEAGUE_ID", "").strip()
    if not api_key or not competition:
        write_status(
            {
                "status": "blocked_missing_apifootball_credentials",
                "required_env": ["APIFOOTBALL_API_KEY", "APIFOOTBALL_WORLD_CUP_LEAGUE_ID"],
                "partition": repo_path(REAL_PARTITION),
                "reason": "Real partition hydration requires provider credentials and a verified competition id.",
            }
        )
        return

    client = APIFootballClient(api_key=api_key)
    provider_fixtures = await client.fixtures(competition=competition, season=2026, date_from=DATE_FROM, date_to=DATE_TO)
    if len(provider_fixtures) != EXPECTED_MATCH_COUNT:
        write_status(
            {
                "status": "blocked_unverified_fixture_coverage",
                "expected_match_count": EXPECTED_MATCH_COUNT,
                "provider_match_count": len(provider_fixtures),
                "provider_fixtures": [asdict(fixture) for fixture in provider_fixtures],
                "reason": "The replay slice must be complete before production partition files are written.",
            }
        )
        return

    market_rows = read_csv(SOURCE_PARTITION / "fixtures_required.csv")
    market_by_key = {market_key(row): row for row in market_rows}
    fixture_rows: list[dict[str, object]] = []
    feature_rows: list[dict[str, object]] = []
    evidence_rows: list[dict[str, object]] = []
    unmatched: list[dict[str, object]] = []

    for fixture in sorted(provider_fixtures, key=lambda item: item.kickoff_at):
        market_row = market_by_key.get(fixture_key(fixture))
        if market_row is None:
            unmatched.append(asdict(fixture))
            continue

        as_of = fixture.kickoff_at - timedelta(minutes=30)
        snapshot = await client.performance_snapshot(fixture, as_of)
        if snapshot.observed_at >= fixture.kickoff_at:
            raise ValueError(f"snapshot leak detected for {fixture.provider_match_id}")

        event_ticker = market_row["event_ticker"]
        fixture_rows.append(
            {
                **market_row,
                "match_id": event_ticker,
                "event_ticker": event_ticker,
                "official_kickoff_utc": iso(fixture.kickoff_at),
                "home_team": fixture.home_team,
                "away_team": fixture.away_team,
                "venue": fixture.venue or "",
                "source_url": fixture.source_url,
                "hydration_status": "api_football_point_in_time",
            }
        )
        feature_rows.append(
            {
                "event_ticker": event_ticker,
                "observed_at_utc": iso(snapshot.observed_at),
                "home_elo_rating": snapshot.home_stats.elo_rating,
                "away_elo_rating": snapshot.away_stats.elo_rating,
                "home_xg_for": snapshot.home_stats.xg_for,
                "home_xg_against": snapshot.home_stats.xg_against,
                "away_xg_for": snapshot.away_stats.xg_for,
                "away_xg_against": snapshot.away_stats.xg_against,
                "home_shots_for": snapshot.home_stats.shots_for,
                "home_shots_against": snapshot.home_stats.shots_against,
                "away_shots_for": snapshot.away_stats.shots_for,
                "away_shots_against": snapshot.away_stats.shots_against,
                "home_ppda": snapshot.home_stats.ppda,
                "away_ppda": snapshot.away_stats.ppda,
                "weather_summary": "not_available_from_api_football",
                "injury_summary": "not_available_from_api_football",
                "lineup_summary": "not_available_from_api_football",
                "source_url": snapshot.source_url,
                "hydration_status": "api_football_point_in_time",
            }
        )
        evidence_rows.append(
            {
                "event_ticker": event_ticker,
                "observed_at_utc": iso(snapshot.observed_at),
                "agent": "statistics",
                "source_name": "API-Football fixtures endpoint",
                "source_type": "analytics_provider",
                "confidence": "0.90",
                "fact": "Rolling team form generated from completed fixtures strictly before as_of.",
                "source_url": snapshot.source_url,
                "hydration_status": "api_football_point_in_time",
            }
        )

    if unmatched:
        write_status(
            {
                "status": "blocked_unmatched_provider_fixtures",
                "unmatched_count": len(unmatched),
                "unmatched": unmatched,
                "reason": "Every provider fixture must map to a discovered Kalshi market event before replay.",
            }
        )
        return

    write_csv(
        REAL_PARTITION / "fixtures_required.csv",
        fixture_rows,
        [
            "match_id",
            "event_ticker",
            "title",
            "official_kickoff_utc",
            "home_team",
            "away_team",
            "venue",
            "home_market_ticker",
            "away_market_ticker",
            "draw_market_ticker",
            "under_2_5_market_ticker",
            "over_2_5_market_ticker",
            "actual_outcome",
            "kalshi_close_time_utc",
            "source_url",
            "hydration_status",
        ],
    )
    write_csv(
        REAL_PARTITION / "feature_snapshots_required.csv",
        feature_rows,
        [
            "event_ticker",
            "observed_at_utc",
            "home_elo_rating",
            "away_elo_rating",
            "home_xg_for",
            "home_xg_against",
            "away_xg_for",
            "away_xg_against",
            "home_shots_for",
            "home_shots_against",
            "away_shots_for",
            "away_shots_against",
            "home_ppda",
            "away_ppda",
            "weather_summary",
            "injury_summary",
            "lineup_summary",
            "source_url",
            "hydration_status",
        ],
    )
    write_csv(
        REAL_PARTITION / "evidence_snapshots_required.csv",
        evidence_rows,
        ["event_ticker", "observed_at_utc", "agent", "source_name", "source_type", "confidence", "fact", "source_url", "hydration_status"],
    )
    write_status(
        {
            "status": "hydrated",
            "fixture_rows": len(fixture_rows),
            "feature_rows": len(feature_rows),
            "evidence_rows": len(evidence_rows),
            "partition": repo_path(REAL_PARTITION),
        }
    )


if __name__ == "__main__":
    asyncio.run(main())
