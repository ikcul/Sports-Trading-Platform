from __future__ import annotations

import math
from statistics import mean

from app.backtesting.schemas import BaselineScore, CalibrationBucket, ReplayRecord


EPSILON = 1e-12


def binary_log_loss(probability: float, won: bool) -> float:
    p = min(1 - EPSILON, max(EPSILON, probability))
    return -(math.log(p) if won else math.log(1 - p))


def brier_score(probability: float, won: bool) -> float:
    return (probability - (1.0 if won else 0.0)) ** 2


def max_drawdown(profit_loss: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for pnl in profit_loss:
        equity += pnl
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return abs(worst)


def calibration_buckets(records: list[ReplayRecord], width: float = 0.05) -> list[CalibrationBucket]:
    buckets: list[CalibrationBucket] = []
    lower = 0.0
    while lower < 1.0:
        upper = min(1.0, lower + width)
        members = [
            r
            for r in records
            if lower <= r.estimated_probability < upper or (upper == 1.0 and r.estimated_probability == 1.0)
        ]
        if members:
            wins = [1.0 if r.actual_outcome == r.recommendation.outcome else 0.0 for r in members]
            buckets.append(
                CalibrationBucket(
                    bucket=f"{int(lower * 100)}-{int(upper * 100)}%",
                    count=len(members),
                    average_prediction=mean(r.estimated_probability for r in members),
                    empirical_win_rate=mean(wins),
                )
            )
        lower = upper
    return buckets


def expected_calibration_error(buckets: list[CalibrationBucket], total_count: int) -> float:
    if total_count == 0:
        return 0.0
    return sum(
        (bucket.count / total_count) * abs(bucket.average_prediction - bucket.empirical_win_rate)
        for bucket in buckets
    )


def baseline_score(name: str, probabilities: list[float], wins: list[bool]) -> BaselineScore:
    return BaselineScore(
        name=name,
        brier=mean(brier_score(p, won) for p, won in zip(probabilities, wins, strict=True)),
        log_loss=mean(binary_log_loss(p, won) for p, won in zip(probabilities, wins, strict=True)),
    )
