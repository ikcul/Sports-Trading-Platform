CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE matches (
    id TEXT PRIMARY KEY,
    competition TEXT NOT NULL,
    kickoff_at TIMESTAMPTZ NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    neutral_site BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE evidence_nodes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    match_id TEXT NOT NULL REFERENCES matches(id),
    agent TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_url TEXT,
    observed_at TIMESTAMPTZ NOT NULL,
    credibility_score NUMERIC(4,3) NOT NULL,
    confidence NUMERIC(4,3) NOT NULL CHECK (confidence <= 0.99),
    extracted_facts JSONB NOT NULL,
    affected_players JSONB NOT NULL DEFAULT '[]',
    affected_teams JSONB NOT NULL DEFAULT '[]',
    reasoning TEXT NOT NULL,
    links JSONB NOT NULL DEFAULT '[]',
    contradictions JSONB NOT NULL DEFAULT '[]',
    inserted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE team_stats_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    match_id TEXT NOT NULL REFERENCES matches(id),
    team TEXT NOT NULL,
    payload JSONB NOT NULL,
    provider TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE model_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    match_id TEXT NOT NULL REFERENCES matches(id),
    model_name TEXT NOT NULL,
    payload JSONB NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE market_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    market_id TEXT NOT NULL,
    match_id TEXT NOT NULL REFERENCES matches(id),
    outcome TEXT NOT NULL,
    bid NUMERIC(6,5) NOT NULL,
    ask NUMERIC(6,5) NOT NULL,
    last_price NUMERIC(6,5) NOT NULL,
    volume INTEGER NOT NULL,
    liquidity NUMERIC(14,2) NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    market_id TEXT NOT NULL,
    match_id TEXT NOT NULL REFERENCES matches(id),
    status TEXT NOT NULL,
    payload JSONB NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE paper_trade_previews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    match_id TEXT NOT NULL,
    market_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    edge NUMERIC(8,6) NOT NULL,
    target_stake NUMERIC(10,8) NOT NULL,
    payload JSONB NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE order_submissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    idempotency_key TEXT NOT NULL UNIQUE,
    market_id TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity NUMERIC(18,8) NOT NULL,
    price NUMERIC(8,6) NOT NULL,
    status TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX evidence_nodes_match_time_idx ON evidence_nodes(match_id, observed_at DESC);
CREATE INDEX market_snapshots_market_time_idx ON market_snapshots(market_id, captured_at DESC);
CREATE INDEX model_runs_match_model_idx ON model_runs(match_id, model_name, generated_at DESC);
CREATE INDEX paper_trade_previews_match_time_idx ON paper_trade_previews(match_id, generated_at DESC);
CREATE INDEX order_submissions_market_time_idx ON order_submissions(market_id, created_at DESC);
