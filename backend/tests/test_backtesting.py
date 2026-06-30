from __future__ import annotations

from datetime import timedelta

import pytest

from app.backtesting.engine import BacktestEngine, LookAheadBiasError
from app.backtesting.sample_data import sample_historical_snapshots


def test_backtest_sample_produces_validation_metrics() -> None:
    report = BacktestEngine(simulations=500).run(sample_historical_snapshots())
    assert report.replay_count == 4
    assert report.brier_score >= 0
    assert report.log_loss >= 0
    assert len(report.baselines) == 2
    assert len(report.records) == 4


def test_backtest_rejects_future_evidence() -> None:
    snapshots = sample_historical_snapshots()
    snapshots[0].evidence[0].observed_at = snapshots[0].as_of + timedelta(minutes=1)
    with pytest.raises(LookAheadBiasError):
        BacktestEngine(simulations=100).run(snapshots)
