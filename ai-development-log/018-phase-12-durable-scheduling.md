# Phase 12 — Durable Scheduling and Orchestration Semantics

## Implementation

Added optional UTC `schedule_at` metadata to durable jobs and migration
`0006_durable_scheduling`. Future jobs remain `ACCEPTED` without an outbox
intent. Past and immediate jobs preserve the existing submission path.

Added `DurableScheduler` and `SchedulerRuntime`. Due activation uses a bounded
indexed PostgreSQL query and `FOR UPDATE SKIP LOCKED` where supported. The
existing CAS state machine, lifecycle event, and versioned outbox intent are
committed atomically. The scheduler has no Kafka or Redis dependency.

## Semantics

`schedule_at` must include a timezone and is normalized to UTC. A timestamp at
or before submission time is immediately eligible. Cancellation remains
authoritative through the existing state machine. Initial scheduling is not
execution retry: retries remain `RETRY_SCHEDULED` and are handled by the
existing outbox eligibility path.

## Verification

The Phase 12 deterministic suite covers schedule validation, future/past
submission, due activation, duplicate polling, cancellation protection, and
idempotency conflicts. SQLite does not prove PostgreSQL row locking,
multi-process scheduling, Kafka delivery, or restart behavior. Live Compose
verification remains environment-dependent when Docker is unavailable.
