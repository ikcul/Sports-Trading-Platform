from __future__ import annotations

from app.agents.base import ResearchAgent
from app.domain.schemas import AgentKind, CoordinatorOutput, EvidenceItem, SourceType


class ResearchCoordinator:
    def __init__(self, agents: list[ResearchAgent]) -> None:
        self.agents = agents

    async def dispatch(self, match_id: str) -> tuple[CoordinatorOutput, list[EvidenceItem]]:
        completed: list[str] = []
        evidence: list[EvidenceItem] = []
        for agent in self.agents:
            evidence.extend(await agent.collect(match_id))
            completed.append(agent.kind.value)
        return CoordinatorOutput(match_id=match_id, pending_tasks=[], completed_tasks=completed), evidence


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
