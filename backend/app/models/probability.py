from __future__ import annotations

import math
from collections import Counter
from random import Random

from app.domain.schemas import EnsembleOutput, Match, ModelOutput, TeamStats

DIXON_COLES_RHO = -0.08
ELO_STAGE_UNCERTAINTY = {
    "group": 0.050,
    "round_of_32": 0.060,
    "round_of_16": 0.065,
    "quarterfinal": 0.070,
    "semifinal": 0.075,
    "final": 0.080,
}


def _poisson_pmf(lam: float, k: int) -> float:
    return math.exp(-lam) * (lam**k) / math.factorial(k)


def normalize_three(home: float, draw: float, away: float) -> tuple[float, float, float]:
    total = home + draw + away
    if total <= 0:
        raise ValueError("probabilities cannot sum to zero")
    return home / total, draw / total, away / total


class EloModel:
    name = "elo"

    def predict(self, match: Match, home: TeamStats, away: TeamStats, tournament_stage: str = "group") -> ModelOutput:
        home_advantage = 0 if match.neutral_site else 65
        rating_delta = (home.elo_rating + home_advantage) - away.elo_rating
        home_no_draw = 1 / (1 + 10 ** (-rating_delta / 400))
        draw = max(0.18, min(0.32, 0.27 - abs(rating_delta) / 2500))
        home_win = home_no_draw * (1 - draw)
        away_win = (1 - home_no_draw) * (1 - draw)
        home_win, draw, away_win = normalize_three(home_win, draw, away_win)
        stage_variance = ELO_STAGE_UNCERTAINTY.get(tournament_stage, ELO_STAGE_UNCERTAINTY["group"])
        return ModelOutput(
            model_name=self.name,
            match_id=match.id,
            home_win=home_win,
            draw=draw,
            away_win=away_win,
            expected_home_goals=max(0.2, 1.30 + rating_delta / 900),
            expected_away_goals=max(0.2, 1.30 - rating_delta / 900),
            confidence_interval=(max(0.0, home_win - 0.09), min(0.99, home_win + 0.09)),
            variance=stage_variance,
            calibration_error=0.055,
            metadata={"rating_delta": rating_delta, "tournament_stage": tournament_stage},
        )


class PoissonGoalModel:
    name = "poisson_goals"

    def predict(self, match: Match, home: TeamStats, away: TeamStats) -> ModelOutput:
        expected_home = max(0.15, (home.xg_for + away.xg_against) / 2)
        expected_away = max(0.15, (away.xg_for + home.xg_against) / 2)
        home_win = draw = away_win = 0.0
        exact_scores: dict[str, float] = {}
        for hg in range(8):
            for ag in range(8):
                p = _poisson_pmf(expected_home, hg) * _poisson_pmf(expected_away, ag) * self._dixon_coles_adjustment(hg, ag, expected_home, expected_away)
                exact_scores[f"{hg}-{ag}"] = p
                if hg > ag:
                    home_win += p
                elif hg == ag:
                    draw += p
                else:
                    away_win += p
        home_win, draw, away_win = normalize_three(home_win, draw, away_win)
        return ModelOutput(
            model_name=self.name,
            match_id=match.id,
            home_win=home_win,
            draw=draw,
            away_win=away_win,
            expected_home_goals=expected_home,
            expected_away_goals=expected_away,
            confidence_interval=(max(0.0, home_win - 0.08), min(0.99, home_win + 0.08)),
            variance=min(0.25, (expected_home + expected_away) / 12),
            calibration_error=0.045,
            metadata={"exact_scores": dict(sorted(exact_scores.items(), key=lambda x: x[1], reverse=True)[:10]), "dixon_coles_rho": DIXON_COLES_RHO},
        )

    @staticmethod
    def _dixon_coles_adjustment(home_goals: int, away_goals: int, expected_home: float, expected_away: float) -> float:
        if home_goals == 0 and away_goals == 0:
            return 1 - expected_home * expected_away * DIXON_COLES_RHO
        if home_goals == 0 and away_goals == 1:
            return 1 + expected_home * DIXON_COLES_RHO
        if home_goals == 1 and away_goals == 0:
            return 1 + expected_away * DIXON_COLES_RHO
        if home_goals == 1 and away_goals == 1:
            return 1 - DIXON_COLES_RHO
        return 1.0


class BayesianUpdater:
    def apply_availability_shift(self, output: ModelOutput, home_goal_delta: float = 0.0, away_goal_delta: float = 0.0) -> ModelOutput:
        match = Match(id=output.match_id, competition="Bayesian update", kickoff_at=output.generated_at, home_team="home", away_team="away")
        home = TeamStats(team="home", elo_rating=1500, xg_for=output.expected_home_goals + home_goal_delta, xg_against=output.expected_away_goals + away_goal_delta, shots_for=0, shots_against=0, ppda=0)
        away = TeamStats(team="away", elo_rating=1500, xg_for=output.expected_away_goals + away_goal_delta, xg_against=output.expected_home_goals + home_goal_delta, shots_for=0, shots_against=0, ppda=0)
        updated = PoissonGoalModel().predict(match, home, away)
        updated.model_name = f"{output.model_name}_bayesian_update"
        updated.metadata["prior_model"] = output.model_name
        updated.metadata["goal_deltas"] = {"home": home_goal_delta, "away": away_goal_delta}
        return updated


