from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from app.backtesting.partition import FeatureSnapshot, FixtureSnapshot
from app.domain.schemas import TeamStats


REQUIRED_FIXTURE_COLUMNS = {
    "event_ticker",
    "official_kickoff_utc",
    "home_team",
    "away_team",
    "home_market_ticker",
    "away_market_ticker",
    "draw_market_ticker",
    "actual_outcome",
}

REQUIRED_FEATURE_COLUMNS = {
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
}


class PartitionLoadError(ValueError):
    pass


def parse_utc(value: str) -> datetime:
    if not value:
        raise PartitionLoadError("missing UTC datetime")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_fixtures(path: Path) -> dict[str, FixtureSnapshot]:
    rows = _read_rows(path, REQUIRED_FIXTURE_COLUMNS)
    fixtures: dict[str, FixtureSnapshot] = {}
    for row in rows:
        if any(not row[column] for column in REQUIRED_FIXTURE_COLUMNS):
            raise PartitionLoadError(f"incomplete fixture row for {row.get('event_ticker')}")
        fixtures[row["event_ticker"]] = FixtureSnapshot(
            event_ticker=row["event_ticker"],
            title=row.get("title", ""),
            kickoff_at=parse_utc(row["official_kickoff_utc"]),
            home_team=row["home_team"],
            away_team=row["away_team"],
            home_market_ticker=row["home_market_ticker"],
            away_market_ticker=row["away_market_ticker"],
            draw_market_ticker=row["draw_market_ticker"],
            actual_outcome=row["actual_outcome"],
            under_2_5_market_ticker=row.get("under_2_5_market_ticker") or None,
            over_2_5_market_ticker=row.get("over_2_5_market_ticker") or None,
        )
    return fixtures


def load_features(path: Path, fixtures: dict[str, FixtureSnapshot]) -> dict[str, FeatureSnapshot]:
    rows = _read_rows(path, REQUIRED_FEATURE_COLUMNS)
    features: dict[str, FeatureSnapshot] = {}
    for row in rows:
        event_ticker = row["event_ticker"]
        if any(not row[column] for column in REQUIRED_FEATURE_COLUMNS):
            raise PartitionLoadError(f"incomplete feature row for {event_ticker}")
        fixture = fixtures.get(event_ticker)
        if fixture is None:
            raise PartitionLoadError(f"feature row has no matching fixture: {event_ticker}")
        features[event_ticker] = FeatureSnapshot(
            event_ticker=event_ticker,
            observed_at=parse_utc(row["observed_at_utc"]),
            home_stats=TeamStats(
                team=fixture.home_team,
                elo_rating=float(row["home_elo_rating"]),
                xg_for=float(row["home_xg_for"]),
                xg_against=float(row["home_xg_against"]),
                shots_for=float(row["home_shots_for"]),
                shots_against=float(row["home_shots_against"]),
                ppda=float(row["home_ppda"]),
            ),
            away_stats=TeamStats(
                team=fixture.away_team,
                elo_rating=float(row["away_elo_rating"]),
                xg_for=float(row["away_xg_for"]),
                xg_against=float(row["away_xg_against"]),
                shots_for=float(row["away_shots_for"]),
                shots_against=float(row["away_shots_against"]),
                ppda=float(row["away_ppda"]),
            ),
            facts=[
                fact
                for fact in [
                    row.get("weather_summary", ""),
                    row.get("injury_summary", ""),
                    row.get("lineup_summary", ""),
                ]
                if fact
            ],
        )
    return features


def _read_rows(path: Path, required_columns: set[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = required_columns - set(reader.fieldnames or [])
        if missing:
            raise PartitionLoadError(f"{path} missing columns: {sorted(missing)}")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]
