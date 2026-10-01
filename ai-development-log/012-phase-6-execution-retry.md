# Phase 6 — Execution Retry and Failure Recovery

## Problem

Phase 5 classified provider failures but treated every execution failure as
terminal. The platform therefore lacked bounded, restart-safe execution retry
while already having `RETRY_SCHEDULED` state and a durable transactional
outbox.

## Scope decision

Implemented:

- centralized deterministic execution retry policy;
- explicit retryability for the Phase 5 failure taxonomy;
- bounded capped exponential backoff using each job's persisted retry policy;
- atomic failure metadata, lease cleanup, state transition, and retry intent;
- future-dated retry dispatch through the existing outbox publisher;
- cancellation, stale-version, duplicate-publication, and retry-exhaustion safety;
- deterministic clock injection for worker retry timing.

Deferred:

- Redis or a general scheduler;
- execution retry API/operator replay;
- external providers and real credentials;
- provider-call resumption after worker crash;
- exactly-once execution, DLQ redesign, and arbitrary user retry policies.

## Architecture before Phase 6

Phase 4 provided dispatch publication retry and Phase 4F worker lease recovery.
Phase 5 provided the provider boundary and failure taxonomy. Execution failures
still transitioned directly from `RUNNING` to `FAILED`.

## Implementation

`ExecutionRetryPolicy` classifies `RATE_LIMIT`, `TIMEOUT`,
`TRANSIENT_PROVIDER` as retryable. Validation, authentication,
permanent-provider, cancellation, unexpected internal, and legacy execution
failures are terminal. The worker invokes `finalize_execution_failure`, which
updates the attempt, clears the lease, applies the CAS-protected state
transition, appends an event, and creates a versioned outbox intent in one
transaction.

The outbox now stores `available_at` and permits one intent per
`(job_id, job_version)`. Its existing publisher is the durable retry
dispatcher. It publishes only due intents whose job state and version match,
so cancellation and stale retry messages cannot resurrect a job.

## Attempt and failure semantics

An attempt is created only after a worker successfully claims `RUNNING`.
Duplicate Kafka delivery is not a new attempt. A failed attempt records its
bounded category, message, provider, and `RETRY` or `TERMINAL` decision.
Successful retry creates the next numbered attempt and the single durable job
result. Retry exhaustion records the final failed attempt and transitions to
`FAILED`.

## Verification

Added deterministic tests for policy classification/backoff, retry scheduling,
future eligibility, second-attempt numbering, permanent failures, exhaustion,
cancellation before publication, duplicate retry delivery, and stale state.
Full-suite and static verification results are recorded in the final report.
Local tests use SQLite/local dispatch; PostgreSQL and Kafka remain unavailable
for integration verification.

## Limitations

The architecture remains at-least-once. A provider call can occur more than
once, and a worker crash after provider-side work but before durable failure
finalization is recovered as a terminal lease outcome rather than resumed.