class EnsembleModel:
    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self.weights = weights or {"elo": 0.35, "poisson_goals": 0.45, "bayesian_context": 0.20}

    def combine(self, outputs: list[ModelOutput], match_id: str) -> EnsembleOutput:
        if not outputs:
            raise ValueError("at least one model output is required")
        active_weights = {o.model_name: self.weights.get(o.model_name, 1.0) for o in outputs}
        total_weight = sum(active_weights.values())
        normalized = {k: v / total_weight for k, v in active_weights.items()}

        def weighted(attr: str) -> float:
            return sum(getattr(o, attr) * normalized[o.model_name] for o in outputs)

        home, draw, away = normalize_three(weighted("home_win"), weighted("draw"), weighted("away_win"))
        home_values = [o.home_win for o in outputs]
        agreement = max(0.0, min(0.99, 1 - (max(home_values) - min(home_values))))
        return EnsembleOutput(
            model_name="weighted_ensemble",
            match_id=match_id,
            home_win=home,
            draw=draw,
            away_win=away,
            expected_home_goals=weighted("expected_home_goals"),
            expected_away_goals=weighted("expected_away_goals"),
            confidence_interval=(max(0.0, home - 0.07), min(0.99, home + 0.07)),
            variance=weighted("variance"),
            calibration_error=weighted("calibration_error"),
            component_weights=normalized,
            model_agreement=agreement,
        )


class MonteCarloSimulator:
    def __init__(self, simulations: int = 100_000, seed: int = 1729) -> None:
        self.simulations = simulations
        self.seed = seed

    def run(self, match_id: str, expected_home_goals: float, expected_away_goals: float, is_knockout: bool = False) -> dict[str, object]:
        rng = Random(self.seed)
        outcomes: Counter[str] = Counter()
        total_home = 0
        total_away = 0
        under_2_5 = 0
        for _ in range(self.simulations):
            home_goals = self._sample_poisson(rng, expected_home_goals)
            away_goals = self._sample_poisson(rng, expected_away_goals)
            total_home += home_goals
            total_away += away_goals
            total_under = home_goals + away_goals < 2.5
            outcome = "home_win" if home_goals > away_goals else "draw" if home_goals == away_goals else "away_win"
            total_bucket = "under_2_5" if total_under else "over_2_5"
            final_winner = outcome
            if is_knockout and outcome == "draw":
                extra_home = self._sample_poisson(rng, expected_home_goals * 0.25)
                extra_away = self._sample_poisson(rng, expected_away_goals * 0.25)
                if extra_home > extra_away:
                    final_winner = "home_win"
                elif extra_away > extra_home:
                    final_winner = "away_win"
                else:
                    final_winner = "home_win" if rng.random() >= 0.5 else "away_win"
            if total_under:
                under_2_5 += 1
            outcomes[outcome] += 1
            outcomes[f"final_{final_winner}"] += 1
            outcomes[f"{outcome}_{total_bucket}"] += 1
        return {
            "match_id": match_id,
            "simulations": self.simulations,
            "home_win": outcomes["home_win"] / self.simulations,
            "draw": outcomes["draw"] / self.simulations,
            "away_win": outcomes["away_win"] / self.simulations,
            "under_2_5": under_2_5 / self.simulations,
            "over_2_5": 1 - under_2_5 / self.simulations,
            "home_win_under_2_5": outcomes["home_win_under_2_5"] / self.simulations,
            "home_win_over_2_5": outcomes["home_win_over_2_5"] / self.simulations,
            "draw_under_2_5": outcomes["draw_under_2_5"] / self.simulations,
            "draw_over_2_5": outcomes["draw_over_2_5"] / self.simulations,
            "away_win_under_2_5": outcomes["away_win_under_2_5"] / self.simulations,
            "away_win_over_2_5": outcomes["away_win_over_2_5"] / self.simulations,
            "final_home_win": outcomes["final_home_win"] / self.simulations if is_knockout else outcomes["home_win"] / self.simulations,
            "final_away_win": outcomes["final_away_win"] / self.simulations if is_knockout else outcomes["away_win"] / self.simulations,
            "knockout_extra_time_penalties_enabled": is_knockout,
            "avg_home_goals": total_home / self.simulations,
            "avg_away_goals": total_away / self.simulations,
        }

    @staticmethod
    def _sample_poisson(rng: Random, lam: float) -> int:
        threshold = math.exp(-lam)
        k = 0
        product = 1.0
        while product > threshold:
            k += 1
            product *= rng.random()
        return k - 1
