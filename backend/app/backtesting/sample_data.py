from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.backtesting.schemas import HistoricalReplaySnapshot
from app.domain.schemas import AgentKind, EvidenceItem, MarketSnapshot, Match, SourceType, TeamStats


def sample_historical_snapshots() -> list[HistoricalReplaySnapshot]:
    kickoff = datetime(2026, 6, 15, 20, 0, tzinfo=timezone.utc)
    rows = [
        ("hist-001", kickoff, "Alpha", "Beta", 1810, 1750, 1.70, 1.16, 0.41, 0.44, 0.47, "home_win"),
        ("hist-002", kickoff + timedelta(days=1), "Gamma", "Delta", 1715, 1780, 1.18, 1.54, 0.34, 0.37, 0.40, "away_win"),
        ("hist-003", kickoff + timedelta(days=2), "Epsilon", "Zeta", 1760, 1768, 1.31, 1.28, 0.30, 0.33, 0.31, "draw"),
        ("hist-004", kickoff + timedelta(days=3), "Eta", "Theta", 1840, 1690, 1.95, 0.92, 0.46, 0.49, 0.54, "home_win"),
    ]
    snapshots: list[HistoricalReplaySnapshot] = []
    for match_id, starts_at, home, away, home_elo, away_elo, home_xg, away_xg, bid, ask, close, result in rows:
        as_of = starts_at - timedelta(hours=6)
        match = Match(id=match_id, competition="Historical sample", kickoff_at=starts_at, home_team=home, away_team=away)
        evidence = [
            EvidenceItem(
                match_id=match_id,
                agent=AgentKind.news,
                source_name="Archived official feed",
                source_type=SourceType.official_federation,
                observed_at=as_of - timedelta(hours=2),
                extracted_facts=["Fixture and venue confirmed before replay cutoff."],
                reasoning="Archived timestamp is before the replay cutoff.",
                confidence=0.96,
            ),
            EvidenceItem(
                match_id=match_id,
                agent=AgentKind.injury,
                source_name="Archived availability report",
                source_type=SourceType.major_media,
                observed_at=as_of - timedelta(hours=1),
                extracted_facts=["No new high-impact absence confirmed before replay cutoff."],
                reasoning="Only pre-cutoff availability evidence is eligible.",
                confidence=0.78,
            ),
        ]
        snapshots.append(
            HistoricalReplaySnapshot(
                match=match,
                as_of=as_of,
                home_stats=TeamStats(
                    team=home,
                    elo_rating=home_elo,
                    xg_for=home_xg,
                    xg_against=away_xg,
                    shots_for=12,
                    shots_against=10,
                    ppda=9.5,
                ),
                away_stats=TeamStats(
                    team=away,
                    elo_rating=away_elo,
                    xg_for=away_xg,
                    xg_against=home_xg,
                    shots_for=11,
                    shots_against=11,
                    ppda=10.2,
                ),
                market=MarketSnapshot(
                    market_id=f"KXHIST-{match_id}",
                    match_id=match_id,
                    outcome="home_win",
                    bid=bid,
                    ask=ask,
                    last_price=(bid + ask) / 2,
                    volume=20_000,
                    liquidity=5_000,
                    captured_at=as_of - timedelta(minutes=5),
                ),
                closing_market_probability=close,
                actual_outcome=result,
                evidence=evidence,
            )
        )
    return snapshots
