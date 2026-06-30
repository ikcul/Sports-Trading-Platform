from __future__ import annotations

from datetime import datetime, timezone

from app.domain.schemas import EnsembleOutput, EvidenceItem, MarketSnapshot


class ConfidenceScorer:
    def score(self, evidence: list[EvidenceItem], model: EnsembleOutput, market: MarketSnapshot, historical_calibration: float = 0.94, lineup_certainty: float = 0.70) -> float:
        if not evidence:
            return 0.0
        now = datetime.now(timezone.utc)
        weighted_evidence = []
        contradiction_penalty = 0.0
        for item in evidence:
            age_hours = max(0.0, (now - item.observed_at).total_seconds() / 3600)
            freshness = 1 / (1 + age_hours / 24)
            weighted_evidence.append(item.credibility_score * item.confidence * freshness)
            contradiction_penalty += 0.05 * len(item.contradictions)
        evidence_agreement = sum(weighted_evidence) / len(weighted_evidence)
        market_stability = max(0.0, 1 - market.spread * 4)
        score = 0.22 * evidence_agreement + 0.22 * model.model_agreement + 0.18 * historical_calibration + 0.14 * lineup_certainty + 0.12 * market_stability + 0.12 * max(0.0, 1 - model.calibration_error) - contradiction_penalty
        return max(0.0, min(0.99, score))
