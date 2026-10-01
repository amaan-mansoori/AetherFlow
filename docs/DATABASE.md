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
| jobs | Durable work state | id, user_id, type, model, normalized input/config, priority, timeout, retry policy, state, version, timestamps |
| job_attempts | Execution history | job_id, attempt number unique pair, worker_id, provider/model, timestamps, error class, retry decision, usage, trace ID |
| job_results | Validated output | job_id unique, schema version, output, usage, created_at |
| job_events | Append-only lifecycle history | job_id, event type, prior/next state, actor, payload, timestamp |
| workers | Worker registry | id, process version, status, capabilities, last heartbeat |
| worker_heartbeats | Liveness history | worker_id, observed_at, load metadata |
| audit_logs | Security/admin actions | actor, action, target, outcome, redacted metadata, timestamp |
| idempotency_records | Submission deduplication | principal_id + key unique, fingerprint, job_id, response status, timestamps |

Phase 2 creates `users`, `roles`, `user_roles`, `refresh_sessions`, `api_keys`, and `audit_logs`. Phase 3 adds `jobs`, `idempotency_records`, `job_attempts`, `job_results`, and `job_events`. The migrations seed exactly `USER` and `ADMIN`. Refresh token values are represented only by SHA-256 hashes; API key secrets are represented only by SHA-256 hashes and an indexed public ID.

## Relationships and lifecycle

Users own jobs and API keys. Jobs own attempts, events, and at most one accepted result. Workers own heartbeats and may be referenced by attempts. Audit records are append-only. Deletion/retention policy is an open operational decision; no destructive cascade may silently remove audit history.

## Constraints and indexes

Required uniqueness includes user email, API-key hash or identifier, idempotency principal/key, job/attempt number, and job result/job. Indexes should support user job listing by creation time, state/queue scheduling, attempts by job, events by job/time, workers by heartbeat, and audit time/actor. Additional indexes require measured query evidence.

Identity-specific indexes are email, role name, refresh token hash, refresh family and expiry, API-key public ID and active-user lookup, and audit event/actor/request/time. No plaintext credential is persisted.

## Concurrency

State transitions use `UPDATE ... WHERE id = ? AND state = expected AND version = expected`, incrementing version and checking affected rows. Claim operations may use a short row lock/skip-locked query. Idempotency insertion relies on the unique constraint; a conflict reloads and compares the fingerprint. Attempt insertion requires `RUNNING`; result insertion is unique by job and occurs only from `RUNNING` or `CANCEL_REQUESTED`. Worker claims, retry scheduling, and dispatch are not yet implemented.

## Migration policy

All schema changes are versioned migrations. Application startup must not silently mutate schema. Migration execution and rollback limitations are documented with deployment procedures.

Phase 2 migration `0001_identity_access` upgrades a clean database with identity tables and role seed data and downgrades by removing that identity schema. Production migration execution remains an explicit deployment step.
