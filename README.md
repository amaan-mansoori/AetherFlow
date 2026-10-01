# AetherFlow

**Distributed AI Job Orchestration Platform**

> **Current status: Phase 11 - Redis coordination and distributed rate limiting**

Phase 4C transactionally records each job's Kafka dispatch intent with durable
job creation. Phase 4D/4E add an independent bounded publisher runtime with
lease recovery, typed failures, persisted retry scheduling, and bounded
backoff. Phase 4F adds worker execution leases and deterministic stale-execution
recovery. Phase 5 adds a provider registry, deterministic mock provider,
normalized provider failures, and worker-enforced execution timeouts. Kafka is
not required for deterministic unit tests and is not claimed as locally
verified unless a broker is available. Real external provider validation remains
environment-dependent. Phase 6 adds deterministic bounded execution retry,
durable future retry
dispatch intents, and cancellation-safe failure recovery. Phase 7 adds
process-local Prometheus-compatible metrics and dependency-aware health checks.
Phase 9 adds an isolated OpenAI-compatible provider adapter. Phase 10 validates
what can be executed locally and distinguishes deterministic verification from
infrastructure-dependent verification. The deterministic mock remains the
default and no provider credential is stored in jobs, Kafka, logs, metrics, or
API responses. In the current environment Docker's Linux engine is unavailable,
so PostgreSQL/Kafka/Compose E2E and real-provider smoke validation are
unverified.
Phase 11 adds optional Redis-backed distributed API rate limiting. PostgreSQL
remains the durable source of truth, Kafka remains asynchronous transport, and
Redis is ephemeral coordination only. Rate limiting is fail-open when Redis is
unavailable.

## Local production-like Compose stack

Copy `.env.example` to `.env`, replace `POSTGRES_PASSWORD` and
`AETHERFLOW_JWT_SECRET_KEY`, then run:

```powershell
docker compose up --build
```

Compose starts PostgreSQL, KRaft Kafka, and internal Redis, runs
`alembic upgrade head` once,
then starts the API, worker, and outbox publisher. Verify `GET /health/live`,
`GET /health/ready`, and `GET /metrics`. Use `docker compose logs -f api worker
outbox-publisher` to inspect processes and `docker compose down` to stop them.
Use `docker compose down -v` only when intentionally deleting local data.
The Compose credentials are local-development values, not production secrets.

## Local backend setup

1. Use Python 3.12 or newer.
2. Create a virtual environment and install `backend` with development extras:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -e .\backend[dev]
   ```

3. Copy `.env.example` to `.env`, replace `AETHERFLOW_JWT_SECRET_KEY` with a random value of at least 32 characters, and set `AETHERFLOW_DATABASE_URL` to a reachable PostgreSQL database. Set `AETHERFLOW_SECURE_COOKIES=true` when using HTTPS/production.
4. Start the API:

   ```powershell
   uvicorn aetherflow.main:app --app-dir backend/src --host 127.0.0.1 --port 8000
   ```

5. Check `GET /health/live` and `GET /health/ready`.
6. Scrape `GET /metrics` for bounded-label application metrics.

Redis rate limiting is disabled by default for local backend runs. Set
`AETHERFLOW_REDIS_ENABLED=true` and configure `AETHERFLOW_REDIS_URL` to enable
the `auth` and `api` fixed-window classes.

Identity routes are available under `/api/v1/auth`. Login returns a short-lived access token and sets the refresh cookie. API keys are managed under `/api/v1/api-keys`; the raw key secret is shown only in the creation response.

## Migrations

From `backend` with `AETHERFLOW_DATABASE_URL` set:

```powershell
alembic upgrade head
alembic downgrade base
```

The Phase 2 identity migration creates users, roles, refresh sessions, API keys, and audit logs; the Phase 3 migration adds jobs, idempotency records, attempts, results, and lifecycle events. Migrations seed `USER` and `ADMIN`.

## Verification

```powershell
ruff format --check backend
ruff check backend
mypy backend/src
pytest backend/tests
```

Phase 10 verification status is documented in
`docs/adr/0019-production-validation-and-e2e-verification.md` and the
development log. The unit suite, static checks, and isolated migration checks
are deterministic; they are not evidence of PostgreSQL or Kafka integration.
