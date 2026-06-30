from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.domain.schemas import EnsembleOutput, EvidenceItem, MarketSnapshot, Match, Recommendation, RecommendationStatus
from app.services.confidence import ConfidenceScorer
from app.services.live_gatekeeper import LiveClockGatekeeper

MAX_MATCH_EXPOSURE = 0.05


@dataclass(frozen=True)
class RecommendationPolicy:
    min_edge: float = 0.035
    min_confidence: float = 0.68
    min_model_agreement: float = 0.76
    min_liquidity: float = 1_000
    max_spread: float = 0.08
    fractional_kelly_multiplier: float = 0.25


@dataclass(frozen=True)
class DerivativePropContext:
    match_id: str
    variables: dict[str, float]
    metadata: dict[str, Any]


class DerivativePropModel(ABC):
    market_outcome: str

    @abstractmethod
    def estimate_probability(self, context: DerivativePropContext) -> float:
        """Return a deterministic probability for a registered derivative market."""


class KickoffsSevenPlusModel(DerivativePropModel):
    market_outcome = "kickoffs_7_plus"

    def estimate_probability(self, context: DerivativePropContext) -> float:
        tempo = context.variables.get("tempo", 0.5)
        defensive_concession = context.variables.get("defensive_concession_rate", 0.5)
        restart_rate = context.variables.get("match_restart_rate", 0.5)
        probability = 0.15 + 0.35 * tempo + 0.25 * defensive_concession + 0.15 * restart_rate
        return max(0.01, min(0.99, probability))


class RecommendationEngine:
    def __init__(self, policy: RecommendationPolicy | None = None, derivative_models: list[DerivativePropModel] | None = None) -> None:
        self.policy = policy or RecommendationPolicy()
        self.confidence = ConfidenceScorer()
        self.derivative_models = {model.market_outcome: model for model in derivative_models or [KickoffsSevenPlusModel()]}

    def evaluate(self, model: EnsembleOutput, market: MarketSnapshot, evidence: list[EvidenceItem], simulation_summary: dict[str, object]) -> Recommendation:
        estimated_probability = self._probability_for_outcome(model, market.outcome)
        market_probability = market.implied_probability
        edge = estimated_probability - market_probability
        expected_value = (estimated_probability * (1 / market.ask - 1)) - (1 - estimated_probability)
        kelly = self._kelly_fraction(estimated_probability, market.ask)
        confidence = self.confidence.score(evidence, model, market)
        reasons: list[str] = []
        if edge < self.policy.min_edge:
            reasons.append("edge_below_threshold")
        if expected_value <= 0:
            reasons.append("non_positive_expected_value")
        if confidence < self.policy.min_confidence:
            reasons.append("confidence_below_threshold")
        if model.model_agreement < self.policy.min_model_agreement:
            reasons.append("model_agreement_below_threshold")
        if market.liquidity < self.policy.min_liquidity:
            reasons.append("insufficient_liquidity")
        if market.spread > self.policy.max_spread:
            reasons.append("bid_ask_spread_too_wide")
        if any(item.contradictions and item.confidence > 0.80 for item in evidence):
            reasons.append("unresolved_high_confidence_contradiction")
        return Recommendation(
            market_id=market.market_id,
            match_id=market.match_id,
            outcome=market.outcome,
            status=RecommendationStatus.rejected if reasons else RecommendationStatus.recommended,
            estimated_probability=estimated_probability,
            market_implied_probability=market_probability,
            edge=edge,
            expected_value=expected_value,
            kelly_fraction=kelly,
            fractional_kelly=kelly * self.policy.fractional_kelly_multiplier,
            confidence_score=confidence,
            risk_score=max(0.01, 1 - confidence + model.variance / 10 + market.spread),
            evidence_ids=[item.id for item in evidence],
            supporting_evidence=[fact for item in evidence for fact in item.extracted_facts[:2]],
            key_statistics={
                "expected_home_goals": model.expected_home_goals,
                "expected_away_goals": model.expected_away_goals,
                "model_agreement": model.model_agreement,
                "calibration_error": model.calibration_error,
                "market_ask": market.ask,
            },
            simulation_summary=simulation_summary,
            risks=["Late lineup changes can invalidate player availability assumptions.", "Market liquidity may be insufficient to enter at displayed price."],
            counterarguments=[c for item in evidence for c in item.contradictions],
            invalidation_triggers=["Confirmed lineup contradicts current availability assumptions.", "Bid/ask spread widens beyond policy maximum.", "New high-credibility evidence conflicts with current evidence graph."],
            rejection_reasons=reasons,
        )

    def evaluate_live(
        self,
        match: Match,
        model: EnsembleOutput,
        market: MarketSnapshot,
        evidence: list[EvidenceItem],
        simulation_summary: dict[str, object],
        gatekeeper: LiveClockGatekeeper | None = None,
    ) -> Recommendation:
        gate = (gatekeeper or LiveClockGatekeeper()).decision_for_match(match)
        gated_evidence = [item for item in evidence if item.observed_at <= gate.as_of]
        recommendation = self.evaluate(model, market, gated_evidence, simulation_summary)
        return recommendation.model_copy(
            update={
                "simulation_summary": {
                    **recommendation.simulation_summary,
                    "operational_as_of": gate.as_of.isoformat(),
                    "evidence_snapshot_locked": gate.snapshot_locked,
                    "lock_reason": gate.lock_reason or "",
                }
            }
        )

    @staticmethod
    def _probability_for_outcome(model: EnsembleOutput, outcome: str) -> float:
        lookup = {"home_win": model.home_win, "draw": model.draw, "away_win": model.away_win}
        if outcome in {"under_2_5", "over_2_5"}:
            value = model.metadata.get(outcome)
            if value is None:
                raise ValueError(f"model metadata missing probability for outcome: {outcome}")
            return float(value)
        if outcome not in lookup:
            raise ValueError(f"unsupported outcome: {outcome}")
        return lookup[outcome]

    @staticmethod
    def _kelly_fraction(probability: float, price: float) -> float:
        net_odds = 1 / price - 1
        fraction = (probability * net_odds - (1 - probability)) / net_odds
        return max(0.0, min(1.0, fraction))


