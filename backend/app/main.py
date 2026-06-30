from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.core.scheduler import build_live_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if settings.live_scheduler_enabled:
        scheduler = build_live_scheduler(settings)
        scheduler.start()
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        if scheduler is not None:
            await scheduler.stop()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Research-driven, deterministic quantitative sports trading platform.",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router, prefix="/api")
