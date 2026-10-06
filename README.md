# AetherFlow

**Distributed AI Job Orchestration Platform**

> **Current status: Phase 15 - public registration and restricted recruiter demo**

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
Phase 12 adds durable one-shot scheduling. Future jobs remain in PostgreSQL as
`ACCEPTED` records without an outbox intent until `schedule_at` is due. The
independent scheduler then atomically moves the job to `QUEUED` and creates the
existing transactional outbox intent; it never publishes to Kafka directly.
Phase 13 adds bounded ADMIN-only job inspection and CAS-backed audited
cancellation. Phase 14 adds a Next.js operations console that uses the existing
API, keeps access tokens in memory, and recovers sessions only through the
backend's HttpOnly refresh cookie.

## Local production-like Compose stack

Copy `.env.example` to `.env`, replace `POSTGRES_PASSWORD` and
`AETHERFLOW_JWT_SECRET_KEY`, then run:

```powershell
docker compose up --build
```

Compose starts PostgreSQL, KRaft Kafka, and internal Redis, runs
`alembic upgrade head` once,
then starts the API, worker, outbox publisher, and scheduler. Verify `GET /health/live`,
`GET /health/ready`, and `GET /metrics`. Use `docker compose logs -f api worker outbox-publisher scheduler` to inspect
processes and `docker compose down` to stop them.
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

### Registration, administrator access, and recruiter demo

Open `/register` in the console to create a standard `USER` account. Registration
requires a valid email and a 12–128 character password, returns a safe user
record, and does not sign the user in. Email verification and password recovery
are not implemented; registration therefore does not prove control of an email
address. Do not treat this local onboarding flow as production identity proof.
The reserved `recruiter-demo@example.com` address is rejected by public
registration so a self-service account cannot occupy the controlled demo
identity.

Administrator privileges are never accepted from registration. To promote an
existing active registered account, run the trusted operator command from
`backend` against the configured database:

```powershell
python -m aetherflow.commands.provision_admin operator@example.com
```

This command does not create users, refuses demo identities, and records an
audit event. Restrict database and command access to trusted operators.

The dedicated `recruiter-demo@example.com` identity is disabled unless
`AETHERFLOW_DEMO_ENABLED=true` and provisioned explicitly. For a fresh Compose
environment, set the demo-enabled flag in the untracked `.env`, start the stack,
provide `AETHERFLOW_DEMO_PASSWORD` through a secure operator environment (never
the frontend environment), then run the one-off provisioning command:

```powershell
docker compose run --rm --no-deps -e AETHERFLOW_DEMO_PASSWORD api python -m aetherflow.commands.provision_demo
```

For a locally installed backend, set both `AETHERFLOW_DEMO_ENABLED=true` and
`AETHERFLOW_DEMO_PASSWORD` in the operator process environment, then run
`python -m aetherflow.commands.provision_demo` from `backend`. The password is
required only on first provisioning; repeat runs preserve the account password
and idempotently verify the fixtures. The command refuses an email/role
collision and never prints the password. Keep the flag enabled in the API
environment for the login/demo status pages to offer access; set it to false
and restart the API to disable demo discovery. Provisioning does not delete
the account or its records.

Demo access is read-only: the account can inspect only its own seeded future
scheduled and cancellation-requested job fixtures. Those records do not have
dispatch intents, and no execution/result is claimed. Demo users cannot submit
or cancel jobs, create or revoke API keys, or access administrative routes.
They receive no API keys or admin role. Demo credentials are shared environment
secrets, so distribute them only through an authorized recruiter/operator
channel and rotate outside the frontend when required. Production deployments
must use HTTPS with `AETHERFLOW_SECURE_COOKIES=true`, an exact CORS origin
allowlist, protected secret management, and restricted access to the admin
provisioning command. Login, refresh, and logout validate supplied browser
Origins against that allowlist; rate limits require Redis and fail open during
Redis outages. See [ADR-0024](./docs/adr/0024-registration-and-recruiter-demo.md)
for the authentication and demo decisions.

## Operations console

From `frontend`, install dependencies and run the development server:

```powershell
Copy-Item .env.example .env.local
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` to the FastAPI origin.
The API CORS allowlist must include the console origin (localhost:3000 by
default in development). Use `localhost` for both the console and API host in
local development (not `localhost` for one and `127.0.0.1` for the other), so
the browser's `SameSite=Strict` refresh cookie remains same-site. See
[docs/FRONTEND.md](./docs/FRONTEND.md) for the
API/auth contract, polling scope, limitations, and verification details.

## Migrations

From `backend` with `AETHERFLOW_DATABASE_URL` set:

```powershell
alembic upgrade head
```

The Phase 2 identity migration creates users, roles, refresh sessions, API keys, and audit logs; the Phase 3 migration adds jobs, idempotency records, attempts, results, and lifecycle events. Migrations seed `USER` and `ADMIN`; migration `0007_demo_role` adds the restricted `DEMO` role without changing existing users. Downgrading to `base` removes application tables and is for disposable migration-test databases only; the `DEMO` downgrade intentionally refuses while that role is assigned.

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
