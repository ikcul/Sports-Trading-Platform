from __future__ import annotations

from datetime import datetime, timezone

from app.backtesting.schemas import ReplayRecord
from app.domain.schemas import Recommendation, RecommendationStatus
from app.services.recommendations import MAX_MATCH_EXPOSURE, PortfolioRiskCovarianceFilter


def _recommendation(outcome: str, fractional_kelly: float) -> Recommendation:
    return Recommendation(
        market_id=f"market-{outcome}",
        match_id="match-1",
        outcome=outcome,
        status=RecommendationStatus.recommended,
        estimated_probability=0.6,
        market_implied_probability=0.5,
        edge=0.1,
        expected_value=0.1,
        kelly_fraction=fractional_kelly * 4,
        fractional_kelly=fractional_kelly,
        confidence_score=0.8,
        risk_score=0.2,
        evidence_ids=[],
        supporting_evidence=[],
        key_statistics={"market_ask": 0.5},
        simulation_summary={"home_win_under_2_5": 0.42},
        risks=[],
        counterarguments=[],
        invalidation_triggers=[],
    )


def test_portfolio_filter_caps_same_match_fractional_kelly_and_recomputes_pnl() -> None:
    records = [
        ReplayRecord(
            match_id="match-1",
            as_of=datetime.now(timezone.utc),
            actual_outcome="home_win",
            estimated_probability=0.6,
            market_probability=0.5,
            closing_probability=0.52,
            brier=0.16,
            log_loss=0.5,
            closing_line_value=0.08,
            profit_loss=0.08,
            recommendation=_recommendation("home_win", 0.08),
        ),
        ReplayRecord(
            match_id="match-1",
            as_of=datetime.now(timezone.utc),
            actual_outcome="under_2_5",
            estimated_probability=0.6,
            market_probability=0.5,
            closing_probability=0.52,
            brier=0.16,
            log_loss=0.5,
            closing_line_value=0.08,
            profit_loss=0.07,
            recommendation=_recommendation("under_2_5", 0.07),
        ),
    ]
    filtered = PortfolioRiskCovarianceFilter().apply_to_replay_records(records)
    exposure = sum(record.recommendation.fractional_kelly for record in filtered)
    assert exposure <= MAX_MATCH_EXPOSURE
    assert abs(filtered[0].recommendation.key_statistics["pre_filter_match_exposure"] - 0.15) < 1e-12
    assert filtered[0].profit_loss == filtered[0].recommendation.fractional_kelly
