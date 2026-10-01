# Testing Strategy

**Status:** Architecture / Specification Phase

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
