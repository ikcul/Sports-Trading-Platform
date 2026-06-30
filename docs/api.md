# API

Base URL: `http://localhost:8000/api`

## `GET /health`

Returns service health.

## `GET /matches`

Returns monitored matches.

## `GET /matches/{match_id}/research`

Runs the research coordinator against configured agents and returns structured evidence.

## `GET /matches/{match_id}/models`

Returns model outputs, ensemble output, and Monte Carlo simulation summary.

## `GET /recommendations`

Returns market recommendations or rejected opportunities. A rejected opportunity includes explicit `rejection_reasons`.

## `GET /recommendations/{market_id}/explain`

Returns traceable evidence, model outputs, simulation summary, risks, counterarguments, and invalidation triggers for a recommendation.

OpenAPI documentation is available at `http://localhost:8000/docs` when the backend is running.