class PortfolioRiskCovarianceFilter:
    def __init__(self, max_match_exposure: float = MAX_MATCH_EXPOSURE) -> None:
        self.max_match_exposure = max_match_exposure

    def apply_to_replay_records(self, records: list[Any]) -> list[Any]:
        grouped: dict[str, list[Any]] = {}
        for record in records:
            recommendation = record.recommendation
            if recommendation.status == RecommendationStatus.recommended and recommendation.fractional_kelly > 0:
                grouped.setdefault(record.match_id, []).append(record)

        adjusted = list(records)
        index_by_id = {id(record): idx for idx, record in enumerate(adjusted)}
        for match_records in grouped.values():
            if len(match_records) < 2:
                continue
            total_exposure = sum(record.recommendation.fractional_kelly for record in match_records)
            cap_scale = min(1.0, self.max_match_exposure / total_exposure) if total_exposure > 0 else 1.0
            joint_probability = self._average_joint_probability(match_records)
            covariance_scale = self._covariance_scale(joint_probability)
            scale = min(cap_scale, covariance_scale)
            if scale >= 0.999:
                continue
            for record in match_records:
                adjusted_record = self._scale_record(record, scale, total_exposure, joint_probability)
                adjusted[index_by_id[id(record)]] = adjusted_record
        return adjusted

    def _scale_record(self, record: Any, scale: float, pre_filter_exposure: float, joint_probability: float) -> Any:
        recommendation = record.recommendation
        scaled_fractional = recommendation.fractional_kelly * scale
        key_statistics = {
            **recommendation.key_statistics,
            "pre_filter_fractional_kelly": recommendation.fractional_kelly,
            "portfolio_scale": scale,
            "match_exposure_cap": self.max_match_exposure,
            "pre_filter_match_exposure": pre_filter_exposure,
            "joint_probability_avg": joint_probability,
        }
        risks = [
            *recommendation.risks,
            "Portfolio covariance filter scaled stake for same-match correlated exposure.",
        ]
        scaled_recommendation = recommendation.model_copy(
            update={
                "fractional_kelly": scaled_fractional,
                "key_statistics": key_statistics,
                "risks": risks,
            }
        )
        won = record.actual_outcome == recommendation.outcome
        ask = float(key_statistics.get("market_ask", recommendation.market_implied_probability))
        profit_loss = self._stake_profit_loss(ask, won, scaled_fractional)
        return record.model_copy(update={"recommendation": scaled_recommendation, "profit_loss": profit_loss})

    @staticmethod
    def _stake_profit_loss(price: float, won: bool, stake: float) -> float:
        if stake <= 0:
            return 0.0
        return stake * ((1 / price) - 1) if won else -stake

    @staticmethod
    def _average_joint_probability(records: list[Any]) -> float:
        values: list[float] = []
        for left_index, left in enumerate(records):
            for right in records[left_index + 1 :]:
                value = PortfolioRiskCovarianceFilter._joint_probability(left.recommendation, right.recommendation)
                if value is not None:
                    values.append(value)
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _joint_probability(left: Recommendation, right: Recommendation) -> float | None:
        keys = [
            f"{left.outcome}_{right.outcome}",
            f"{right.outcome}_{left.outcome}",
        ]
        for key in keys:
            if key in left.simulation_summary:
                return float(left.simulation_summary[key])
            if key in right.simulation_summary:
                return float(right.simulation_summary[key])
        return None

    @staticmethod
    def _covariance_scale(joint_probability: float) -> float:
        if joint_probability <= 0:
            return 1.0
        return max(0.50, min(1.0, 1.0 - joint_probability))
