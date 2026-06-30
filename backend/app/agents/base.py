from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from app.domain.schemas import AgentKind, EvidenceItem, SourceType


class ResearchAgent(ABC):
    kind: AgentKind

    @abstractmethod
    async def collect(self, match_id: str) -> list[EvidenceItem]:
        """Collect structured evidence. Agents must not predict outcomes."""

    def evidence(self, match_id: str, source_name: str, source_type: SourceType, facts: list[str], reasoning: str, confidence: float, links: list[str] | None = None, contradictions: list[str] | None = None) -> EvidenceItem:
        return EvidenceItem(match_id=match_id, agent=self.kind, source_name=source_name, source_type=source_type, observed_at=datetime.now(timezone.utc), extracted_facts=facts, reasoning=reasoning, confidence=min(confidence, 0.99), links=links or [], contradictions=contradictions or [])
