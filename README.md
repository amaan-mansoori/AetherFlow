# AetherFlow

**Distributed AI Job Orchestration Platform**

> **Current status: Phase 2 - Identity and Access Foundation**

Phase 2 contains the backend foundation plus multi-user identity and access: registration, Argon2 password hashing, JWT access tokens, rotating hashed refresh sessions, logout, current-user retrieval, `USER`/`ADMIN` role primitives, hash-indexed one-time API keys, audit events, and identity migrations. Jobs, Kafka, Redis, AI providers, workers, frontend, Kubernetes, and production observability are intentionally deferred.

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

Identity routes are available under `/api/v1/auth`. Login returns a short-lived access token and sets the refresh cookie. API keys are managed under `/api/v1/api-keys`; the raw key secret is shown only in the creation response.

## Migrations

From `backend` with `AETHERFLOW_DATABASE_URL` set:

```powershell
alembic upgrade head
alembic downgrade base
```

The Phase 2 identity migration creates users, roles, refresh sessions, API keys, and audit logs and seeds `USER` and `ADMIN`.

## Verification

```powershell
ruff format --check backend
ruff check backend
mypy backend/src
pytest backend/tests
```
