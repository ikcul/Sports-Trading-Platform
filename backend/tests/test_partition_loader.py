from __future__ import annotations

from pathlib import Path

import pytest

from app.backtesting.partition_loader import PartitionLoadError, load_features, load_fixtures


def test_partition_loader_rejects_incomplete_required_rows(tmp_path: Path) -> None:
    fixtures = tmp_path / "fixtures.csv"
    fixtures.write_text(
        "event_ticker,official_kickoff_utc,home_team,away_team,home_market_ticker,away_market_ticker,draw_market_ticker,actual_outcome\n"
        "KXWCGAME-26JUN11MEXRSA,,Mexico,South Africa,KXWCGAME-26JUN11MEXRSA-MEX,KXWCGAME-26JUN11MEXRSA-RSA,KXWCGAME-26JUN11MEXRSA-TIE,home_win\n",
        encoding="utf-8",
    )
    with pytest.raises(PartitionLoadError):
        load_fixtures(fixtures)


def test_partition_loader_initializes_team_stats_from_complete_rows(tmp_path: Path) -> None:
    fixtures_path = tmp_path / "fixtures.csv"
    fixtures_path.write_text(
        "event_ticker,title,official_kickoff_utc,home_team,away_team,home_market_ticker,away_market_ticker,draw_market_ticker,actual_outcome\n"
        "KXWCGAME-26JUN11MEXRSA,Mexico vs South Africa Winner?,2026-06-11T21:00:00Z,Mexico,South Africa,KXWCGAME-26JUN11MEXRSA-MEX,KXWCGAME-26JUN11MEXRSA-RSA,KXWCGAME-26JUN11MEXRSA-TIE,home_win\n",
        encoding="utf-8",
    )
    features_path = tmp_path / "features.csv"
    features_path.write_text(
        "event_ticker,observed_at_utc,home_elo_rating,away_elo_rating,home_xg_for,home_xg_against,away_xg_for,away_xg_against,home_shots_for,home_shots_against,away_shots_for,away_shots_against,home_ppda,away_ppda,weather_summary,injury_summary,lineup_summary\n"
        "KXWCGAME-26JUN11MEXRSA,2026-06-11T19:00:00Z,1810,1700,1.7,1.1,1.0,1.4,12,9,10,11,9.1,10.2,clear,no major injuries,lineups unavailable\n",
        encoding="utf-8",
    )
    fixtures = load_fixtures(fixtures_path)
    features = load_features(features_path, fixtures)
    assert features["KXWCGAME-26JUN11MEXRSA"].home_stats.team == "Mexico"
    assert features["KXWCGAME-26JUN11MEXRSA"].home_stats.xg_for == 1.7
