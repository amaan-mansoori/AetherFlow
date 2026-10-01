# ADR-0011: Kafka Dispatch Envelope and Acknowledgement

**Status:** Accepted  
**Date:** 2026-10-01

## Decision

Use Kafka topic `aetherflow.jobs` with the job UUID as the message key and a
versioned JSON envelope named `aetherflow.job-dispatch.v1`. The envelope carries
`schema_version`, `job_id`, `job_version`, and timezone-aware `enqueued_at`.
Workers use the `aetherflow-workers` consumer group with auto-commit disabled.

The Kafka adapter remains behind `JobDispatcher`; the worker owns business
decisions and acknowledges only after a durable decision. Malformed or
unsupported messages are not acknowledged. Duplicate delivery is expected and
is handled by the existing job version, state machine, and CAS protections.

## Rationale

Job-key partitioning preserves ordering for a job without coupling domain code
to Kafka classes. Explicit acknowledgement avoids acknowledging work before
the worker has persisted its decision. `acks=all` and producer idempotence
improve publication behavior but do not provide exactly-once execution.

## Consequences

PostgreSQL and Kafka remain separate systems with no distributed transaction.
The API can return dispatch-unavailable after a durable job commit, leaving an
accepted job requiring future recovery. An outbox or recovery mechanism is
deferred until its operational requirements are defined.
