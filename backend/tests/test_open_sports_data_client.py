from __future__ import annotations

from datetime import timedelta

import pytest

from app.ingestion.open_sports_data_client import APIFootballClient, APIFootballProviderError


def test_api_football_sample_payload_parses_fixture_and_stats_before_as_of() -> None:
    fixtures = APIFootballClient.parse_fixture_payload(
        {
            "response": [
                {
                    "fixture": {
                        "id": 1001,
                        "date": "2026-06-11T19:00:00Z",
                        "venue": {"name": "Guadalajara Stadium"},
                    },
                    "teams": {
                        "home": {"id": 17, "name": "Korea Republic"},
                        "away": {"id": 18, "name": "Czechia"},
                    },
                    "league": {"id": 1, "season": 2026},
                }
            ]
        }
    )
    fixture = fixtures[0]
    assert fixture.metadata["home_team_id"] == 17
    as_of = fixture.kickoff_at - timedelta(minutes=30)
    snapshot = APIFootballClient.parse_performance_snapshot_payload(
        {
            "observed_at": "2026-06-11T18:00:00Z",
            "source_url": "sample://api-football/team-statistics",
            "teams": {
                "home": {"elo_rating": 1810, "xg_for": 1.45, "xg_against": 1.05, "shots_for": 11, "shots_against": 9, "ppda": 9.2},
                "away": {"elo_rating": 1760, "xg_for": 1.22, "xg_against": 1.18, "shots_for": 10, "shots_against": 10, "ppda": 10.1},
            },
        },
        fixture,
        as_of,
    )
    assert snapshot.home_stats.team == "Korea Republic"
    assert snapshot.observed_at < as_of


def test_api_football_sample_payload_rejects_post_as_of_stats() -> None:
    fixture = APIFootballClient.parse_fixture_payload(
        {
            "response": [
                {
                    "fixture": {"id": 1001, "date": "2026-06-11T19:00:00Z", "venue": {"name": "Guadalajara Stadium"}},
                    "teams": {"home": {"name": "Korea Republic"}, "away": {"name": "Czechia"}},
                }
            ]
        }
    )[0]
    with pytest.raises(ValueError):
        APIFootballClient.parse_performance_snapshot_payload(
            {
                "observed_at": "2026-06-11T18:45:00Z",
                "teams": {
                    "home": {"elo_rating": 1810, "xg_for": 1.45, "xg_against": 1.05, "shots_for": 11, "shots_against": 9, "ppda": 9.2},
                    "away": {"elo_rating": 1760, "xg_for": 1.22, "xg_against": 1.18, "shots_for": 10, "shots_against": 10, "ppda": 10.1},
                },
            },
            fixture,
            fixture.kickoff_at - timedelta(minutes=30),
        )


def test_api_football_completed_fixture_filter_and_rolling_stats_are_point_in_time() -> None:
    as_of = APIFootballClient.parse_fixture_payload(
        {
            "response": [
                {
                    "fixture": {"id": 1001, "date": "2026-06-11T19:00:00Z", "venue": {"name": "Guadalajara Stadium"}},
                    "teams": {"home": {"id": 17, "name": "Korea Republic"}, "away": {"id": 18, "name": "Czechia"}},
                    "league": {"id": 1, "season": 2026},
                }
            ]
        }
    )[0].kickoff_at - timedelta(minutes=30)
    payload = {
        "response": [
            {
                "fixture": {"date": "2026-06-01T18:00:00Z", "status": {"short": "FT"}},
                "teams": {"home": {"id": 17, "name": "Korea Republic"}, "away": {"id": 99, "name": "Opponent"}},
                "goals": {"home": 2, "away": 0},
            },
            {
                "fixture": {"date": "2026-06-11T18:45:00Z", "status": {"short": "FT"}},
                "teams": {"home": {"id": 17, "name": "Korea Republic"}, "away": {"id": 98, "name": "Late Opponent"}},
                "goals": {"home": 0, "away": 3},
            },
        ]
    }
    rows = APIFootballClient.completed_fixtures_before(payload, team_id=17, as_of=as_of)
    stats = APIFootballClient._rolling_stats_from_completed_fixtures("Korea Republic", rows)
    assert len(rows) == 1
    assert stats.xg_for > stats.xg_against


@pytest.mark.asyncio
async def test_api_football_get_raises_provider_error(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"errors": {"plan": "Free plans do not have access to this season."}}

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def get(self, path, params):
            return FakeResponse()

    monkeypatch.setattr("app.ingestion.open_sports_data_client.httpx.AsyncClient", FakeClient)
    with pytest.raises(APIFootballProviderError) as exc:
        await APIFootballClient(api_key="test")._get("/fixtures", {"league": 1})
    assert "plan" in exc.value.errors
