# Data Model

The canonical SQL schema is in `backend/app/db/schema.sql`.

`matches` stores fixtures and stable match identity.

`evidence_nodes` stores immutable research output. Each node includes source, source type, credibility score, confidence, extracted facts, links, contradictions, and timestamps.

`team_stats_snapshots` stores provider-specific structured statistics. The JSON payload allows provider variance while preserving captured time and provenance.

`model_runs` stores deterministic model outputs, including exact model name and generated timestamp.

`market_snapshots` stores normalized Kalshi market data, bid, ask, last price, volume, liquidity, and captured time.

`recommendations` stores the final policy output. The payload contains both approved recommendations and rejected opportunities with reasons.

Evidence is append-only. Contradictory or stale evidence is not deleted; confidence scoring handles freshness decay and contradiction penalties.
