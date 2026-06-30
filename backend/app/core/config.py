from __future__ import annotations

from enum import Enum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvMode(str, Enum):
    sandbox = "sandbox"
    production = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", populate_by_name=True)

    app_name: str = "Quantitative Sports Trading Platform"
    environment: str = "local"
    env_mode: EnvMode = Field(default=EnvMode.sandbox, validation_alias="ENV_MODE")
    database_url: str = "postgresql+psycopg://quant:quant@postgres:5432/quant"
    redis_url: str = "redis://redis:6379/0"
    cors_origins: list[str] = ["http://localhost:3000"]
    monte_carlo_simulations: int = 100_000
    log_level: str = "INFO"
    api_football_api_key: str | None = Field(default=None, validation_alias="APIFOOTBALL_API_KEY")
    api_football_world_cup_league_id: str | None = Field(default=None, validation_alias="APIFOOTBALL_WORLD_CUP_LEAGUE_ID")
    kalshi_api_credentials: str | None = Field(default=None, validation_alias="KALSHI_API_CREDENTIALS")

    @property
    def use_live_data(self) -> bool:
        return self.env_mode == EnvMode.production

    @property
    def has_api_football_credentials(self) -> bool:
        return bool(self.api_football_api_key and self.api_football_world_cup_league_id)

    @property
    def has_kalshi_credentials(self) -> bool:
        return bool(self.kalshi_api_credentials)


settings = Settings()
