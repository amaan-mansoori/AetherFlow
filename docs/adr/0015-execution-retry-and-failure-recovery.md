# ADR-0015: Durable Execution Retry and Failure Recovery

**Status:** Accepted
**Date:** 2026-10-02

## Decision

Use a centralized deterministic `ExecutionRetryPolicy` for provider execution
failures. Retry only rate limits, timeouts, transient provider failures, and
unexpected internal failures. Validation, authentication, permanent-provider,
cancellation, and legacy execution failures are terminal. The persisted
per-job retry policy supplies a bounded attempt budget and capped exponential
backoff; jitter is not applied.

On a retryable failure, the worker atomically records bounded attempt failure
metadata, clears the execution lease, transitions `RUNNING` to
`RETRY_SCHEDULED`, and inserts a versioned future-dated `outbox_dispatches`
intent. The existing outbox publisher claims the intent when due and when the
job state/version still match. The worker processes the resulting message
through `RETRY_SCHEDULED -> QUEUED -> RUNNING`.

## Rationale

Execution retry must survive process restart and must not bypass the existing
state machine or Kafka acknowledgement boundary. Reusing the outbox publisher
avoids Redis, a general scheduler, direct worker-to-Kafka publication, and a
second competing retry source of truth.

## Consequences

The outbox schema now permits multiple versioned intents per job and stores
`available_at` for future retry publication. Cancellation and stale version
checks prevent scheduled retries from resurrecting jobs. Publication and
execution remain at least once; a provider may receive duplicate work. SQLite
tests provide deterministic behavioral coverage but do not prove PostgreSQL
row-locking or Kafka broker semantics. Execution retry does not resume a
provider call interrupted by a worker crash.
