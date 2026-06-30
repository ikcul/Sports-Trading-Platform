from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.agents.research import InjuryAgent, NewsAgent, ResearchCoordinator, TacticalAgent
from app.backtesting.engine import BacktestEngine
from app.backtesting.sample_data import sample_historical_snapshots
from app.backtesting.schemas import BacktestReport
from app.domain.schemas import EvidenceItem, Match, MarketSnapshot, Recommendation, TeamStats
from app.models.probability import BayesianUpdater, EloModel, EnsembleModel, MonteCarloSimulator, PoissonGoalModel
from app.services.explainability import ExplainabilityEngine
from app.services.recommendations import RecommendationEngine

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/matches")
async def matches() -> list[Match]:
    return [_sample_match()]


@router.get("/matches/{match_id}/research")
async def research(match_id: str) -> dict[str, object]:
    coordinator = ResearchCoordinator([NewsAgent(), InjuryAgent(), TacticalAgent()])
    output, evidence = await coordinator.dispatch(match_id)
    return {"coordinator": output, "evidence": evidence}


@router.get("/matches/{match_id}/models")
async def models(match_id: str) -> dict[str, object]:
    match, home, away = _sample_context(match_id)
    elo = EloModel().predict(match, home, away)
    poisson = PoissonGoalModel().predict(match, home, away)
    bayesian = BayesianUpdater().apply_availability_shift(poisson, home_goal_delta=0.03, away_goal_delta=-0.02)
    bayesian.model_name = "bayesian_context"
    ensemble = EnsembleModel().combine([elo, poisson, bayesian], match_id=match.id)
    simulation = MonteCarloSimulator(simulations=25_000).run(match.id, ensemble.expected_home_goals, ensemble.expected_away_goals)
    return {"match": match, "models": [elo, poisson, bayesian], "ensemble": ensemble, "simulation": simulation}


@router.get("/recommendations")
async def recommendations() -> list[Recommendation]:
    rec, _ = await _sample_recommendation()
    return [rec]


@router.get("/backtests/sample")
async def sample_backtest() -> BacktestReport:
    return BacktestEngine(simulations=5_000).run(sample_historical_snapshots())


@router.get("/recommendations/{market_id}/explain")
async def explain(market_id: str) -> dict[str, object]:
    rec, evidence = await _sample_recommendation()
    return ExplainabilityEngine().render(rec, evidence)


async def _sample_recommendation() -> tuple[Recommendation, list[EvidenceItem]]:
    match, home, away = _sample_context("fifa-2026-sample-001")
    coordinator = ResearchCoordinator([NewsAgent(), InjuryAgent(), TacticalAgent()])
    _, evidence = await coordinator.dispatch(match.id)
    elo = EloModel().predict(match, home, away)
    poisson = PoissonGoalModel().predict(match, home, away)
    bayesian = BayesianUpdater().apply_availability_shift(poisson, home_goal_delta=0.03, away_goal_delta=-0.02)
    bayesian.model_name = "bayesian_context"
    ensemble = EnsembleModel().combine([elo, poisson, bayesian], match_id=match.id)
    simulation = MonteCarloSimulator(simulations=25_000).run(match.id, ensemble.expected_home_goals, ensemble.expected_away_goals)
    market = MarketSnapshot(market_id="KXWCUP-2026-SAMPLE-HOME", match_id=match.id, outcome="home_win", bid=0.42, ask=0.45, last_price=0.44, volume=18850, liquidity=4200)
    return RecommendationEngine().evaluate(ensemble, market, evidence, simulation), evidence


def _sample_match(match_id: str = "fifa-2026-sample-001") -> Match:
    return Match(id=match_id, competition="FIFA World Cup 2026", kickoff_at=datetime(2026, 7, 1, 20, 0, tzinfo=timezone.utc), home_team="Sample Home", away_team="Sample Away", neutral_site=True)


def _sample_context(match_id: str) -> tuple[Match, TeamStats, TeamStats]:
    match = _sample_match(match_id)
    home = TeamStats(team=match.home_team, elo_rating=1815, xg_for=1.72, xg_against=0.95, shots_for=14.2, shots_against=8.9, ppda=8.8, goalkeeper_goals_prevented=0.12)
    away = TeamStats(team=match.away_team, elo_rating=1762, xg_for=1.35, xg_against=1.18, shots_for=11.7, shots_against=10.5, ppda=10.4, goalkeeper_goals_prevented=-0.03)
    return match, home, away
