# Data Flow

**Status:** Architecture / Specification Phase

## Submission

1. Client sends an authenticated request and idempotency key.
2. API authenticates, authorizes, validates schema, normalizes the payload, and computes a request fingerprint.
3. A transaction inserts or resolves the idempotency record and creates `ACCEPTED` job state.
4. API publishes a versioned `jobs.submit` message containing job ID, tenant/principal ID, attempt policy, and trace context.
5. Job becomes `QUEUED`; publication failures are recorded and surfaced for recovery.

## Execution

1. Worker consumes a message in a consumer group.
2. Worker starts a span, checks cancellation and terminal state, and claims the job using a compare-and-set transition to `RUNNING`.
3. Worker creates an attempt record.
4. Provider adapter applies timeout, provider error classification, and normalized response handling.
5. Pydantic validation accepts or rejects structured output.
6. A transaction persists result or failure, updates job state, and appends a job event.
7. Worker publishes a lifecycle message; duplicate lifecycle publication is acceptable because consumers must be idempotent.

## Read path

The console polls versioned API endpoints. API reads PostgreSQL for durable status and results, using Redis only for explicitly cacheable short-lived views. Cache invalidation follows job mutation events; stale reads are bounded by TTL and never override authoritative state.

## Trace propagation

Request ID and correlation ID enter at HTTP, are stored in job/attempt metadata where appropriate, and are propagated in Kafka headers. The conceptual span chain is HTTP -> persistence -> publish -> consume -> inference -> persistence.

