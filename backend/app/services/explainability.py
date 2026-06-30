from __future__ import annotations

from app.domain.schemas import EvidenceItem, Recommendation


class ExplainabilityEngine:
    def render(self, recommendation: Recommendation, evidence: list[EvidenceItem]) -> dict[str, object]:
        evidence_by_id = {item.id: item for item in evidence}
        supporting = [evidence_by_id[eid] for eid in recommendation.evidence_ids if eid in evidence_by_id]
        return {
            "market_id": recommendation.market_id,
            "status": recommendation.status,
            "why": {
                "estimated_probability": recommendation.estimated_probability,
                "market_implied_probability": recommendation.market_implied_probability,
                "edge": recommendation.edge,
                "expected_value": recommendation.expected_value,
                "confidence_score": recommendation.confidence_score,
                "risk_score": recommendation.risk_score,
            },
            "evidence_timeline": [
                {"timestamp": item.observed_at.isoformat(), "source": item.source_name, "credibility": item.credibility_score, "facts": item.extracted_facts, "links": item.links, "contradictions": item.contradictions}
                for item in sorted(supporting, key=lambda e: e.observed_at)
            ],
            "model_outputs": recommendation.key_statistics,
            "simulation_summary": recommendation.simulation_summary,
            "risks": recommendation.risks,
            "counterarguments": recommendation.counterarguments,
            "invalidation_triggers": recommendation.invalidation_triggers,
        }
