# Development

The root [README quick start](../README.md#quick-start) is the recommended
end-to-end local workflow. This guide covers contributor setup and repeatable
checks.

## Prerequisites

- Python 3.12 or newer for backend development; the container image uses
  Python 3.12.
- Node.js 20.9 or newer and npm for the Next.js 16 console.
- Docker Engine and the Docker Compose plugin for the integrated local stack.
- Git.

PostgreSQL, Kafka, and Redis are supplied by Compose. No external AI provider
credential is needed: the default provider is the deterministic mock.

## Install

From the repository root, copy each example only if a local configuration file
does not already exist. Never replace an existing `.env` or `.env.local`.

```powershell
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
if (-not (Test-Path frontend/.env.local)) {
    Copy-Item frontend/.env.example frontend/.env.local
}

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e "backend[dev]"

Set-Location frontend
npm ci
```

Set private local values for `POSTGRES_PASSWORD` and
`AETHERFLOW_JWT_SECRET_KEY` in `.env`; the JWT secret must be at least 32
characters. These are local development values, not production secret
management.

## Run and validate

Start the local infrastructure and backend processes from the repository root:

```powershell
docker compose up --build -d
docker compose ps
```

Run the frontend in a separate terminal from `frontend`:

```powershell
npm run dev
```

Backend unit and API tests use isolated SQLite and fakes. From `backend`:

```powershell
python -m pytest tests -q
python -m ruff format --check .
python -m ruff check .
python -m mypy src
```

The test suite disables dotenv loading for constructed test settings, so
repository-local credentials are not required for the tests. The conventional
working directory is still `backend`.

From `frontend`, run:

```powershell
npm run test
npm run lint
npm run typecheck
npm run build
```

See the [testing guide](TESTING.md) for coverage boundaries and reported
verification. SQLite/fake-based tests do not establish PostgreSQL locking,
Kafka broker, cross-process Redis, or provider behavior.

## Change discipline

- Keep the modular backend boundaries: API/domain policy in backend modules,
  database and broker details in infrastructure adapters, and process
  entrypoints in `aetherflow.runtime`.
- Version database changes with Alembic migrations and run them explicitly
  before starting application processes.
- Update [API documentation](API.md) when request, response, or state
  transition behavior changes. Update architecture docs and an ADR when a
  material design decision changes.
- Do not include `.env`, `.env.local`, credentials, tokens, generated build
  output, or local databases in a change.
- Keep tests deterministic and do not substitute a fake for a claim about live
  infrastructure. Record exactly which integration services were exercised.
