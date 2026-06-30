from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.config import EnvMode, Settings, settings
from app.services.order_executor import LiveOrderExecutor, PostgresPaperTradeLogStore

logger = logging.getLogger(__name__)

JobCallable = Callable[[], Awaitable[None] | None]


@dataclass
class ScheduledJob:
    name: str
    interval_seconds: int
    callback: JobCallable
    runs: int = 0
    failures: int = 0
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_error: str | None = None


class LiveScheduler:
    def __init__(self, jobs: list[ScheduledJob], run_immediately: bool = False) -> None:
        self.jobs = jobs
        self.run_immediately = run_immediately
        self._tasks: list[asyncio.Task[None]] = []
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._tasks = [asyncio.create_task(self._job_loop(job), name=f"live-scheduler:{job.name}") for job in self.jobs]
        logger.info("live_scheduler_started", extra={"jobs": [job.name for job in self.jobs]})

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        logger.info("live_scheduler_stopped")

    async def _job_loop(self, job: ScheduledJob) -> None:
        if self.run_immediately:
            await self.run_job(job)
        while self._running:
            await asyncio.sleep(job.interval_seconds)
            if self._running:
                await self.run_job(job)

    async def run_job(self, job: ScheduledJob) -> None:
        job.last_started_at = datetime.now(timezone.utc)
        try:
            result = job.callback()
            if inspect.isawaitable(result):
                await result
            job.runs += 1
            job.last_error = None
            logger.info("live_scheduler_job_completed", extra={"job": job.name, "runs": job.runs})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            job.failures += 1
            job.last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("live_scheduler_job_failed", extra={"job": job.name, "error": job.last_error})
        finally:
            job.last_finished_at = datetime.now(timezone.utc)


class LiveDataOrchestrator:
    def __init__(self, config: Settings = settings, executor: LiveOrderExecutor | None = None) -> None:
        self.config = config
        self.executor = executor or LiveOrderExecutor(
            config=config,
            log_store=PostgresPaperTradeLogStore(config.database_url) if config.env_mode == EnvMode.production else None,
        )

    async def poll_ingestion(self) -> None:
        if not self.config.has_api_football_credentials:
            logger.info("live_ingestion_skipped_missing_api_football_credentials")
            return
        logger.info(
            "live_ingestion_poll_requested",
            extra={"league_id": self.config.api_football_world_cup_league_id},
        )

    async def sync_markets(self) -> None:
        if not self.config.has_kalshi_credentials:
            logger.info("live_market_sync_skipped_missing_kalshi_credentials")
            return
        logger.info("live_market_sync_poll_requested")

    async def evaluate_models(self) -> None:
        logger.info("live_model_evaluation_requested", extra={"simulations": 5_000})


def build_live_scheduler(config: Settings = settings, orchestrator: LiveDataOrchestrator | None = None) -> LiveScheduler:
    live_orchestrator = orchestrator or LiveDataOrchestrator(config)
    jobs = [
        ScheduledJob("ingestion", config.ingestion_interval_seconds, live_orchestrator.poll_ingestion),
        ScheduledJob("market_sync", config.market_sync_interval_seconds, live_orchestrator.sync_markets),
        ScheduledJob("model_evaluation", config.model_evaluation_interval_seconds, live_orchestrator.evaluate_models),
    ]
    return LiveScheduler(jobs=jobs, run_immediately=False)


def scheduler_status(scheduler: LiveScheduler | None) -> dict[str, Any]:
    if scheduler is None:
        return {"running": False, "jobs": []}
    return {
        "running": scheduler.running,
        "jobs": [
            {
                "name": job.name,
                "interval_seconds": job.interval_seconds,
                "runs": job.runs,
                "failures": job.failures,
                "last_started_at": job.last_started_at,
                "last_finished_at": job.last_finished_at,
                "last_error": job.last_error,
            }
            for job in scheduler.jobs
        ],
    }
