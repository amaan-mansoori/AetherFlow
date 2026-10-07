# API Contract

**Status:** Implemented contract
**Versioning:** `/api/v1`; additive changes are preferred, breaking changes require a new version.

## Authentication

- `POST /api/v1/auth/register`
- `GET /api/v1/auth/demo`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`

`POST /api/v1/auth/register` accepts `{ "email": "...", "password": "..." }` and returns a safe user object with `201`. Email is normalized to lowercase; passwords must contain 12–128 characters and not be blank. Registration always assigns `USER`; role, permission, admin, and owner fields are rejected. Registration does not create a session. Invalid input returns the established validation error; a duplicate address returns `409 CONFLICT`. The reserved demo email cannot be registered publicly. Email verification and password recovery are not implemented.

`POST /api/v1/auth/login` accepts the same credentials and returns a short-lived bearer access token plus safe user data. It also sets a rotating opaque refresh credential in an `HttpOnly` cookie. Invalid credentials return the same `401 AUTHENTICATION_REQUIRED` response for existing and nonexistent accounts. Login, refresh, and logout reject a supplied browser `Origin` that is not in the configured CORS origin allowlist; non-browser clients may omit Origin.

`POST /api/v1/auth/refresh` reads only the refresh cookie, rotates it, revokes the used credential, and returns a new access token. Reuse of a rotated token revokes its session family and returns `401`. `POST /api/v1/auth/logout` revokes the presented refresh session family and clears the cookie; newly issued family-bound bearer tokens are rejected immediately. Tokens issued before session-family binding remain compatible until their short expiration. The cookie uses `HttpOnly`, `SameSite=Strict`, a path limited to `/api/v1/auth`, and environment-configured `Secure`/domain values. HTTPS deployments must enable secure cookies; production settings enforce this.

`GET /api/v1/auth/me` requires `Authorization: Bearer <access-token>` and returns only ID, email, roles, and safe timestamps. Access tokens contain only subject, roles, issue/expiry times, and token type.

`GET /api/v1/auth/demo` is unauthenticated and returns `{ "available": boolean, "access_mode": "read-only" }`. Availability requires both `AETHERFLOW_DEMO_ENABLED=true` and an active user with the reserved DEMO identity and exact DEMO role. It does not return credentials. The identity is created only by the trusted `aetherflow.commands.provision_demo` command with an operator-supplied `AETHERFLOW_DEMO_PASSWORD`.

New bearer tokens additionally carry a session-family identifier; logout
revokes that family. Authorization resolves current roles from the database,
not from token role claims. Tokens issued before this binding remain valid only
until their normal short expiration.

## API keys

- `POST /api/v1/api-keys`
- `GET /api/v1/api-keys`
- `DELETE /api/v1/api-keys/{key_id}`

`POST /api/v1/api-keys` requires a bearer access token and accepts `{ "name": "..." }`. It returns metadata plus the complete secret exactly once. `GET /api/v1/api-keys` lists metadata only. `DELETE /api/v1/api-keys/{key_id}` revokes a key and is idempotent for an owned key.

Keys use `afk_<public-id>_<secret>`. The public ID is indexed for lookup; only a SHA-256 digest of the high-entropy secret is stored. Programmatic authentication uses `X-API-Key`; revoked, malformed, or invalid keys return `401`. A request containing both `Authorization` and `X-API-Key` is rejected as ambiguous.

## Jobs

- `POST /api/v1/jobs`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/jobs/{job_id}/attempts`
- `GET /api/v1/jobs/{job_id}/events`
- `POST /api/v1/jobs/{job_id}/cancel`

The events and attempts endpoints accept optional `limit` (1–100) and
non-negative `offset` query parameters for bounded console history pages.
When omitted, the existing full per-job response behavior is preserved.

Submission body contains `type`, `model`, `input`, `configuration`, `priority`,
`timeout_seconds`, `retry_policy`, `metadata`, optional timezone-aware
`schedule_at`, and the `Idempotency-Key` header. Responses include job ID,
state, `schedule_at`, timestamps, and identifiers for later inspection.

`schedule_at` is normalized to UTC and must include an explicit timezone. A
future value creates durable `ACCEPTED` work without an outbox dispatch until
the timestamp is due. A value at or before the current UTC time is immediately
outbox-eligible. The scheduler is internal; there is no public scheduler
endpoint. Reusing an idempotency key with a different schedule is a conflict.
Cancelling a scheduled job while it remains `ACCEPTED` moves it directly to
terminal `CANCELLED` because it has not been claimed for execution; a pending
dispatch message is treated as stale by the worker. Repeated cancellation is
idempotent. Immediate submissions and jobs that have moved beyond `ACCEPTED`
use `CANCEL_REQUESTED` and are finalized by the worker when possible.

The first workload is a bounded structured inference operation: a typed input object is submitted with an explicit output schema/version selected by `job_type`. The provider adapter is selected by the runtime-configured provider registry and returns normalized text/structured content and usage metadata; the domain validates the content against the job type's schema before creating `job_results`. Provider credentials are not accepted in job configuration. Arbitrary tools, URLs, code, shell commands, and autonomous planning are not part of this contract.

## Health

- `GET /health/live`
- `GET /health/ready`
- `GET /metrics` returns unauthenticated Prometheus-compatible application metrics.

In the Compose deployment, API readiness represents PostgreSQL availability.
Kafka readiness is enforced for the worker and outbox publisher process
startup, not by API liveness.

## Administrative operations

Phase 13 adds an explicit `ADMIN`-only control plane:

- `GET /api/v1/admin/jobs` supports bounded filtering by job/user ID, state,
  type, model, provider, priority, created/scheduled ranges, and offset
  pagination. Ordering is stable by `created_at DESC, id DESC`.
- `GET /api/v1/admin/jobs/{job_id}` returns bounded attempts, lifecycle
  events, and durable outbox publication metadata.
- `POST /api/v1/admin/jobs/{job_id}/cancel` uses the existing versioned CAS
  cancellation primitive and writes an audit event.

Administrative responses omit job input and configuration, redact sensitive
operational values, and cap child collections at 100 records. There is no
admin retry/requeue route: the current state machine has no safe manual retry
transition, so execution retry remains worker-owned and durable.

## Implementation status

Implemented capabilities include registration and session access, durable
idempotent jobs, explicit versioned state transitions, attempts/results/events,
cancellation, provider-independent worker execution, Kafka transport,
transactional outbox publication, bounded dispatch retry, independent publisher
runtime, worker execution-lease recovery, provider abstraction, execution
retry, Redis-backed rate limiting, durable scheduling, administrative
operations, the Next.js console, and restricted demo provisioning. The
frontend uses the documented API contracts and does not add backend
capabilities.

The worker may select the configured `openai` provider, but provider
credentials are runtime environment settings and cannot be supplied through
the job API.

The DEMO role may read only its own job records and is denied job submission,
job cancellation, API-key creation/revocation, and all administrative routes.
The seeded future-scheduled and cancellation-requested examples have no outbox
dispatch intent and are not evidence of worker or provider execution. Redis
rate limiting is optional outside Compose and intentionally fails open if
Redis is unavailable.

## Contract rules

All request and response schemas are explicit, JSON timestamps are UTC ISO-8601, pagination is cursor- or bounded-page based, and unknown fields are rejected or handled consistently. OpenAPI generated by FastAPI is the primary machine-readable contract; checked-in examples and contract tests must remain aligned.
