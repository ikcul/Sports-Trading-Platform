from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, computed_field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentKind(str, Enum):
    research_coordinator = "research_coordinator"
    x_intelligence = "x_intelligence"
    news = "news"
    injury = "injury"
    lineup = "lineup"
    tactical = "tactical"
    coach = "coach"
    player_form = "player_form"
    transfer_locker_room = "transfer_locker_room"
    weather = "weather"
    market_news = "market_news"
    evidence_verification = "evidence_verification"
    report_generation = "report_generation"


class SourceType(str, Enum):
    official_federation = "official_federation"
    official_club = "official_club"
    official_player = "official_player"
    analytics_provider = "analytics_provider"
    tier_one_journalist = "tier_one_journalist"
    major_media = "major_media"
    verified_analyst = "verified_analyst"
    verified_social = "verified_social"
    fan_speculation = "fan_speculation"
    anonymous = "anonymous"


SOURCE_CREDIBILITY: dict[SourceType, float] = {
    SourceType.official_federation: 0.99,
    SourceType.official_club: 0.99,
    SourceType.official_player: 0.98,
    SourceType.analytics_provider: 0.98,
    SourceType.tier_one_journalist: 0.95,
    SourceType.major_media: 0.90,
    SourceType.verified_analyst: 0.80,
    SourceType.verified_social: 0.50,
    SourceType.fan_speculation: 0.20,
    SourceType.anonymous: 0.05,
}


class EvidenceItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    match_id: str
    agent: AgentKind
    source_name: str
    source_type: SourceType
    source_url: str | None = None
    observed_at: datetime = Field(default_factory=utcnow)
    extracted_facts: list[str]
    affected_players: list[str] = Field(default_factory=list)
    affected_teams: list[str] = Field(default_factory=list)
    reasoning: str
    links: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=0.99)

    @computed_field
    @property
    def credibility_score(self) -> float:
        return SOURCE_CREDIBILITY[self.source_type]


class Match(BaseModel):
    id: str
    competition: str
    kickoff_at: datetime
    home_team: str
    away_team: str
    neutral_site: bool = True


class TeamStats(BaseModel):
    team: str
    elo_rating: float
    xg_for: float
    xg_against: float
    shots_for: float
    shots_against: float
    ppda: float
    goalkeeper_goals_prevented: float = 0.0


class ModelOutput(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_name: str
    match_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    home_win: float = Field(ge=0.0, le=1.0)
    draw: float = Field(ge=0.0, le=1.0)
    away_win: float = Field(ge=0.0, le=1.0)
    expected_home_goals: float = Field(ge=0.0)
    expected_away_goals: float = Field(ge=0.0)
    confidence_interval: tuple[float, float]
    variance: float = Field(ge=0.0)
    calibration_error: float = Field(ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EnsembleOutput(ModelOutput):
    component_weights: dict[str, float]
    model_agreement: float = Field(ge=0.0, le=1.0)


class MarketSnapshot(BaseModel):
    market_id: str
    match_id: str
    outcome: str
    bid: float = Field(gt=0.0, lt=1.0)
    ask: float = Field(gt=0.0, lt=1.0)
    last_price: float = Field(gt=0.0, lt=1.0)
    volume: int = Field(ge=0)
    liquidity: float = Field(ge=0.0)
    captured_at: datetime = Field(default_factory=utcnow)

    @computed_field
    @property
    def implied_probability(self) -> float:
        return (self.bid + self.ask) / 2

    @computed_field
    @property
    def spread(self) -> float:
        return self.ask - self.bid


class RecommendationStatus(str, Enum):
    recommended = "recommended"
    rejected = "rejected"


class Recommendation(BaseModel):
    market_id: str
    match_id: str
    outcome: str
    status: RecommendationStatus
    estimated_probability: float
    market_implied_probability: float
    edge: float
    expected_value: float
    kelly_fraction: float
    fractional_kelly: float
    confidence_score: float
    risk_score: float
    evidence_ids: list[str]
    supporting_evidence: list[str]
    key_statistics: dict[str, float]
    simulation_summary: dict[str, Any]
    risks: list[str]
    counterarguments: list[str]
    invalidation_triggers: list[str]
    rejection_reasons: list[str] = Field(default_factory=list)


class CoordinatorOutput(BaseModel):
    match_id: str
    pending_tasks: list[str]
    completed_tasks: list[str]
