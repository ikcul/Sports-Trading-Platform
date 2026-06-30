from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import psycopg
from psycopg.types.json import Json

from app.core.config import Settings, settings
from app.domain.schemas import Recommendation, RecommendationStatus
from app.services.recommendations import MAX_MATCH_EXPOSURE, PortfolioRiskCovarianceFilter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionPreview:
    match_id: str
    market_id: str
    outcome: str
    pre_scale_stake: float
    post_scale_stake: float
    message: str


class PaperTradeLogStore(Protocol):
    def record_preview(self, preview: ExecutionPreview, recommendation: Recommendation) -> None:
        """Persist a paper-trade execution preview."""


class JsonlPaperTradeLogStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def record_preview(self, preview: ExecutionPreview, recommendation: Recommendation) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = _preview_payload(preview, recommendation)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")


class PostgresPaperTradeLogStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url.replace("postgresql+psycopg://", "postgresql://")

    def record_preview(self, preview: ExecutionPreview, recommendation: Recommendation) -> None:
        payload = _preview_payload(preview, recommendation)
        try:
            with psycopg.connect(self.database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS paper_trade_previews (
                            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                            match_id TEXT NOT NULL,
                            market_id TEXT NOT NULL,
                            outcome TEXT NOT NULL,
                            edge NUMERIC(8,6) NOT NULL,
                            target_stake NUMERIC(10,8) NOT NULL,
                            payload JSONB NOT NULL,
                            generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                        )
                        """
                    )
                    cursor.execute(
                        """
                        INSERT INTO paper_trade_previews (match_id, market_id, outcome, edge, target_stake, payload)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            preview.match_id,
                            preview.market_id,
                            preview.outcome,
                            recommendation.edge,
                            preview.post_scale_stake,
                            Json(payload, dumps=lambda value: json.dumps(value, default=str)),
                        ),
                    )
        except Exception as exc:
            logger.warning("paper_trade_preview_db_write_failed", exc_info=exc)


class LiveOrderExecutor:
    def __init__(
        self,
        config: Settings = settings,
        max_match_exposure: float = MAX_MATCH_EXPOSURE,
        log_store: PaperTradeLogStore | None = None,
    ) -> None:
        self.config = config
        self.max_match_exposure = max_match_exposure
        self.log_store = log_store or JsonlPaperTradeLogStore(config.paper_trade_log_path)

    def submit_portfolio_positions(self, recommendations: list[Recommendation]) -> list[ExecutionPreview]:
        filtered_recommendations = PortfolioRiskCovarianceFilter(self.max_match_exposure).apply_live_cap(recommendations)
        executable = [
            recommendation
            for recommendation in filtered_recommendations
            if recommendation.status == RecommendationStatus.recommended and recommendation.fractional_kelly > 0
        ]
        previews: list[ExecutionPreview] = []
        for recommendation in executable:
            message = (
                "LIVE REAL-TIME PREVIEW: "
                f"[Match ID: {recommendation.match_id}] "
                f"[Market: {recommendation.market_id}] "
                f"[Edge: {recommendation.edge:.6f}] "
                "[Action: Recommended] -> "
                f"Target Stake: {recommendation.fractional_kelly:.6f} units."
            )
            logger.info(message)
            preview = ExecutionPreview(
                match_id=recommendation.match_id,
                market_id=recommendation.market_id,
                outcome=recommendation.outcome,
                pre_scale_stake=recommendation.key_statistics.get("pre_filter_fractional_kelly", recommendation.fractional_kelly),
                post_scale_stake=recommendation.fractional_kelly,
                message=message,
            )
            self.log_store.record_preview(preview, recommendation)
            previews.append(preview)
        if not self.config.use_live_data:
            logger.info("Sandbox mode active: generated execution previews only; no live Kalshi orders were submitted.")
        return previews

def _preview_payload(preview: ExecutionPreview, recommendation: Recommendation) -> dict[str, object]:
    return {
        "generated_at": datetime.now(timezone.utc),
        "match_id": preview.match_id,
        "market_id": preview.market_id,
        "outcome": preview.outcome,
        "edge": recommendation.edge,
        "estimated_probability": recommendation.estimated_probability,
        "market_implied_probability": recommendation.market_implied_probability,
        "pre_scale_stake": preview.pre_scale_stake,
        "post_scale_stake": preview.post_scale_stake,
        "message": preview.message,
    }
