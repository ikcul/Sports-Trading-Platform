from __future__ import annotations

import asyncio
from typing import Any

from redis.asyncio import from_url

from app.core.config import settings


async def redis_healthcheck(timeout_seconds: float = 2.0) -> dict[str, Any]:
    """Ping Redis using the same authenticated URL configured for the backend."""

    client = from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    try:
        pong = await asyncio.wait_for(client.ping(), timeout=timeout_seconds)
        return {"status": "ok" if pong else "unhealthy", "authenticated": bool(pong)}
    except Exception as exc:
        return {"status": "error", "authenticated": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        await client.aclose()
