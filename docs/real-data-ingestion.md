# Real Historical Backtest Ingestion

The June 11-28, 2026 World Cup Kalshi market partition is generated from the `KXWCGAME` market series. It contains 73 match events and 219 outcome markets.

Generated files:

- `data/world_cup_2026_jun11_jun28/fixtures_required.csv`
- `data/world_cup_2026_jun11_jun28/feature_snapshots_required.csv`
- `data/world_cup_2026_jun11_jun28/evidence_snapshots_required.csv`

The partition remains blocked until the fixture and feature files are filled with timestamped, source-backed historical data.

## Open Data Provider Interfaces

`backend/app/ingestion/open_sports_data_client.py` defines provider adapters for replacing the mock sports feed:

- `APIFootballClient`
- `UnderstatFBrefSnapshotClient`
- `EntitySportClient`

These clients are intentionally interface-first. Production use still requires provider credentials, source snapshotting, and timestamped parser outputs so the backtest can prove every feature was known before `as_of`.

## Required Fixture Fields

`fixtures_required.csv` must be completed with:

- `official_kickoff_utc`
- `home_team`
- `away_team`
- `home_market_ticker`
- `away_market_ticker`
- `draw_market_ticker`
- `actual_outcome`
- `source_url`

The `kalshi_close_time_utc` column is included for reconciliation only. It is not a substitute for official kickoff time.

## Required Feature Fields

`feature_snapshots_required.csv` must be completed with pre-cutoff point-in-time values:

- `observed_at_utc`
- Elo ratings
- xG for and against
- shots for and against
- PPDA
- weather summary
- injury summary
- lineup summary
- source URL

Every `observed_at_utc` must be strictly earlier than the replay `as_of` cutoff.

## Validation Behavior

The loader rejects:

- missing kickoff timestamps
- missing TeamStats fields
- feature rows without matching fixtures
- feature rows that cannot initialize `TeamStats`

The mapper rejects:

- feature snapshots after `as_of`
- Kalshi candles after `as_of`
- `as_of` timestamps at or after kickoff

## Current Status

The real replay is intentionally blocked because official kickoff timestamps and point-in-time feature snapshots are not yet present. This prevents accidental leakage from settled market metadata or post-match information.
