from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import psycopg
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)


class PaperTradePreview(BaseModel):
    id: str
    match_id: str
    market_id: str
    outcome: str
    edge: float
    target_stake: float
    estimated_probability: float | None = None
    market_implied_probability: float | None = None
    action: str = "LIVE PREVIEW POSITION"
    generated_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class PaperTradeRepository:
    def __init__(self, database_url: str = settings.database_url) -> None:
        self.database_url = database_url.replace("postgresql+psycopg://", "postgresql://")

    def list_recent(self, limit: int = 100) -> list[PaperTradePreview]:
        try:
            with psycopg.connect(self.database_url) as connection:
                with connection.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT id::text, match_id, market_id, outcome, edge, target_stake, payload, generated_at
                        FROM paper_trade_previews
                        ORDER BY generated_at DESC
                        LIMIT %s
                        """,
                        (limit,),
                    )
                    return [self._row_to_preview(row) for row in cursor.fetchall()]
        except psycopg.errors.UndefinedTable:
            logger.info("paper_trade_previews_table_missing")
            return []
        except Exception as exc:
            logger.warning("paper_trade_preview_read_failed", exc_info=exc)
            return []

    @staticmethod
    def _row_to_preview(row: dict[str, Any]) -> PaperTradePreview:
        payload = row.get("payload") or {}
        return PaperTradePreview(
            id=str(row["id"]),
            match_id=row["match_id"],
            market_id=row["market_id"],
            outcome=row["outcome"],
            edge=float(row["edge"]),
            target_stake=float(row["target_stake"]),
            estimated_probability=_optional_float(payload.get("estimated_probability")),
            market_implied_probability=_optional_float(payload.get("market_implied_probability")),
            generated_at=row["generated_at"],
            payload=payload,
        )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
