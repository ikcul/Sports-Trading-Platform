from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.agents.base import ResearchAgent
from app.agents.research import ResearchCoordinator
from app.domain.schemas import AgentKind, EvidenceItem, SourceType


class EmptyAgent(ResearchAgent):
    kind = AgentKind.news

    async def collect(self, match_id: str) -> list[EvidenceItem]:
        return []


class ValidAgent(ResearchAgent):
    kind = AgentKind.injury

    async def collect(self, match_id: str) -> list[EvidenceItem]:
        return [
            EvidenceItem(
                match_id=match_id,
                agent=self.kind,
                source_name="Official report",
                source_type=SourceType.official_federation,
                observed_at=datetime.now(timezone.utc),
                extracted_facts=["Player availability confirmed."],
                reasoning="Official evidence.",
                confidence=0.9,
            )
        ]


class FailingAgent(ResearchAgent):
    kind = AgentKind.tactical

    async def collect(self, match_id: str) -> list[EvidenceItem]:
        raise RuntimeError("feed down")


@pytest.mark.asyncio
async def test_research_coordinator_tracks_empty_success_and_failure_sentinel() -> None:
    output, evidence = await ResearchCoordinator([ValidAgent(), EmptyAgent(), FailingAgent()]).dispatch("match-1")
    assert output.completed_with_evidence == ["injury"]
    assert output.completed_empty == ["news"]
    assert output.failed_agents == ["tactical"]
    assert any(item.confidence == 0 and item.source_name == "agent_failure_sentinel" for item in evidence)
