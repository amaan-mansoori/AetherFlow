# Phase 4C — Transactional Outbox

## Starting checkpoint

`f09d6c5` — `feat: add Kafka-backed asynchronous dispatch`.

## Objective

Close the PostgreSQL job-creation to Kafka-publication reliability gap by
persisting an immutable dispatch intent in the same transaction as submission.

## Schema and transaction design

`outbox_dispatches` has one unique row per job, immutable dispatch fields
(`job_id`, `job_version`, `schema_version`, `enqueued_at`, `created_at`) and
publication metadata (`published_at`, `attempt_count`, `last_error`,
`lease_owner`, `lease_until`). An index on `(published_at, created_at)` supports
oldest-unpublished scans.

The API now only commits the job, idempotency record, lifecycle event, and
outbox row. It never waits for Kafka. The outbox publisher claims a row in a
short transaction, publishes outside the transaction, and finalizes it in a
new transaction.

## Recovery and crash windows

Failed publication clears the lease and retains error metadata. Lease expiry
recovers a publisher crash. A crash after Kafka success and before finalization
can produce duplicate publication; existing worker version/state/CAS behavior
handles the duplicate. No exactly-once claim is made.

## Tests and verification

`test_outbox.py` covers atomic submission, rollback, idempotent replay,
immutable fields, successful publication, failure recovery, skipping published
rows, and multi-record publication. SQLite validates portable behavior only;
PostgreSQL locking and Kafka broker behavior remain unverified.

## Deferred work

Redis, scheduler, execution retries/backoff, DLQ, providers, production worker
runtime deployment, observability, Kubernetes, frontend, and cloud deployment.
