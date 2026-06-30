from __future__ import annotations

from statistics import mean
from uuid import uuid4

from app.backtesting.metrics import (
    baseline_score,
    binary_log_loss,
    brier_score,
    calibration_buckets,
    expected_calibration_error,
    max_drawdown,
)
from app.backtesting.schemas import BacktestReport, HistoricalReplaySnapshot, ReplayRecord
from app.domain.schemas import EnsembleOutput, RecommendationStatus
from app.models.probability import BayesianUpdater, EloModel, EnsembleModel, MonteCarloSimulator, PoissonGoalModel
from app.services.recommendations import PortfolioRiskCovarianceFilter, RecommendationEngine


class LookAheadBiasError(ValueError):
    pass


class BacktestEngine:
    def __init__(self, simulations: int = 10_000) -> None:
        self.simulations = simulations
        self.recommender = RecommendationEngine()

    def run(self, snapshots: list[HistoricalReplaySnapshot]) -> BacktestReport:
        ordered = sorted(snapshots, key=lambda s: s.as_of)
        records = [self._replay(snapshot) for snapshot in ordered]
        if not records:
            raise ValueError("at least one replay snapshot is required")
        records = PortfolioRiskCovarianceFilter().apply_to_replay_records(records)

        wins = [record.actual_outcome == record.recommendation.outcome for record in records]
        recommended = [record for record in records if record.recommendation.status == RecommendationStatus.recommended]
        buckets = calibration_buckets(records)
        baselines = [
            baseline_score("market_implied", [r.market_probability for r in records], wins),
            baseline_score("constant_50_percent", [0.50 for _ in records], wins),
        ]
        staked = sum(record.recommendation.fractional_kelly for record in recommended)
        total_pnl = sum(record.profit_loss for record in records)
        return BacktestReport.model_validate(
            {
                "run_id": str(uuid4()),
                "replay_count": len(records),
                "recommended_count": len(recommended),
                "rejected_count": len(records) - len(recommended),
                "accuracy": mean(1.0 if won else 0.0 for won in wins),
                "brier_score": mean(record.brier for record in records),
                "log_loss": mean(record.log_loss for record in records),
                "roi": total_pnl / staked if staked else 0.0,
                "yield": total_pnl / len(records),
                "total_profit_loss": total_pnl,
                "average_edge": mean(record.recommendation.edge for record in records),
                "average_clv": mean(record.closing_line_value for record in records),
                "maximum_drawdown": max_drawdown([record.profit_loss for record in records]),
                "calibration_error": expected_calibration_error(buckets, len(records)),
                "calibration_buckets": buckets,
                "baselines": baselines,
                "records": records,
            }
        )

    def _replay(self, snapshot: HistoricalReplaySnapshot) -> ReplayRecord:
        self._assert_no_lookahead(snapshot)
        elo = EloModel().predict(snapshot.match, snapshot.home_stats, snapshot.away_stats)
        poisson = PoissonGoalModel().predict(snapshot.match, snapshot.home_stats, snapshot.away_stats)
        bayesian = BayesianUpdater().apply_availability_shift(poisson)
        bayesian.model_name = "bayesian_context"
        ensemble = EnsembleModel().combine([elo, poisson, bayesian], match_id=snapshot.match.id)
        simulation = MonteCarloSimulator(simulations=self.simulations).run(
            snapshot.match.id,
            ensemble.expected_home_goals,
            ensemble.expected_away_goals,
        )
        if "under_2_5" in simulation:
            ensemble.metadata["under_2_5"] = simulation["under_2_5"]
            ensemble.metadata["over_2_5"] = simulation["over_2_5"]
        recommendation = self.recommender.evaluate(ensemble, snapshot.market, snapshot.evidence, simulation)
        probability = self._probability_for_outcome(ensemble, snapshot.market.outcome)
        won = self._market_won(snapshot.actual_outcome, snapshot.market.outcome)
        staked = recommendation.status == RecommendationStatus.recommended
        profit_loss = self._profit_loss(snapshot.market.ask, won, recommendation.fractional_kelly) if staked else 0.0
        return ReplayRecord(
            match_id=snapshot.match.id,
            as_of=snapshot.as_of,
            actual_outcome=snapshot.actual_outcome,
            estimated_probability=probability,
            market_probability=snapshot.market.implied_probability,
            closing_probability=snapshot.closing_market_probability,
            brier=brier_score(probability, won),
            log_loss=binary_log_loss(probability, won),
            closing_line_value=probability - snapshot.closing_market_probability,
            profit_loss=profit_loss,
            recommendation=recommendation,
        )

    @staticmethod
    def _assert_no_lookahead(snapshot: HistoricalReplaySnapshot) -> None:
        if snapshot.as_of >= snapshot.match.kickoff_at:
            raise LookAheadBiasError("replay cutoff must be before kickoff")
        if snapshot.market.captured_at > snapshot.as_of:
            raise LookAheadBiasError("market snapshot was captured after replay cutoff")
        for evidence in snapshot.evidence:
            if evidence.observed_at > snapshot.as_of:
                raise LookAheadBiasError(f"evidence {evidence.id} was observed after replay cutoff")

    @staticmethod
    def _probability_for_outcome(model: EnsembleOutput, outcome: str) -> float:
        if outcome in {"under_2_5", "over_2_5"}:
            return float(model.metadata[outcome])
        return {"home_win": model.home_win, "draw": model.draw, "away_win": model.away_win}[outcome]

    @staticmethod
    def _profit_loss(price: float, won: bool, stake: float) -> float:
        return stake * ((1 / price) - 1) if won else -stake

    @staticmethod
    def _market_won(actual_outcome: str, market_outcome: str) -> bool:
        return actual_outcome == market_outcome
