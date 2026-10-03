# ADR-0021: Durable One-Shot Scheduling

**Status:** Accepted  
**Date:** 2026-10-02

## Decision

Persist an optional timezone-aware UTC `jobs.schedule_at` value in PostgreSQL.
Immediate and past-due submissions use the existing initial outbox intent.
Future submissions remain `ACCEPTED` and create no dispatch intent until due.

An independent scheduler polls a bounded indexed query for due `ACCEPTED`
jobs. In one short PostgreSQL transaction it locks a row with
`FOR UPDATE SKIP LOCKED` where supported, applies the existing versioned
`ACCEPTED -> QUEUED` transition, records a lifecycle event, and inserts the
versioned `outbox_dispatches` row. The existing outbox publisher remains the
only Kafka publication path.

## Rationale

PostgreSQL remains the sole durable source of truth. The scheduler is a
recovery-safe polling process, not a timer registry or broker publisher.
Row locking, CAS predicates, and the unique `(job_id, job_version)` outbox
constraint protect concurrent scheduler instances. A crash before commit
rolls back activation; a crash after commit leaves a recoverable outbox
intent.

## Cancellation and retries

Cancellation of a future `ACCEPTED` job uses the existing CAS state machine and
changes it to `CANCEL_REQUESTED`; the scheduler only selects `ACCEPTED`, so it
cannot resurrect the job. Initial scheduling is distinct from execution retry:
retry intents remain `RETRY_SCHEDULED` with `available_at` and continue through
the existing outbox publisher.

## Consequences

Schedules survive API, scheduler, worker, Kafka, and Redis restarts because
the schedule and activation intent are durable. Publication and execution
remain at least once; no exactly-once claim is made. SQLite tests validate
portable deterministic behavior but do not prove PostgreSQL locking or
multi-process behavior. Recurring schedules and cron syntax remain out of
scope.
