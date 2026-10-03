# Database Specification

**Status:** Architecture / Specification Phase  
**Authority:** PostgreSQL is the source of truth.

## Entities

| Entity | Purpose | Important fields and constraints |
|---|---|---|
| users | Identity | id, email (unique), password hash, status, timestamps |
| roles | Role catalog | stable code (`USER`, `ADMIN`) |
| user_roles | Assignment | unique user/role pair, foreign keys |
| api_keys | Programmatic auth | id, user_id, prefix, secure hash, name, last_used_at, revoked_at; never raw secret |
| jobs | Durable work state | id, user_id, type, model, normalized input/config, priority, timeout, retry policy, optional UTC schedule_at, state, version, timestamps |
| job_attempts | Execution history | job_id, attempt number unique pair, worker_id, provider/model, timestamps, error class, retry decision, usage, trace ID |
| job_results | Validated output | job_id unique, schema version, output, usage, created_at |
| job_events | Append-only lifecycle history | job_id, event type, prior/next state, actor, payload, timestamp |
| workers | Worker registry | id, process version, status, capabilities, last heartbeat |
| worker_heartbeats | Liveness history | worker_id, observed_at, load metadata |
| audit_logs | Security/admin actions | actor, action, target, outcome, redacted metadata, timestamp |
| idempotency_records | Submission deduplication | principal_id + key unique, fingerprint, job_id, response status, timestamps |
| outbox_dispatches | Durable dispatch intent | unique job/version pair, schema/enqueue data, publication state, future eligibility, lease and bounded failure metadata |

Phase 2 creates `users`, `roles`, `user_roles`, `refresh_sessions`, `api_keys`, and `audit_logs`. Phase 3 adds `jobs`, `idempotency_records`, `job_attempts`, `job_results`, and `job_events`. Phase 4C adds `outbox_dispatches`; Phase 4D/4E adds its publication state, retry schedule, classification, and timestamps. Phase 4F adds `jobs.execution_owner`, `jobs.execution_dispatch_version`, and `jobs.execution_lease_until` for restart recovery and stale-message protection. Phase 5 uses the existing job configuration and attempt provider/usage fields. Phase 6 migration `0005_execution_retry` adds `outbox_dispatches.available_at` and changes intent uniqueness to `(job_id, job_version)`, allowing durable future retry dispatches. Phase 12 migration `0006_durable_scheduling` adds nullable `jobs.schedule_at` and the due-job index. Provider credentials are runtime settings and are never stored in job configuration. The migrations seed exactly `USER` and `ADMIN`. Refresh token values are represented only by SHA-256 hashes; API key secrets are represented only by SHA-256 hashes and an indexed public ID.

## Relationships and lifecycle

Users own jobs and API keys. Jobs own attempts, events, and at most one accepted result. Workers own heartbeats and may be referenced by attempts. Audit records are append-only. Deletion/retention policy is an open operational decision; no destructive cascade may silently remove audit history.

## Constraints and indexes

Required uniqueness includes user email, API-key hash or identifier, idempotency principal/key, job/attempt number, and job result/job. Indexes should support user job listing by creation time, state/queue scheduling, attempts by job, events by job/time, workers by heartbeat, and audit time/actor. Additional indexes require measured query evidence.

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
