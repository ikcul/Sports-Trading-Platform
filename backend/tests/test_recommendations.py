from __future__ import annotations

from datetime import datetime, timezone

from app.domain.schemas import AgentKind, EnsembleOutput, EvidenceItem, MarketSnapshot, SourceType
from app.services.recommendations import RecommendationEngine, RecommendationStatus


def _evidence() -> list[EvidenceItem]:
    return [
        EvidenceItem(match_id="m1", agent=AgentKind.news, source_name="Official feed", source_type=SourceType.official_federation, observed_at=datetime.now(timezone.utc), extracted_facts=["Confirmed fixture."], reasoning="Official schedule evidence.", confidence=0.98),
        EvidenceItem(match_id="m1", agent=AgentKind.injury, source_name="Tier 1 reporter", source_type=SourceType.tier_one_journalist, observed_at=datetime.now(timezone.utc), extracted_facts=["No late injury concern reported."], reasoning="Availability update from a historically reliable reporter.", confidence=0.91),
    ]


def test_recommendation_rejects_low_edge() -> None:
    model = EnsembleOutput(model_name="weighted_ensemble", match_id="m1", home_win=0.46, draw=0.28, away_win=0.26, expected_home_goals=1.4, expected_away_goals=1.1, confidence_interval=(0.39, 0.53), variance=0.20, calibration_error=0.04, component_weights={"elo": 0.5, "poisson_goals": 0.5}, model_agreement=0.91)
    market = MarketSnapshot(market_id="mk1", match_id="m1", outcome="home_win", bid=0.44, ask=0.47, last_price=0.45, volume=10000, liquidity=5000)
    rec = RecommendationEngine().evaluate(model, market, _evidence(), {"simulations": 100000})
    assert rec.status == RecommendationStatus.rejected
    assert "edge_below_threshold" in rec.rejection_reasons


def test_recommendation_allows_high_quality_positive_ev() -> None:
    model = EnsembleOutput(model_name="weighted_ensemble", match_id="m1", home_win=0.55, draw=0.25, away_win=0.20, expected_home_goals=1.8, expected_away_goals=0.9, confidence_interval=(0.49, 0.61), variance=0.18, calibration_error=0.03, component_weights={"elo": 0.35, "poisson_goals": 0.45, "bayesian_context": 0.20}, model_agreement=0.88)
    market = MarketSnapshot(market_id="mk1", match_id="m1", outcome="home_win", bid=0.42, ask=0.45, last_price=0.44, volume=30000, liquidity=8000)
    rec = RecommendationEngine().evaluate(model, market, _evidence(), {"simulations": 100000})
    assert rec.status == RecommendationStatus.recommended
    assert rec.expected_value > 0
    assert rec.fractional_kelly <= rec.kelly_fraction


def test_recommendation_rejects_unsupported_outcome_without_throwing() -> None:
    model = EnsembleOutput(model_name="weighted_ensemble", match_id="m1", home_win=0.55, draw=0.25, away_win=0.20, expected_home_goals=1.8, expected_away_goals=0.9, confidence_interval=(0.49, 0.61), variance=0.18, calibration_error=0.03, component_weights={"elo": 1.0}, model_agreement=0.88)
    market = MarketSnapshot(market_id="mk1", match_id="m1", outcome="first_corner", bid=42, ask=45, last_price=44, volume=30000, liquidity=8000)
    rec = RecommendationEngine().evaluate(model, market, _evidence(), {"simulations": 100000})
    assert rec.status == RecommendationStatus.rejected
    assert rec.rejection_reasons == ["unsupported_outcome"]
    assert rec.kelly_fraction == 0.0


def test_market_snapshot_normalizes_cent_prices() -> None:
    market = MarketSnapshot(market_id="mk1", match_id="m1", outcome="home_win", bid=42, ask=45, last_price=44, volume=1, liquidity=1)
    assert market.bid == 0.42
    assert market.ask == 0.45
