from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.config import EnvMode, Settings, settings
from app.domain.schemas import Match


@dataclass(frozen=True)
class LiveGateDecision:
    match_id: str
    as_of: datetime
    snapshot_locked: bool
    lock_reason: str | None


class LiveClockGatekeeper:
    def __init__(self, config: Settings = settings) -> None:
        self.config = config

    def decision_for_match(self, match: Match, now: datetime | None = None) -> LiveGateDecision:
        execution_time = self._utc(now)
        as_of = execution_time if self.config.env_mode == EnvMode.production else match.kickoff_at - timedelta(minutes=30)
        lock_reason = self._lock_reason(match, execution_time)
        return LiveGateDecision(
            match_id=match.id,
            as_of=as_of,
            snapshot_locked=lock_reason is not None,
            lock_reason=lock_reason,
        )

    def _lock_reason(self, match: Match, now: datetime) -> str | None:
        kickoff = self._utc(match.kickoff_at)
        lock_window = timedelta(minutes=self.config.live_gate_lock_minutes)
        until_kickoff = kickoff - now
        if timedelta(0) <= until_kickoff <= lock_window:
            return "within_pre_kickoff_lock_window"
        if now >= kickoff:
            return "kickoff_already_reached"
        return None

    @staticmethod
    def _utc(value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
