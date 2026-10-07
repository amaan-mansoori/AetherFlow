# Testing Strategy

**Status:** Current test strategy and latest verified checks

## Layers

- **Unit:** state machine, fingerprinting, retry classification/backoff, schema validation, authorization policies, provider adapters with fakes.
- **Component/integration-style:** SQLite/Alembic, injected Kafka/Redis/provider fakes, API and worker lifecycle behavior.
- **API/contract:** OpenAPI schemas, status codes, error envelope, auth/API-key behavior, idempotency replay and conflict handling.
- **Manual local smoke:** Compose-backed API, PostgreSQL, Kafka, publisher, scheduler, worker, and mock provider. This is separate from the automated SQLite/fake-based suite.
- **Load/performance:** no reproducible benchmark harness is currently reported; do not infer throughput or latency from functional tests.
- **Security:** negative authorization, ownership-isolation, and secret-redaction tests; automated dependency/container scanning is not configured here.

## Mandatory scenarios

Important targets include duplicate submission, concurrent idempotency races,
duplicate Kafka messages, worker crash/restart, provider timeout/429/5xx,
malformed output, broker/Redis/database outage, retry exhaustion, poison
messages, cancellation before/during a provider call, and unauthorized access.
These are target scenarios, not a claim that every infrastructure variant is
automated in the current suite.

The checked-in pull-request workflow uses the deterministic mock provider and
the isolated test suite; it does not start external services. External
provider tests are opt-in and are not required for ordinary pull requests.
Tests should assert observable outcomes rather than implementation details.

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

The suite remains deterministic validation; it does not substitute for
infrastructure checks. A local Compose smoke check in this workspace observed
API readiness, mock-provider success, retry exhaustion, and a due scheduled
job reaching a persisted result through PostgreSQL/Kafka/publisher/scheduler/
worker. The running stack was already present and was not rebuilt for the
current source changes. PostgreSQL lock races, broker restart/rebalance,
multi-process concurrency, and shutdown recovery remain unverified. No
external provider credential was used.

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

## Latest workspace verification

The following checks were run for the current working tree:

- Backend `pytest tests -q`: **150 passed**. The run emitted 1,144
  `pytest-asyncio` deprecation warnings concerning event-loop policy APIs.
- Full backend Ruff lint: passed.
- Full backend mypy: **57 source files passed**.
- Full backend `ruff format --check .`: passed for all 82 files.
- Frontend Vitest: **32 tests passed**; ESLint, TypeScript, and production
  build passed.
- `docker compose config --quiet`: passed without printing resolved
  environment values.
- `git diff --check`: passed.
- GitHub Actions workflow syntax and hosted execution have not been verified
  by a GitHub run for this uncommitted change.

The future-schedule cancellation regression is covered by the SQLite/API
service test and a frontend confirmation test. That behavior has not been
retested against a freshly rebuilt Compose stack. Live provider calls,
PostgreSQL locking/concurrency, and restart/rebalance behavior remain
unverified.
