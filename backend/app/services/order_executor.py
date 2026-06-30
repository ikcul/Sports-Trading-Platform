from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import EnvMode, Settings, settings
from app.domain.schemas import Recommendation, RecommendationStatus
from app.services.recommendations import MAX_MATCH_EXPOSURE

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionPreview:
    match_id: str
    market_id: str
    outcome: str
    pre_scale_stake: float
    post_scale_stake: float
    message: str


class LiveOrderExecutor:
    def __init__(self, config: Settings = settings, max_match_exposure: float = MAX_MATCH_EXPOSURE) -> None:
        self.config = config
        self.max_match_exposure = max_match_exposure

    def submit_portfolio_positions(self, recommendations: list[Recommendation]) -> list[ExecutionPreview]:
        executable = [
            recommendation
            for recommendation in recommendations
            if recommendation.status == RecommendationStatus.recommended and recommendation.fractional_kelly > 0
        ]
        scaled_stakes = self._scale_same_match_exposure(executable)
        previews: list[ExecutionPreview] = []
        for recommendation in executable:
            stake = scaled_stakes[id(recommendation)]
            message = (
                "LIVE DEPLOYMENT PREVIEW: "
                f"Submitting {recommendation.outcome} ticker position with scaled fractional Kelly stake {stake:.6f} on Kalshi."
            )
            logger.info(message)
            previews.append(
                ExecutionPreview(
                    match_id=recommendation.match_id,
                    market_id=recommendation.market_id,
                    outcome=recommendation.outcome,
                    pre_scale_stake=recommendation.fractional_kelly,
                    post_scale_stake=stake,
                    message=message,
                )
            )
        if self.config.env_mode != EnvMode.production:
            logger.info("Sandbox mode active: generated execution previews only; no live Kalshi orders were submitted.")
        return previews

    def _scale_same_match_exposure(self, recommendations: list[Recommendation]) -> dict[int, float]:
        grouped: dict[str, list[Recommendation]] = {}
        for recommendation in recommendations:
            grouped.setdefault(recommendation.match_id, []).append(recommendation)

        scaled: dict[int, float] = {}
        for match_recommendations in grouped.values():
            total = sum(recommendation.fractional_kelly for recommendation in match_recommendations)
            cap_scale = min(1.0, self.max_match_exposure / total) if total > 0 else 1.0
            covariance_scale = self._covariance_scale(match_recommendations)
            scale = min(cap_scale, covariance_scale)
            for recommendation in match_recommendations:
                scaled[id(recommendation)] = recommendation.fractional_kelly * scale
        return scaled

    @staticmethod
    def _covariance_scale(recommendations: list[Recommendation]) -> float:
        if len(recommendations) < 2:
            return 1.0
        joint_probabilities: list[float] = []
        for left_index, left in enumerate(recommendations):
            for right in recommendations[left_index + 1 :]:
                for key in (f"{left.outcome}_{right.outcome}", f"{right.outcome}_{left.outcome}"):
                    if key in left.simulation_summary:
                        joint_probabilities.append(float(left.simulation_summary[key]))
                        break
                    if key in right.simulation_summary:
                        joint_probabilities.append(float(right.simulation_summary[key]))
                        break
        if not joint_probabilities:
            return 1.0
        average_joint = sum(joint_probabilities) / len(joint_probabilities)
        return max(0.50, min(1.0, 1.0 - average_joint))
