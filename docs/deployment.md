# Deployment

## Local Docker

```bash
cp .env.example .env
docker compose up --build
```

Services:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000/api`
- OpenAPI: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

Use managed PostgreSQL and Redis where possible. Store Kalshi and provider credentials in a secret manager. Run ingestion and research agents as separate workers so API latency is isolated from collection jobs.

Model runs should be versioned by model name, code version, input snapshot identifiers, and generated timestamp. Recommendation records should be immutable for auditability.
