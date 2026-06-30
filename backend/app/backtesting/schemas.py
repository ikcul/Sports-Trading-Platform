from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.schemas import EvidenceItem, MarketSnapshot, Match, Recommendation, TeamStats


class HistoricalReplaySnapshot(BaseModel):
    match: Match
    as_of: datetime
    home_stats: TeamStats
    away_stats: TeamStats
    market: MarketSnapshot
    closing_market_probability: float = Field(gt=0.0, lt=1.0)
    actual_outcome: str
    evidence: list[EvidenceItem]


class ReplayRecord(BaseModel):
    match_id: str
    as_of: datetime
    actual_outcome: str
    estimated_probability: float
    market_probability: float
    closing_probability: float
    brier: float
    log_loss: float
    closing_line_value: float
    profit_loss: float
    recommendation: Recommendation


class CalibrationBucket(BaseModel):
    bucket: str
    count: int
    average_prediction: float
    empirical_win_rate: float


class BaselineScore(BaseModel):
    name: str
    brier: float
    log_loss: float


class BacktestReport(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    run_id: str
    replay_count: int
    recommended_count: int
    rejected_count: int
    accuracy: float
    brier_score: float
    log_loss: float
    roi: float
    yield_: float = Field(alias="yield")
    total_profit_loss: float
    average_edge: float
    average_clv: float
    maximum_drawdown: float
    calibration_error: float
    calibration_buckets: list[CalibrationBucket]
    baselines: list[BaselineScore]
    records: list[ReplayRecord]
