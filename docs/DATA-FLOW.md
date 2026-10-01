# Data Flow

**Status:** Architecture / Specification Phase

## Submission

1. Client sends an authenticated request and idempotency key.
2. API authenticates, authorizes, validates schema, normalizes the payload, and computes a request fingerprint.
3. One database transaction inserts or resolves the idempotency record, creates
   `ACCEPTED` job state, and records an immutable outbox dispatch intent.
4. An independent outbox publisher reconstructs the versioned dispatch message
   and publishes it to Kafka after the transaction commits.
5. Publication failures remain recoverable in the outbox; the worker owns later
   execution-state transitions.

## Execution

1. Worker consumes a message in a consumer group.
2. Worker starts a span, checks cancellation and terminal state, and claims the job using a compare-and-set transition to `RUNNING`.
3. Worker creates an attempt record.
4. `ProviderExecutor` resolves a configured provider through the registry; the adapter applies provider error classification and normalized response handling.
5. The worker enforces the job timeout outside the database transaction.
6. Pydantic validation accepts or rejects structured output.
7. For retryable failure, one transaction persists bounded failure metadata,
   clears the lease, transitions `RUNNING -> RETRY_SCHEDULED`, and creates a
   future-dated outbox dispatch intent.
8. The outbox publisher later publishes the eligible retry intent; the worker
   advances it through `QUEUED -> RUNNING`. Permanent or exhausted failures
   transition to `FAILED`.
9. A transaction persists a successful result and lifecycle event. Duplicate
   lifecycle publication is acceptable because consumers must be idempotent.

## Read path

The console polls versioned API endpoints. API reads PostgreSQL for durable status and results, using Redis only for explicitly cacheable short-lived views. Cache invalidation follows job mutation events; stale reads are bounded by TTL and never override authoritative state.

## Trace propagation

Request ID and correlation ID enter at HTTP, are stored in job/attempt metadata where appropriate, and are propagated in Kafka headers. The conceptual span chain is HTTP -> persistence -> publish -> consume -> inference -> persistence.
