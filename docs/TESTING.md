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
