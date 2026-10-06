# Testing Strategy

**Status:** Implementation and deterministic verification through Phase 15

## Layers

- **Unit:** state machine, fingerprinting, retry classification/backoff, schema validation, authorization policies, provider adapters with fakes.
- **Integration:** PostgreSQL migrations/repositories, Kafka publish/consume, Redis limits/cache, worker lifecycle.
- **API/contract:** OpenAPI schemas, status codes, error envelope, auth/API-key behavior, idempotency concurrency.
- **End-to-end:** login -> submit -> worker -> result -> polling -> cancellation/retry using Compose.
- **Load/performance:** controlled mock-provider workloads measuring throughput and percentile latency.
- **Security:** dependency/container scans, negative authorization tests, secret/log redaction, injection payloads.

## Mandatory scenarios

Duplicate submission, concurrent idempotency race, duplicate Kafka message, worker crash/restart, provider timeout/429/5xx, malformed output, broker/Redis/database outage, retry exhaustion, poison message, cancellation before and during provider call, and unauthorized access.

CI uses the deterministic mock provider and isolated disposable dependencies. External provider tests are opt-in and never required for ordinary pull requests. Tests must assert observable outcomes rather than implementation details.

## Phase 1 foundation coverage

The initial test harness uses an in-memory SQLite database through the async SQLAlchemy interface, so unit/API tests do not require production PostgreSQL. It covers application startup, liveness, database-backed readiness, request-ID generation/propagation/rejection, error envelopes, configuration validation, and session lifecycle. PostgreSQL migration and connectivity checks remain separate integration verification and are run when a PostgreSQL environment is available.

## Phase 2 identity coverage

Identity tests cover normalized registration, validation, duplicate email, generic login failures, Argon2-backed login, safe current-user responses, JWT claims, refresh rotation and reuse rejection, logout, API-key high entropy/one-time display/list/revocation/rejection, ambiguous authentication, and reusable admin denial behavior. Migration verification covers clean upgrade and downgrade. Tests use seeded in-memory schema and never call external services.

## Phase 3 durable job-domain coverage

Job-domain tests cover schema validation, legal and illegal state transitions, terminal-state protection, versioned compare-and-set rejection for stale transitions, idempotent replay and payload mismatch, principal scoping, ownership/admin visibility, cancellation requests and lifecycle events, attempt/result uniqueness, and rejection of attempt/result writes outside execution-eligible states. No true concurrent idempotency test is present yet. PostgreSQL concurrency remains an integration check; SQLite tests do not establish PostgreSQL locking behavior.

## Phase 4A execution-foundation coverage

`backend/tests/test_phase4a.py` covers the provider-independent execution
contract, local dispatcher round trips and failures, worker success, controlled
and unexpected execution failures, cancellation before execution, attempt/result
persistence, terminal/ineligible dispatches, and stale-version rejection. These
tests are deterministic and do not require Kafka or Redis. They do not prove
PostgreSQL locking, durable broker delivery, or exactly-once execution.

## Phase 4B Kafka transport coverage

`backend/tests/test_kafka.py` uses fake producer and consumer clients to verify
deterministic envelope serialization, schema/version and field validation,
job-ID message keys, producer failure propagation, valid receive, explicit
offset acknowledgement, and malformed-message non-acknowledgement. No test
requires a Kafka broker. The suite therefore validates adapter behavior but not
broker connectivity, partition rebalancing, or production delivery.

The application lifecycle intentionally creates only a producer when Kafka is
enabled. A worker runtime must create the consumer dispatcher and
`KafkaWorkerRunner`; no Kafka consumer is started in each API replica.

## Phase 4C transactional outbox coverage

`backend/tests/test_outbox.py` verifies the atomic job/outbox submission
invariant, rollback behavior, idempotent replay, immutable dispatch fields,
successful publication/finalization, publication failure recovery metadata,
published-record skipping, and bounded multi-record publication. These tests
use SQLite for deterministic portable behavior and do not prove PostgreSQL
`SKIP LOCKED` concurrency.

## Phase 4D/4E/4F reliability coverage

Reliability tests cover bounded publisher runtime start/stop and resource
closure, retry attempt scheduling and terminal cutoff, deterministic backoff,
permanent malformed records, lease recovery, and worker recovery of expired
execution leases. Tests use injected time where retry timing matters. They do
not claim SQLite proves PostgreSQL locking or Kafka broker behavior.

## Phase 5 provider coverage

Provider tests cover registry resolution, unsupported providers/models,
deterministic mock success, normalized failure categories and output
validation, worker result and attempt persistence, timeout durability, and
rejection of provider credentials in job configuration. Provider tests use no
external credentials or network; they do not verify an external provider.

## Phase 9 real provider adapter coverage

The OpenAI-compatible adapter is tested with `httpx.MockTransport`; tests cover
normalized output and usage, authentication, rate limits, timeout, 5xx,
permanent 4xx, malformed responses, allowlisted configuration, and secret
non-leakage. Tests do not require network access or provider credentials.

## Phase 6 execution retry coverage

