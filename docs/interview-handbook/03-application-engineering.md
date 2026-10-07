# Chapter 11 — FastAPI and API Design

## Routing, validation, and dependency boundaries

The application composes versioned routers under `/api/v1`. Route functions
are HTTP adapters: Pydantic request/response models define the wire contract;
dependencies resolve the async SQLAlchemy session and authenticated principal;
job/auth services enforce domain rules. This keeps provider execution out of
the request handler. OpenAPI is generated from FastAPI route/schema
declarations; health and metrics routes can be excluded from the public schema.

Unknown request fields are rejected on key public schemas. The error contract
is normalized to:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "request_id": "request-id",
    "details": {"fields": [{"location": ["body", "model"], "message": "Field required"}]}
  }
}
```

The exact example `request_id` is illustrative. Pydantic validation is mapped
to HTTP 400. Expected domain/API errors preserve status and stable error code;
unexpected exceptions are logged with server context and return a generic
HTTP 500 body rather than a traceback.

## Endpoint map

| Method/path | Purpose | Access |
|---|---|---|
| `POST /api/v1/auth/register` | Create identity. | Public, subject to configured controls. |
| `POST /api/v1/auth/login` | Issue access token and refresh cookie. | Public, rate-limited. |
| `POST /api/v1/auth/refresh` | Rotate refresh session and issue a new access token. | Cookie + allowed origin. |
| `POST /api/v1/auth/logout` | Revoke session family and clear refresh cookie. | Cookie/origin-aware. |
| `GET /api/v1/auth/me` | Return current principal and roles. | Authenticated. |
| `POST /api/v1/jobs` | Idempotently submit a job. | Authenticated non-demo principal. |
| `GET /api/v1/jobs` | List caller's jobs with bounded pagination/filters. | Authenticated. |
| `GET /api/v1/jobs/{id}` | Read owner-scoped job/detail. | Owner or authorized admin. |
| `POST /api/v1/jobs/{id}/cancel` | Request/perform state-safe cancellation. | Owner or authorized admin. |
| `GET /api/v1/jobs/{id}/events` | Read lifecycle history. | Owner or authorized admin. |
| `GET /api/v1/jobs/{id}/attempts` | Read execution attempts. | Owner or authorized admin. |
| `GET /health/live`, `GET /health/ready` | Process liveness and database readiness. | Operational probes. |
| `GET /metrics` | Prometheus exposition. | Operational route. |

Administrative routes under `/api/v1/admin` provide bounded queue/job and
redacted operational views to admins. Check `backend/src/aetherflow/api/v1`
for the exact filters and response model before quoting one. The implemented
pagination for user event/attempt collections is limit/offset; do not call it
cursor pagination.

Example response shape for a created job (values illustrative):

```json
{
  "id": "11111111-1111-4111-8111-111111111111",
  "state": "ACCEPTED",
  "version": 1,
  "type": "structured_inference",
  "model": "mock-model",
  "created_at": "2026-01-01T12:00:00Z"
}
```

Use the actual response schema in `jobs/schemas.py` rather than promising
these exact values or field subset. API versioning is a URL prefix; no claim
of a multi-version migration policy is made.

## Health, readiness, limiting and error behavior

Liveness is dependency-free. Readiness probes PostgreSQL and returns
unavailable if the database check fails; it does not test Kafka, Redis, or an
external inference provider. API rate limiting is middleware around
`/api/v1/` routes with a separate auth class; it is optional and Redis
fail-open. This is a deliberate availability/abuse-control trade-off, not a
strict security boundary.

## Design alternatives

FastAPI gives typed request validation and OpenAPI with async endpoint
support. Django REST Framework could be preferable for a product needing its
integrated admin/ORM/auth ecosystem; Flask could be adequate for a smaller
synchronous API but requires assembling more conventions. These are
retrospective comparisons: no repository evidence says they were all
evaluated during original selection.

# Chapter 12 — Frontend and User Experience

## Actual UI structure and API interaction

The frontend is a Next.js App Router application in `frontend/app`, React 19,
TypeScript, CSS/Tailwind-based styling, Lucide icons, and a small set of
product-specific components. The console offers sign-in/registration, an
optional read-only demo mode, job submission/list/detail, filters and
pagination, cancellation confirmation, and admin operational views. Do not
describe it as a real-time WebSocket console: job detail polls the API about
every 10 seconds while the document is visible and the job is nonterminal.

`frontend/lib/api/client.ts` centralizes the API base URL, bearer token in
memory, credentialed fetches for refresh cookies, structured `ApiError`
responses, bounded query parameters, and a refresh attempt after an eligible
401. `auth-provider.tsx` coordinates registration/login and session
refresh. The UI avoids putting long-lived bearer credentials in local storage;
refresh is handled with an HttpOnly cookie. A stale return URL is constrained
to safe in-app destinations.

Job detail presents current state and result, event/attempt histories, and a
cancellation flow. Polling is suspended while hidden and resumes when the
document becomes visible. The view distinguishes an accepted scheduled-job
cancellation from a general cancellation request. Loading, errors, retry,
terminal-state and no-data surfaces are covered by component/API-client
tests.

## Frontend alternatives

Next.js supports server/client composition and routing; a Vite SPA could be
simpler if server rendering and framework routing are not needed. A heavier
design system could improve accessibility consistency at the cost of
dependencies and overrides. Current implementation uses custom console
components; do not infer shadcn/ui or Framer Motion use from the original
product brief. Alternatives here are retrospective rather than documented
original selection history.

## UX trade-offs

Polling is easy to reason about and recovers after tab re-entry, but it
increases periodic read traffic and can delay updates. At higher scale,
server-sent events or WebSockets could lower perceived latency, but require
connection management, authorization on streams, fan-out/backpressure, and a
durable catch-up path. Terminal state still needs to be read from the API.

# Chapter 13 — Authentication and Security

## Implemented controls

- **Passwords:** Argon2 `PasswordHasher`; request schema bounds password
  length and rejects blank values.
- **Access:** short-lived HS256 bearer access tokens. Authentication
  rechecks the current user/session family and loads current database roles;
  a role is not trusted solely because an old browser screen displays it.
- **Refresh:** opaque random refresh material is stored hashed, set in an
  HttpOnly cookie, rotated on use, and bound to a session family. Logout
  revokes the family so associated access tokens become invalid under the
  implemented check.
- **API keys:** one-time secret display, public-ID lookup and stored hash;
  revoke and last-used metadata. Treat the full key like a password.
- **Authorization:** service queries constrain ordinary users to their own
  jobs; admin views require admin role. The optional DEMO principal is
  read-only and restricted from submission/mutation.
- **Browser origin:** configured origin allowlist is applied to cookie-auth
  routes. CORS is explicit; wildcard credentials are not an acceptable
  substitute for an origin allowlist.
- **Secret handling:** settings come from runtime configuration; payload
  schemas reject credential-like job config. No environment secret values
  belong in this handbook.

Authentication answers “who is this caller?” Authorization answers “may
this caller perform this operation on this exact object?” Owner filtering is
therefore important on reads, not just on mutation. The auth tests include
cross-user isolation and role/ownership field injection checks.

## Controls that are absent or incomplete

Email verification and password recovery are absent. There is no claim of MFA,
SSO, WebAuthn, account lockout, or a public production threat review.
Rate-limiter keys use a public API-key identifier when available and client
host otherwise; bearer users without API keys are therefore grouped by
network host for the general limiter. Redis failure is logged/metriced and
fails open, so protection is reduced during that outage. The demo password is
shared only by an explicitly provisioned operator and is not a production
identity strategy.

## Threat-model prompts and improvements

Protect against credential stuffing, refresh-token theft/replay, IDOR,
overprivileged demo/admin access, prompt/PII leakage, API-key exfiltration,
forged client IP behind proxy headers, CSRF on cookie routes, origin
misconfiguration, dependency compromise and resource exhaustion. Production
readiness would include TLS and trusted proxy policy, rate limiting with
known outage behavior, secret rotation, backups, retention/deletion policy,
audit review, dependency scanning, security headers, abuse controls and
incident response.

Interview rule: state the concrete present control first; distinguish
“implemented” from “must be configured” and from “would add.” Never suggest
that a bearer token alone proves the caller owns a job.

# Chapter 14 — Observability and Operations

## Signals that exist

The backend exposes Prometheus-compatible process-local metrics for request
classes, job transitions, worker execution, retry decisions, outbox
publication, rate limits/Redis errors, and durations. Labels are bounded to
avoid arbitrary job IDs. Structured logs include request/job correlation
where available. Readiness means PostgreSQL is reachable; liveness means the
API process can answer. These are not interchangeable.

Metrics are in-memory and reset on process restart. The repository does not
bundle a Prometheus server, Grafana dashboards, alerting, an OpenTelemetry
collector, durable traces, or worker registry. A local metric endpoint is
instrumentation, not a complete observability deployment.

## Triage runbook

| Symptom | First evidence | Next checks |
|---|---|---|
| API will not start | API process log and Compose status. | Settings validation, port binding, PostgreSQL URL/network, import/runtime error. Never print secret environment values. |
| Database connection failure | `/health/ready`, DB logs, connection count. | Host/port/database, migration completion, credentials source, pool budget, TLS policy. |
| Migration failure | Migration process exit and Alembic revision. | Database target, current revision, failed DDL, backup/rollback plan. Do not run destructive downgrade on shared data casually. |
| Kafka unavailable | Publisher/worker logs; unpublished outbox age/count. | Broker listener advertised to container network, topic/bootstrap setting, broker health, consumer lag and offset. |
| Jobs stay `ACCEPTED` (immediate) | Job and outbox rows; job version. | Publisher lease/retry/error state, Kafka connectivity, batch/poll process. Scheduled future `ACCEPTED` can be expected; inspect `schedule_at`. |
| Jobs stay `QUEUED` | Outbox published state and Kafka lag. | Worker process/group, partition assignment, dispatch version/state. |
| Jobs stay `RUNNING` | Execution owner/lease, attempt timestamps and result existence. | Worker crash/timeout, provider duration, stale-lease recovery cadence, worker logs. |
| Repeated retries | Failure kind, attempt count, `retry_at`, provider metadata. | Rate limit/quota, provider status, timeout budget, deterministic backoff, misclassified failure. |
| Provider timeout | Attempt error class and configured timeout. | External latency/availability, worker connectivity, per-job timeout, avoid exposing prompt or secret. |
| Frontend cannot reach API | Browser network panel and API base URL. | `NEXT_PUBLIC_API_BASE_URL`, allowed origin/CORS, credentials, TLS/mixed content, API readiness. |

These are diagnostic starting points, not claims that every failure produces a
single distinctive metric. Local logs and row state remain important because
metrics are process-local.

# Chapter 15 — Testing and Quality Engineering

## Test architecture

Backend tests use `pytest`, async fixtures, an isolated SQLite database,
dependency overrides and fake provider/dispatch/Redis boundaries. The suite
covers state transitions, idempotency, auth/ownership, job API, cancellation,
outbox behavior, retry classification, providers, metrics, scheduling,
admin, pagination and onboarding. This makes domain and API paths
deterministic; SQLite does not implement PostgreSQL's `SKIP LOCKED` semantics.

Frontend tests use Vitest, Testing Library and jsdom. They cover the API
client, token/refresh behavior, validation, routes/components, job detail,
pagination, cancellation, admin behavior, demo/read-only labelling and safe
navigation. Separate ESLint, TypeScript and production build checks validate
static and packaging properties.

Compose includes a local PostgreSQL/Kafka/Redis path. The observed smoke check
used a stack that was already running, not a fresh rebuild with all current
working-tree changes. It exercised mock success, retry exhaustion and a due
scheduled job through the infrastructure path. It did not verify broker
rebalance, PostgreSQL lock races, multi-process recovery or production
availability. OpenAI-compatible HTTP behavior is tested with mock transport;
no live credential was used.

## Observed verification (2026-10-07 workspace)

`docs/TESTING.md` records the most recent observed results for this workspace:

- Backend `pytest tests -q`: **150 passed**, with 1,144
  `pytest-asyncio` deprecation warnings.
- Ruff lint, Ruff format check (82 files), and mypy (57 source files): passed.
- Frontend Vitest: **32 passed**; ESLint, TypeScript `--noEmit`, and
  production build: passed.
- `docker compose config --quiet` and `git diff --check`: passed.
- The current uncommitted GitHub Actions workflow has not had a hosted
  workflow run observed.

The selected local Python environment reported Python 3.14.3, Windows; these
results do not establish every supported Python version. Check the present
`docs/TESTING.md` and rerun commands before using these numbers in a future
interview. Counts are snapshot evidence, not a permanent promise.

## Testing gaps and strategy

Before production claims, add real PostgreSQL concurrency tests for row
locking/leases and scheduler races; Kafka restart/rebalance/redelivery tests;
cross-process Redis limiter tests; subprocess shutdown/recovery tests; and
provider contract tests with a controlled fake HTTP server. Add property/
state-machine tests for legal transitions and fault injection at each
commit/ack boundary. Run load tests with reproducible environment, workload,
percentiles and resource metrics before making performance claims.
