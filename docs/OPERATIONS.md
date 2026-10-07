# Local Operations

This guide covers the checked-in Docker Compose environment. It is not a
production deployment runbook; there is no verified cloud or Kubernetes
deployment.

## Start and inspect

From the repository root, ensure `.env` exists and contains private local
values as described in the [README](../README.md#quick-start), then start the
stack:

```powershell
docker compose up --build -d
docker compose ps
```

Compose waits for PostgreSQL and Kafka health checks and completes the
one-shot `migrate` service before starting the API and backend workers. The
frontend is a separate Node.js process; start it from `frontend` with
`npm run dev`.

Check API health:

```powershell
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
```

Liveness confirms the API process is serving. Readiness checks PostgreSQL; it
does not report worker, Kafka, or provider health. Inspect each runtime
separately:

```powershell
docker compose logs --tail 100 api migrate outbox-publisher worker scheduler
docker compose logs -f outbox-publisher worker scheduler
```

The Compose health checks cover PostgreSQL, Kafka, Redis, and API readiness.
The worker, outbox publisher, and scheduler have no dedicated health endpoint
in this configuration; use `docker compose ps` and their logs.

## Migrations and durable state

The `migrate` one-shot service runs `alembic upgrade head` before the API,
worker, publisher, and scheduler. If it exits unsuccessfully, inspect
`docker compose logs migrate` and resolve the reported migration or database
connectivity issue before restarting dependent processes.

`docker compose down` stops the stack but preserves the named
`postgres-data` volume. No automatic local-data reset is provided. Do not use
`docker compose down -v` unless you intentionally want to permanently delete
the local database volume and its contents.

## Following work

- Job state, attempts, results, and lifecycle events are persisted in
  PostgreSQL and read through the API/console.
- The outbox publisher is the only bridge from durable dispatch intent to
  Kafka. Inspect its logs and admin dispatch details for publication failures.
- Workers acknowledge Kafka offsets after a durable decision. Execution is
  at least once; duplicate provider calls remain possible.
- A future scheduled job normally remains `ACCEPTED` without an outbox intent
  until due. The scheduler activates due jobs. A scheduled job cancelled while
  still `ACCEPTED` becomes `CANCELLED`; any pending dispatch is a worker no-op.
- There is no operator replay API for permanent outbox failures or general
  retry/requeue control.

## Operational boundaries

Redis rate limiting is optional outside Compose and fails open during Redis
failure. Application metrics are process-local; this repository does not
include a Prometheus server, Grafana dashboards, alerting, distributed tracing,
backups, or production secret management. Treat Compose credentials as local
development configuration only.

For failure diagnosis, see [Troubleshooting](TROUBLESHOOTING.md) and
[Known limitations](KNOWN-LIMITATIONS.md).
