from __future__ import annotations

from datetime import datetime, timezone

from app.domain.schemas import EnsembleOutput, MarketSnapshot
from app.models.probability import MonteCarloSimulator
from app.services.recommendations import DerivativePropContext, KickoffsSevenPlusModel, RecommendationEngine


def test_monte_carlo_exposes_under_2_5_probability() -> None:
    result = MonteCarloSimulator(simulations=5000, seed=3).run("m1", 1.1, 0.9)
    assert 0.0 < float(result["under_2_5"]) < 1.0
    assert round(float(result["under_2_5"]) + float(result["over_2_5"]), 10) == 1.0


def test_recommendation_engine_prices_under_2_5_from_model_metadata() -> None:
    model = EnsembleOutput(
        model_name="weighted_ensemble",
        match_id="m1",
        home_win=0.4,
        draw=0.3,
        away_win=0.3,
        expected_home_goals=1.1,
        expected_away_goals=0.9,
        confidence_interval=(0.33, 0.47),
        variance=2.0,
        calibration_error=0.04,
        component_weights={"poisson_goals": 1.0},
        model_agreement=0.9,
        metadata={"under_2_5": 0.61},
    )
    market = MarketSnapshot(
        market_id="KXWCTOTAL-26JUN11MEXRSA-2",
        match_id="m1",
        outcome="under_2_5",
        bid=0.50,
        ask=0.53,
        last_price=0.52,
        volume=10000,
        liquidity=5000,
        captured_at=datetime.now(timezone.utc),
    )
    recommendation = RecommendationEngine().evaluate(model, market, [], {"under_2_5": 0.61})
    assert recommendation.estimated_probability == 0.61
    assert recommendation.edge > 0


def test_derivative_prop_stub_returns_bounded_probability() -> None:
    probability = KickoffsSevenPlusModel().estimate_probability(
        DerivativePropContext(
            match_id="m1",
            variables={"tempo": 0.8, "defensive_concession_rate": 0.6, "match_restart_rate": 0.7},
            metadata={},
        )
    )
    assert 0.01 <= probability <= 0.99
