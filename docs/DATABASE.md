# Database Specification

**Status:** Reflects the current SQLAlchemy models and Alembic migrations
**Authority:** PostgreSQL is the source of truth.

## Entities

| Entity | Purpose | Important fields and constraints |
|---|---|---|
| users | Identity | id, email (unique), password hash, status, timestamps |
| roles | Role catalog | stable code (`USER`, `ADMIN`, `DEMO`) |
| user_roles | Assignment | unique user/role pair, foreign keys |
| api_keys | Programmatic auth | id, user_id, prefix, secure hash, name, last_used_at, revoked_at; never raw secret |
| jobs | Durable work state | id, user_id, type, model, normalized input/config, priority, timeout, retry policy, optional UTC schedule_at, state, version, timestamps |
| job_attempts | Execution history | job_id, attempt number unique pair, worker_id, provider/model, timestamps, error class, retry decision, usage, trace ID |
| job_results | Validated output | job_id unique, schema version, output, usage, created_at |
| job_events | Append-only lifecycle history | job_id, event type, prior/next state, actor, payload, timestamp |
| audit_logs | Security/admin actions | actor, action, target, outcome, redacted metadata, timestamp |
| idempotency_records | Submission deduplication | principal_id + key unique, fingerprint, job_id, response status, timestamps |
| outbox_dispatches | Durable dispatch intent | unique job/version pair, schema/enqueue data, publication state, future eligibility, lease and bounded failure metadata |

The versioned migrations create identity/session/API-key/audit tables, durable
job and idempotency tables, execution attempts/results/events, and
`outbox_dispatches`. Migration `0005_execution_retry` adds durable retry
eligibility; `0006_durable_scheduling` adds nullable `jobs.schedule_at` and the
due-job index; `0007_demo_role` adds `DEMO`. `0001_identity_access` seeds
`USER` and `ADMIN`. Provider credentials are runtime settings and are never
stored in job configuration. Refresh tokens are stored as SHA-256 hashes.
API-key secrets are hashed; the public key identifier is stored for lookup.

## Relationships and lifecycle

Users own jobs, API keys, and refresh sessions. Jobs own attempts, events, and
at most one result. Attempts record a worker identifier as text; there is no
persisted worker registry or heartbeat table. Audit records are append-only.
Deletion/retention policy is an open operational decision; no destructive
cascade may silently remove audit history.

## Constraints and indexes

Required uniqueness includes user email, API-key hash or identifier,
idempotency principal/key, job/attempt number, job result/job, and outbox
job/version. Indexes support user job listing by creation time, due scheduling,
attempts by job, events by job/time, and audit time/actor. Additional indexes
require measured query evidence.

Identity-specific indexes are email, role name, refresh token hash, refresh family and expiry, API-key public ID and active-user lookup, and audit event/actor/request/time. No plaintext credential is persisted.

## Concurrency

State transitions use `UPDATE ... WHERE id = ? AND state = expected AND version = expected`, incrementing version and checking affected rows. Outbox publishers use short lease claims and PostgreSQL `SKIP LOCKED` when multiple publishers are deployed. Retry eligibility is indexed by publication state, future availability, next-attempt timestamp, and creation order. Execution retry intent creation and the `RETRY_SCHEDULED` transition commit atomically. Execution leases are only recoverable after expiry and are cleared by worker decisions. Idempotency insertion relies on the unique constraint; a conflict reloads and compares the fingerprint. Attempt insertion requires `RUNNING`; result insertion is unique by job and occurs only from `RUNNING` or `CANCEL_REQUESTED`. SQLite does not prove PostgreSQL row-lock behavior.

Future initial schedules are activated by short PostgreSQL transactions using
`FOR UPDATE SKIP LOCKED` where supported. Activation performs the
`ACCEPTED -> QUEUED` versioned update, lifecycle event, and outbox insert in
one transaction. SQLite tests do not prove PostgreSQL lock behavior.

Production startup uses an explicit Alembic migration step before application
processes. API replicas do not run migrations automatically. PostgreSQL pools
use bounded size, overflow, pre-ping, and connection recycling settings from
environment configuration.

## Migration policy

All schema changes are versioned migrations. Application startup must not silently mutate schema. Migration execution and rollback limitations are documented with deployment procedures.

Phase 2 migration `0001_identity_access` upgrades a clean database with identity tables and role seed data and downgrades by removing that identity schema. Production migration execution remains an explicit deployment step.
