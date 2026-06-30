from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND = PROJECT_ROOT / "backend"
if (BACKEND / "app").exists():
    sys.path.insert(0, str(BACKEND))
else:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import EnvMode, Settings  # noqa: E402
from app.domain.schemas import AgentKind, EnsembleOutput, EvidenceItem, MarketSnapshot, Match, SourceType  # noqa: E402
from app.services.live_gatekeeper import LiveClockGatekeeper  # noqa: E402
from app.services.order_executor import LiveOrderExecutor, PostgresPaperTradeLogStore  # noqa: E402
from app.services.recommendations import RecommendationEngine  # noqa: E402


@dataclass(frozen=True)
class SimMatch:
    match_id: str
    home_team: str
    away_team: str
    venue: str
    home_model: float
    draw_model: float
    away_model: float
    over_model: float
    under_model: float
    base_market_home: float
    base_market_away: float
    base_market_draw: float
    base_market_over: float
    base_market_under: float
    shock: bool = False


SIM_MATCHES = [
    SimMatch("SIM-WC26-MEX-KOR", "Mexico", "Korea Republic", "Mexico City Stadium", 0.58, 0.23, 0.19, 0.61, 0.39, 0.42, 0.29, 0.29, 0.43, 0.57, True),
    SimMatch("SIM-WC26-USA-CZE", "United States", "Czechia", "Los Angeles Stadium", 0.56, 0.25, 0.19, 0.38, 0.62, 0.41, 0.31, 0.28, 0.56, 0.44, True),
    SimMatch("SIM-WC26-BRA-GER", "Brazil", "Germany", "MetLife Stadium", 0.54, 0.24, 0.22, 0.64, 0.36, 0.40, 0.34, 0.26, 0.45, 0.55, True),
    SimMatch("SIM-WC26-ARG-FRA", "Argentina", "France", "Dallas Stadium", 0.47, 0.27, 0.26, 0.57, 0.43, 0.39, 0.35, 0.26, 0.50, 0.50),
    SimMatch("SIM-WC26-ESP-NED", "Spain", "Netherlands", "Miami Stadium", 0.49, 0.26, 0.25, 0.41, 0.59, 0.40, 0.34, 0.26, 0.54, 0.46),
    SimMatch("SIM-WC26-ENG-JPN", "England", "Japan", "Seattle Stadium", 0.59, 0.23, 0.18, 0.58, 0.42, 0.48, 0.27, 0.25, 0.50, 0.50),
    SimMatch("SIM-WC26-POR-URU", "Portugal", "Uruguay", "Atlanta Stadium", 0.51, 0.25, 0.24, 0.55, 0.45, 0.42, 0.33, 0.25, 0.48, 0.52),
    SimMatch("SIM-WC26-CAN-MAR", "Canada", "Morocco", "Toronto Stadium", 0.44, 0.28, 0.28, 0.52, 0.48, 0.37, 0.35, 0.28, 0.47, 0.53),
    SimMatch("SIM-WC26-ITA-COL", "Italy", "Colombia", "Boston Stadium", 0.50, 0.27, 0.23, 0.39, 0.61, 0.43, 0.31, 0.26, 0.54, 0.46),
    SimMatch("SIM-WC26-SEN-AUS", "Senegal", "Australia", "Kansas City Stadium", 0.46, 0.28, 0.26, 0.56, 0.44, 0.38, 0.35, 0.27, 0.49, 0.51),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed live paper-trading previews with simulated multi-market World Cup states.")
    parser.add_argument("--duration-seconds", type=int, default=30)
    parser.add_argument("--tick-seconds", type=float, default=3.0)
    parser.add_argument("--clear", action="store_true", help="Clear existing paper_trade_previews rows before seeding.")
    args = parser.parse_args()

    config = Settings(env_mode=EnvMode.production)
    executor = LiveOrderExecutor(config=config, log_store=PostgresPaperTradeLogStore(config.database_url))
    engine = RecommendationEngine()
    gatekeeper = LiveClockGatekeeper(config)

    ensure_table(config)
    if args.clear:
        clear_table(config)

    started = time.monotonic()
    tick = 0
    while time.monotonic() - started < args.duration_seconds:
        recommendations = []
        now = datetime.now(timezone.utc)
        for index, sim in enumerate(SIM_MATCHES):
            match = Match(
                id=sim.match_id,
                competition="FIFA World Cup 2026 Live Simulation",
                kickoff_at=now + timedelta(hours=2, minutes=index * 7),
                home_team=sim.home_team,
                away_team=sim.away_team,
                neutral_site=True,
            )
            model = model_output(sim, match.id)
            simulation = simulation_summary(sim)
            evidence = evidence_items(sim, now)
            for outcome, market_probability in market_probabilities(sim, tick).items():
                market = market_snapshot(sim, outcome, market_probability, tick)
                recommendation = engine.evaluate_live(match, model, market, evidence, simulation, gatekeeper)
                if recommendation.status.value == "recommended":
                    recommendations.append(recommendation)
        previews = executor.submit_portfolio_positions(recommendations)
        print(f"tick={tick} inserted_previews={len(previews)} recommendations={len(recommendations)}")
        tick += 1
        time.sleep(args.tick_seconds)


def market_probabilities(sim: SimMatch, tick: int) -> dict[str, float]:
    wave = math.sin(tick / 2.0)
    drift = min(0.04, tick * 0.004)
    if sim.shock:
        home = sim.base_market_home + drift + wave * 0.006
        over = sim.base_market_over + drift * 0.8 + wave * 0.005
    else:
        home = sim.base_market_home + wave * 0.01
        over = sim.base_market_over + math.cos(tick / 2.5) * 0.01
    return {
        "home_win": clamp(home),
        "away_win": clamp(sim.base_market_away - wave * 0.006),
        "draw": clamp(sim.base_market_draw + math.cos(tick / 3.0) * 0.006),
        "over_2_5": clamp(over),
        "under_2_5": clamp(sim.base_market_under - math.cos(tick / 2.5) * 0.008),
    }


def model_output(sim: SimMatch, match_id: str) -> EnsembleOutput:
    return EnsembleOutput(
        model_name="live_simulation_ensemble",
        match_id=match_id,
        home_win=sim.home_model,
        draw=sim.draw_model,
        away_win=sim.away_model,
        expected_home_goals=1.6 + sim.home_model * 0.8,
        expected_away_goals=0.9 + sim.away_model * 0.8,
        confidence_interval=(0.42, 0.68),
        variance=0.08,
        calibration_error=0.04,
        component_weights={"elo": 0.35, "poisson": 0.40, "bayesian": 0.25},
        model_agreement=0.91,
        metadata={"over_2_5": sim.over_model, "under_2_5": sim.under_model},
    )


def simulation_summary(sim: SimMatch) -> dict[str, float | int]:
    return {
        "simulations": 5_000,
        "home_win": sim.home_model,
        "draw": sim.draw_model,
        "away_win": sim.away_model,
        "over_2_5": sim.over_model,
        "under_2_5": sim.under_model,
        "home_win_over_2_5": min(sim.home_model, sim.over_model) * 0.72,
        "home_win_under_2_5": min(sim.home_model, sim.under_model) * 0.68,
        "away_win_over_2_5": min(sim.away_model, sim.over_model) * 0.58,
        "away_win_under_2_5": min(sim.away_model, sim.under_model) * 0.61,
        "draw_under_2_5": min(sim.draw_model, sim.under_model) * 0.74,
    }


def evidence_items(sim: SimMatch, now: datetime) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            match_id=sim.match_id,
            agent=AgentKind.news,
            source_name="Live simulation feed",
            source_type=SourceType.analytics_provider,
            observed_at=now - timedelta(minutes=5),
            extracted_facts=[f"{sim.home_team} vs {sim.away_team} live simulation snapshot at {sim.venue}."],
            affected_teams=[sim.home_team, sim.away_team],
            reasoning="Synthetic dashboard demonstration row; not a betting recommendation.",
            confidence=0.93,
        ),
        EvidenceItem(
            match_id=sim.match_id,
            agent=AgentKind.tactical,
            source_name="Live simulation tactical model",
            source_type=SourceType.analytics_provider,
            observed_at=now - timedelta(minutes=4),
            extracted_facts=["Tempo and chance-quality assumptions are stable for this simulated tick."],
            affected_teams=[sim.home_team, sim.away_team],
            reasoning="Synthetic tactical evidence for portfolio risk visualization.",
            confidence=0.91,
        ),
    ]


def market_snapshot(sim: SimMatch, outcome: str, probability: float, tick: int) -> MarketSnapshot:
    bid = clamp(probability - 0.015)
    ask = clamp(probability + 0.015)
    ticker = f"KX-LIVE-DEMO-{sim.match_id}-{outcome.upper()}-{tick:03d}"
    return MarketSnapshot(
        market_id=ticker,
        match_id=sim.match_id,
        outcome=outcome,
        bid=bid,
        ask=ask,
        last_price=probability,
        volume=12_000 + tick * 125,
        liquidity=8_500,
    )


def ensure_table(config: Settings) -> None:
    import psycopg

    database_url = config.database_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
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


def clear_table(config: Settings) -> None:
    import psycopg

    database_url = config.database_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM paper_trade_previews")


def clamp(value: float) -> float:
    return max(0.05, min(0.95, value))


if __name__ == "__main__":
    main()
