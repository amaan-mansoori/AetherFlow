# ADR-0012: Transactional Outbox for Durable Dispatch

**Status:** Accepted  
**Date:** 2026-10-01

## Decision

Create one `outbox_dispatches` row in the same PostgreSQL transaction as a new
job and its idempotency record. Store immutable dispatch fields: job ID,
submission-time job version, schema version, and enqueue timestamp. Store
publication timestamp, attempt count, last error, and a short lease as mutable
publisher metadata.

An independent `OutboxPublisher` leases rows, publishes through
`JobDispatcher` outside the database transaction, then marks the row published
in a separate transaction. PostgreSQL publishers use `SKIP LOCKED` semantics;
SQLite tests cover portable behavior only.

## Rationale

The outbox closes the job-commit/Kafka-publication loss window without a
distributed transaction. Immutable fields prevent later job changes from
altering the original dispatch intent. Leases permit recovery after a
publisher crash.

## Consequences

Kafka publication is at least once. A crash after publication and before
finalization can produce a duplicate; the existing job version, state machine,
and CAS protections handle duplicate dispatch eligibility. The outbox is not
an execution deduplication mechanism, and retries/backoff/DLQ policy remain
future work.