Phase 6 tests cover deterministic retry classification and capped backoff,
retryable failure persistence, atomic retry intent creation, second-attempt
numbering, permanent failure, retry exhaustion, future eligibility,
cancellation before publication, duplicate retry delivery, and stale-state
protection. SQLite and local dispatch provide deterministic behavior but do
not prove PostgreSQL `FOR UPDATE SKIP LOCKED` or Kafka consumer concurrency.

## Phase 7 observability coverage

Tests verify Prometheus exposition, HTTP status classes and normalized routes,
bounded metric labels, and distinct liveness/readiness behavior. They do not
claim external Prometheus scraping or infrastructure-level telemetry.

## Phase 10 production-like validation

The complete pytest suite and static checks are deterministic validation.
Compose-based PostgreSQL, Kafka, outbox, worker, shutdown, concurrency, and
API-to-result E2E checks are run only when Docker is available; they are not
substituted with SQLite or fake clients. Docker's Linux engine was unavailable
in the current environment, so these checks are **UNVERIFIED**. Real-provider
smoke testing is also **UNVERIFIED** because no credential was supplied.

## Phase 11 Redis coverage

Deterministic tests inject a fake async Redis boundary and verify the atomic
fixed-window result contract, bounded TTL inputs, class separation, safe
public-ID key construction, 429 and `Retry-After` behavior, and fail-open
operation during Redis timeout. They do not claim a real Redis server or
cross-process behavior. Real Redis integration remains opt-in and separate
from the ordinary suite.

## Phase 12 scheduling coverage

`backend/tests/test_phase12_scheduling.py` verifies timezone validation and
UTC normalization, future/past submission behavior, due activation, bounded
duplicate polling, cancellation protection, and idempotency conflicts that
include scheduling metadata. These SQLite tests validate deterministic domain
behavior only; PostgreSQL `SKIP LOCKED`, process restart, Kafka delivery, and
multi-process scheduling remain infrastructure checks.

## Phase 13 administrative coverage

`backend/tests/test_phase13_admin.py` verifies unauthenticated and `USER`
denial, bounded admin listing and filtering, redacted detail responses,
cancellation through the existing state machine, terminal-state protection,
and safe audit actor and target metadata. Manual retry/requeue is intentionally
tested as an absent capability rather than introducing an unsafe transition.
SQLite still does not prove PostgreSQL row-locking or live Kafka/outbox
behavior.

Phase 14 adds `backend/tests/test_phase14_api_pagination.py` to verify that
optional user job-event and attempt pagination returns stable bounded pages
while requests without pagination retain the existing response behavior.

Phase 15 authentication and onboarding coverage extends `backend/tests/test_auth.py`
with privilege/owner-field injection rejection, Origin checks on cookie-auth
routes, immediate invalidation of family-bound access tokens after logout,
opt-in and idempotent demo provisioning, refusal to overwrite an unrelated
identity, safe read-only demo access, private-job isolation, and trusted admin
promotion. Tests use the isolated in-memory SQLite app fixture and do not
connect to external services. The `DEMO` schema migration is checked separately
against clean and pre-existing SQLite databases.

Frontend tests use Vitest and Testing Library for access-token memory storage,
refresh-cookie request behavior, refresh after 401, structured errors and
`Retry-After`, bounded API parameters, submission/idempotency, job filtering and
pagination, detail rendering, state labels, cancellation confirmation, admin
role/redaction behavior, command-palette keyboard navigation, registration
validation and signed-out success, demo availability/read-only labeling, and
safe post-login return destinations.

Phase 14 verification (historical): frontend lint, TypeScript, component tests,
and production build passed; 135 backend tests passed; Ruff passed; changed
backend modules passed mypy; full mypy reported two Redis typing errors in
`infrastructure/redis.py`. The Docker Linux engine was unavailable, so its live
Compose checks were **UNVERIFIED**. Browser checks exercised the earlier
operations console against disposable SQLite and validated console routes, not
worker or production integration.

Phase 15 acceptance verification (2026-10-04): all 149 backend tests passed;
Ruff format/check passed; mypy passed for the nine changed backend source
modules. Full `mypy backend/src` still reports the two existing errors in
`infrastructure/redis.py` (`_pool` annotation and `Redis.aclose`). All 31
frontend tests, ESLint, TypeScript, and the production build passed. Disposable
SQLite/Alembic verification passed upgrade to head, preservation of a
pre-existing user, guarded downgrade while DEMO is assigned, downgrade after
unassignment, and re-upgrade.

Browser verification against a disposable SQLite-backed API with Kafka, Redis,
and the scheduler disabled confirmed registration remains signed out, login,
refresh-cookie session restoration after reload, logout invalidation, protected
route redirect after logout, demo availability/read-only explanation, and the
DEMO account's own sample records. Registration and demo were checked at 375px
without horizontal overflow. PostgreSQL, Kafka, Redis, worker execution, and
full Compose integration were **UNVERIFIED** because Docker Desktop's Linux
engine was unavailable. No external provider credentials were supplied.
