# Phase 13 — Administrative Operations Control Plane

## Implementation

Added centralized ADMIN-only routes for bounded job inspection and a detailed
operational view containing redacted job metadata, attempts, lifecycle events,
and durable outbox publication metadata. Filters are typed and bounded, and
ordering is deterministic.

Added an ADMIN cancellation route that reuses the existing versioned CAS
`cancel_job` primitive. The mutation writes a safe audit event in the same
transaction, including server-derived actor, operation, target, outcome, and
request ID. No direct Kafka publication, Redis durability, or second retry
mechanism was introduced.

Manual admin retry/requeue is intentionally unsupported because it cannot be
expressed safely by the current authoritative state machine and durable retry
policy.

## Verification

The focused Phase 13 tests cover unauthenticated denial, USER denial, ADMIN
inspection, bounded pagination/filtering, redaction, terminal cancellation
behavior, CAS-backed cancellation, and audit metadata without secrets.
SQLite does not verify PostgreSQL row locking, Kafka publication, or live
Compose runtime behavior when the Docker Linux engine is unavailable.
