from __future__ import annotations

from app.core.config import EnvMode, Settings
from app.domain.schemas import Recommendation, RecommendationStatus
from app.services.order_executor import LiveOrderExecutor
from app.services.recommendations import MAX_MATCH_EXPOSURE


class MemoryLogStore:
    def __init__(self) -> None:
        self.records = []

    def record_preview(self, preview, recommendation) -> None:
        self.records.append((preview, recommendation))


def _recommendation(outcome: str, fractional_kelly: float, status: RecommendationStatus = RecommendationStatus.recommended) -> Recommendation:
    return Recommendation(
        market_id=f"ticker-{outcome}",
        match_id="match-1",
        outcome=outcome,
        status=status,
        estimated_probability=0.6,
        market_implied_probability=0.5,
        edge=0.1,
        expected_value=0.1,
        kelly_fraction=fractional_kelly * 4,
        fractional_kelly=fractional_kelly,
        confidence_score=0.8,
        risk_score=0.2,
        evidence_ids=[],
        supporting_evidence=[],
        key_statistics={"market_ask": 0.5},
        simulation_summary={"home_win_under_2_5": 0.42},
        risks=[],
        counterarguments=[],
        invalidation_triggers=[],
    )


def test_settings_reads_operational_credentials_from_env(monkeypatch) -> None:
    monkeypatch.setenv("ENV_MODE", "production")
    monkeypatch.setenv("APIFOOTBALL_API_KEY", "api-key")
    monkeypatch.setenv("APIFOOTBALL_WORLD_CUP_LEAGUE_ID", "1")
    monkeypatch.setenv("KALSHI_API_CREDENTIALS", "kalshi-json")
    settings = Settings()
    assert settings.env_mode == EnvMode.production
    assert settings.use_live_data
    assert settings.has_api_football_credentials
    assert settings.has_kalshi_credentials


def test_live_order_executor_previews_and_caps_same_match_exposure() -> None:
    store = MemoryLogStore()
    executor = LiveOrderExecutor(config=Settings(env_mode=EnvMode.sandbox), log_store=store)
    previews = executor.submit_portfolio_positions(
        [
            _recommendation("home_win", 0.08),
            _recommendation("under_2_5", 0.07),
            _recommendation("away_win", 0.10, RecommendationStatus.rejected),
        ]
    )
    assert len(previews) == 2
    assert sum(preview.post_scale_stake for preview in previews) <= MAX_MATCH_EXPOSURE
    assert "LIVE REAL-TIME PREVIEW" in previews[0].message
    assert len(store.records) == 2
