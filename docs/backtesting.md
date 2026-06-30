# Backtesting and Validation

Backtesting is a chronological replay of historical matches. The replay engine only allows data with timestamps at or before the replay cutoff, and it rejects any evidence or market snapshot from the future.

## Run the Sample Backtest

With the backend running:

```bash
curl http://127.0.0.1:8000/api/backtests/sample
```

## Real Data Partition

Use `docs/real-data-ingestion.md` for the June 11-28, 2026 World Cup partition. The Kalshi market coverage is mapped, but the replay remains blocked until official kickoff timestamps and point-in-time feature snapshots are loaded.

## Trade Ledger Audit

Executed recommendations can be inspected with:

```bash
python work/audit_backtest_ledger.py outputs/world_cup_2026_jun11_jun28_mock_backtest.json
```

The auditor only prints records where `recommendation.status == "recommended"` and `kelly_fraction > 0`.

## Totals Markets

The replay stack supports `under_2_5` and `over_2_5` market outcomes when a fixture partition includes `KXWCTOTAL-*` tickers. Monte Carlo simulation emits `under_2_5` and `over_2_5` probabilities from sampled joint goal distributions.

The sample endpoint returns:

- Replay count
- Recommended and rejected counts
- Accuracy
- Brier score
- Log loss
- ROI and yield
- Average edge
- Average Closing Line Value
- Maximum drawdown
- Calibration buckets
- Baseline comparisons
- Per-match replay records

## Production Backtest Flow

1. Build timestamped historical snapshots for each match.
2. Set an `as_of` cutoff before kickoff.
3. Include only evidence, stats, injuries, lineups, weather, and market prices known before `as_of`.
4. Replay matches chronologically.
5. Store every recommendation and intermediate model output.
6. Compare model probabilities against market-implied probabilities and closing prices.
7. Evaluate calibration, ROI, CLV, drawdown, baselines, and ablations.

## Required Data Shape

Each replay snapshot needs:

- `match`
- `as_of`
- `home_stats`
- `away_stats`
- `market`
- `closing_market_probability`
- `actual_outcome`
- `evidence`

## Guardrails

The engine raises `LookAheadBiasError` when:

- Replay cutoff is at or after kickoff
- Market snapshot was captured after the cutoff
- Any evidence item was observed after the cutoff

This is the minimum guardrail needed before adding real historical data sources, walk-forward validation, and ablation runs.
