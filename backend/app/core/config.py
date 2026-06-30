from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Quantitative Sports Trading Platform"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://quant:quant@postgres:5432/quant"
    redis_url: str = "redis://redis:6379/0"
    cors_origins: list[str] = ["http://localhost:3000"]
    monte_carlo_simulations: int = 100_000
    log_level: str = "INFO"


settings = Settings()
