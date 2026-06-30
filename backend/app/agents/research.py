from __future__ import annotations

import asyncio
from collections.abc import Iterable

from app.agents.base import ResearchAgent
from app.domain.schemas import AgentKind, CoordinatorOutput, EvidenceItem, SourceType

AGENT_TIMEOUT_SECONDS = 15.0


class ResearchCoordinator:
    def __init__(self, agents: list[ResearchAgent], timeout_seconds: float = AGENT_TIMEOUT_SECONDS) -> None:
        self.agents = agents
        self.timeout_seconds = timeout_seconds

    async def dispatch(self, match_id: str) -> tuple[CoordinatorOutput, list[EvidenceItem]]:
        completed_with_evidence: list[str] = []
        completed_empty: list[str] = []
        failed_agents: list[str] = []
        evidence: list[EvidenceItem] = []
        tasks = [self._collect_with_timeout(agent, match_id) for agent in self.agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for agent, result in zip(self.agents, results, strict=True):
            agent_name = agent.kind.value
            if isinstance(result, Exception):
                failed_agents.append(agent_name)
                evidence.append(self._failure_sentinel(match_id, agent.kind, result))
                continue
            valid_items = self._validate_evidence(result)
            evidence.extend(valid_items)
            if valid_items:
                completed_with_evidence.append(agent_name)
            else:
                completed_empty.append(agent_name)
        output = CoordinatorOutput(
            match_id=match_id,
            pending_tasks=[],
            completed_with_evidence=completed_with_evidence,
            completed_empty=completed_empty,
            failed_agents=failed_agents,
        )
        return output, evidence

    async def _collect_with_timeout(self, agent: ResearchAgent, match_id: str) -> list[EvidenceItem]:
        return await asyncio.wait_for(agent.collect(match_id), timeout=self.timeout_seconds)

    @staticmethod
    def _validate_evidence(items: Iterable[EvidenceItem]) -> list[EvidenceItem]:
        valid: list[EvidenceItem] = []
        for item in items:
            if item.source_name and item.observed_at and item.confidence > 0 and item.extracted_facts:
                valid.append(item)
        return valid

    @staticmethod
    def _failure_sentinel(match_id: str, agent: AgentKind, exc: Exception) -> EvidenceItem:
        return EvidenceItem(
            match_id=match_id,
            agent=agent,
            source_name="agent_failure_sentinel",
            source_type=SourceType.anonymous,
            extracted_facts=[f"agent_failed:{agent.value}:{type(exc).__name__}"],
            reasoning=f"Agent collection failed before producing validated evidence: {type(exc).__name__}",
            confidence=0.0,
        )


class NewsAgent(ResearchAgent):
    kind = AgentKind.news

    async def collect(self, match_id: str) -> list[EvidenceItem]:
        return [self.evidence(match_id, "Fixture official feed", SourceType.official_federation, ["Fixture is active in the monitored FIFA competition calendar."], "Official fixture data anchors downstream market and model joins.", 0.97)]


class InjuryAgent(ResearchAgent):
    kind = AgentKind.injury

    async def collect(self, match_id: str) -> list[EvidenceItem]:
        return [self.evidence(match_id, "Training availability feed", SourceType.major_media, ["No confirmed high-impact injury update is present in the current feed."], "Absence of confirmed injury evidence is represented explicitly and can be superseded.", 0.72)]


class TacticalAgent(ResearchAgent):
    kind = AgentKind.tactical

    async def collect(self, match_id: str) -> list[EvidenceItem]:
        return [self.evidence(match_id, "Analyst tactical feed", SourceType.verified_analyst, ["Both teams have sufficient recent match data for formation and pressing analysis."], "The tactical layer records structural observations only; probabilities are model owned.", 0.75)]
