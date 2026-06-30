from __future__ import annotations

import httpx
import pytest
import asyncio
from datetime import datetime, timedelta, timezone

from app.core.config import EnvMode, Settings
from app.core.scheduler import LiveScheduler, ScheduledJob, build_live_scheduler
from app.domain.schemas import Match
from app.services.live_gatekeeper import LiveClockGatekeeper


@pytest.mark.asyncio
async def test_scheduler_initializes_and_stops_cleanly() -> None:
    calls = 0

    async def noop() -> None:
        nonlocal calls
        calls += 1

    scheduler = LiveScheduler([ScheduledJob("noop", 60, noop)], run_immediately=True)
    scheduler.start()
    await asyncio.sleep(0)
    await scheduler.stop()
    assert not scheduler.running
    assert scheduler.jobs[0].runs == 1
    assert calls == 1


@pytest.mark.asyncio
async def test_scheduler_records_network_drop_without_crashing_loop() -> None:
    async def failing_feed() -> None:
        raise httpx.ConnectError("network unavailable")

    job = ScheduledJob("market_sync", 60, failing_feed)
    scheduler = LiveScheduler([job])
    await scheduler.run_job(job)
    assert job.failures == 1
    assert "ConnectError" in (job.last_error or "")


def test_build_live_scheduler_registers_required_jobs() -> None:
    scheduler = build_live_scheduler(
        Settings(
            env_mode=EnvMode.sandbox,
            ingestion_interval_seconds=3600,
            market_sync_interval_seconds=120,
            model_evaluation_interval_seconds=300,
        )
    )
    assert [job.name for job in scheduler.jobs] == ["ingestion", "market_sync", "model_evaluation"]


def test_live_gatekeeper_locks_snapshot_inside_pre_kickoff_window() -> None:
    kickoff = datetime(2026, 7, 1, 20, 0, tzinfo=timezone.utc)
    match = Match(id="match-1", competition="FIFA World Cup", kickoff_at=kickoff, home_team="A", away_team="B")
    gatekeeper = LiveClockGatekeeper(Settings(env_mode=EnvMode.production, live_gate_lock_minutes=15))
    decision = gatekeeper.decision_for_match(match, now=kickoff - timedelta(minutes=10))
    assert decision.as_of == kickoff - timedelta(minutes=10)
    assert decision.snapshot_locked
    assert decision.lock_reason == "within_pre_kickoff_lock_window"
