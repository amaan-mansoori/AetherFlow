# ADR-0013: Bounded Dispatch Runtime and Worker Crash Recovery

**Status:** Accepted  
**Date:** 2026-10-01

## Decision

Run outbox publication in an independent `OutboxPublisherRuntime` with
configurable polling and bounded batches. Preserve the short
claim-commit-publish-finalize sequence. Classify publication failures,
persist bounded retry metadata, and use deterministic capped exponential
backoff. Invalid dispatch data becomes a retained `PERMANENT_FAILURE` row
instead of being retried indefinitely.

Workers persist an execution owner and expiry lease while invoking an
executor. A restarted worker does not steal an active lease. After expiry it
recovers a `RUNNING` job to `FAILED`, or to `SUCCEEDED` if a durable result is
already present.

## Rationale

The publisher must be independently restartable and must not tie API request
lifetime to Kafka availability. Persisted retry scheduling avoids in-memory
retry state and makes failure behavior inspectable. The execution lease closes
the committed-running crash window without introducing an unsafe in-memory
deduplication cache.

## Consequences

Dispatch remains at least once: Kafka success before publication finalization
can produce a duplicate. Worker crash recovery records an explicit outcome; it
does not resume an interrupted provider call or provide exactly-once execution.
Execution retry orchestration, DLQ infrastructure, scheduler coordination, and
operator replay remain deferred.
