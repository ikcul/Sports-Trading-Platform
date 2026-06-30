from __future__ import annotations

from datetime import datetime, timezone

from app.domain.schemas import Match, TeamStats
from app.models.probability import EloModel, EnsembleModel, MonteCarloSimulator, PoissonGoalModel


def test_model_probabilities_sum_to_one() -> None:
    match = Match(id="m1", competition="FIFA World Cup 2026", kickoff_at=datetime.now(timezone.utc), home_team="A", away_team="B")
    home = TeamStats(team="A", elo_rating=1800, xg_for=1.6, xg_against=0.9, shots_for=12, shots_against=8, ppda=9)
    away = TeamStats(team="B", elo_rating=1720, xg_for=1.2, xg_against=1.3, shots_for=10, shots_against=11, ppda=11)
    outputs = [EloModel().predict(match, home, away), PoissonGoalModel().predict(match, home, away)]
    ensemble = EnsembleModel().combine(outputs, match.id)
    assert round(ensemble.home_win + ensemble.draw + ensemble.away_win, 8) == 1.0
    assert 0 <= ensemble.model_agreement <= 0.99


def test_monte_carlo_is_reproducible() -> None:
    first = MonteCarloSimulator(simulations=1000, seed=7).run("m1", 1.4, 1.1)
    second = MonteCarloSimulator(simulations=1000, seed=7).run("m1", 1.4, 1.1)
    assert first == second
