# Phase 4D/4E/4F — Dispatch and Worker Reliability

## Starting checkpoint

`0153398` — `feat: add transactional outbox for durable dispatch`.

## Implemented

### Phase 4D

- Added an independent `OutboxPublisherRuntime`.
- Added configurable polling interval, bounded batch size, lease duration,
  publisher identity, and graceful shutdown.
- Added executable module entrypoint
  `aetherflow.runtime.outbox_publisher`.
- Preserved claim/commit, publish outside the transaction, and finalization
  boundaries.

### Phase 4E

- Added typed transient/permanent dispatch failures.
- Added persisted publication state, failure category, bounded error text,
  failure timestamp, attempt count, next-attempt timestamp, and retry index.
- Added deterministic capped exponential backoff and terminal permanent failure.

### Phase 4F

- Added execution owner and expiry lease fields to jobs.
- Added the dispatch version marker for execution leases so an unrelated stale
  message cannot trigger recovery of a newer execution.
- Added active-lease protection and expired-lease restart recovery.
- A recovered running job becomes `FAILED`, or `SUCCEEDED` when a durable
  result already exists.
- Existing state-machine, CAS, duplicate-delivery, cancellation, attempt, and
  result semantics remain authoritative.

## Intentional deferrals

No scheduler, DLQ, Redis, provider integration, frontend, Kubernetes,
distributed transaction, or exactly-once execution was added. Durable
execution retry orchestration remains deferred because it requires a separate
retry-dispatch design rather than an in-memory sleep.

## Verification

Deterministic tests cover runtime lifecycle, bounded batches, failure
classification, retry backoff/cutoff, malformed records, lease recovery,
duplicate delivery, stale messages, cancellation, and worker crash recovery.
SQLite migration lifecycle and static checks are run locally. PostgreSQL and
Kafka availability must be reported separately; fake clients do not constitute
broker verification.

Final local verification:

- `pytest backend/tests -q`: 86 passed, 622 warnings.
- `ruff format --check .`: passed.
- `ruff check .`: passed.
- `mypy backend/src`: passed.
- `git diff --check`: passed.
- Fresh SQLite `upgrade -> downgrade -> upgrade`: passed.
- PostgreSQL unavailable; PostgreSQL locking and concurrency semantics remain
  unverified.
- Kafka unavailable; real broker publication, acknowledgement, and restart
  behavior remain unverified.

The combined 4D/4E/4F milestone is complete for the implemented local,
deterministic scope. Production PostgreSQL/Kafka verification and durable
execution retry orchestration remain intentionally outside this milestone.
