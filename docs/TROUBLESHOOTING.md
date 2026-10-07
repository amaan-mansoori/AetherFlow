# Troubleshooting

## Compose refuses to start

Compose requires `POSTGRES_PASSWORD` and `AETHERFLOW_JWT_SECRET_KEY` in the
root `.env`. If the file is absent, copy `.env.example` only when it will not
overwrite an existing file:

```powershell
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
```

Replace the example values with private local values; the JWT secret must be
at least 32 characters. Do not print or share `.env` contents. Validate the
Compose file without rendering resolved environment values:

```powershell
docker compose config --quiet
```

If the command reports a port conflict, check whether ports 8000 or 3000 are
already in use and stop only the specific process you own.

## API readiness is failing

Check service status and PostgreSQL/migration logs:

```powershell
docker compose ps
docker compose logs --tail 100 postgres migrate api
```

The API readiness endpoint checks PostgreSQL. A failed migration prevents
dependent application services from starting; address the migration error
rather than deleting the database volume or editing migration history.

## A submitted job does not progress

Inspect the outbox publisher, Kafka broker, worker, and scheduler:

```powershell
docker compose logs --tail 150 kafka outbox-publisher worker scheduler
```

Immediate work is persisted before publication. A future `schedule_at` value
is expected to remain `ACCEPTED` with no dispatch intent until due. The
scheduler then creates the outbox intent; the publisher sends it to Kafka and
the worker processes it. The default mock provider needs no external API key.

For terminal failures, inspect the job’s attempt history and failure category.
Retry is bounded and limited to selected failure classes. There is no manual
operator retry/replay endpoint. Kafka delivery is at least once, so repeated
dispatches do not prove repeated successful execution, and provider-side work
may be duplicated after a process failure.

## Cancellation appears pending

An `ACCEPTED` scheduled job has not been claimed for execution; cancelling it
transitions it directly to `CANCELLED`, and any pending dispatch is a worker
no-op. Once a job has moved beyond `ACCEPTED`, cancellation uses
`CANCEL_REQUESTED` and depends on worker processing. A provider call already
in flight may still finish; cancellation is not a remote-provider abort
guarantee. Immediate submissions use `CANCEL_REQUESTED` even while they are
still `ACCEPTED`.

## Frontend sign-in or refresh fails

Use `localhost` consistently for both the console and API origins; do not mix
`localhost` and `127.0.0.1`. The refresh cookie is HttpOnly and
SameSite=Strict. Confirm `frontend/.env.local` points to
`http://localhost:8000`, and that the backend's exact CORS allowlist includes
`http://localhost:3000`. If a frontend config file is missing, copy its
example only if the target does not already exist.

## Redis errors

Redis is used for optional API rate limiting, not job state. The application
fails open when Redis is unavailable, so requests can continue but limits are
not enforced during that outage. Check Redis service health and API logs; do
not expect a Redis failure to change persisted job status.

## Stop without deleting local data

Run `docker compose down` to stop Compose while preserving the PostgreSQL
volume. Avoid `docker compose down -v` unless you explicitly intend to delete
the local database and all data in that named volume.
