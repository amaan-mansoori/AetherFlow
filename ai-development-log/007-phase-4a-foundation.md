# Phase 4A — Asynchronous Execution Foundation

## Objective

Establish provider- and broker-independent execution contracts and a
deterministic local worker/dispatcher foundation without implementing Kafka,
Redis, providers, retries, or distributed deployment.

## Design decisions

- `JobExecutor` uses immutable typed requests and outcomes.
- `JobDispatcher` carries job identity and the expected durable version.
- `LocalDispatcher` is explicitly test/development-only.
- `Worker` reuses the Phase 3 state machine, CAS transitions, attempt/result
  services, and lifecycle events.
- Claim and persistence transactions are short; execution occurs between them.
- Stale dispatch versions are rejected rather than bypassing CAS.
- No database migration was required because existing job, attempt, result, and
  event tables are sufficient.

## Files changed

- `backend/src/aetherflow/jobs/execution.py`
- `backend/src/aetherflow/jobs/dispatch.py`
- `backend/src/aetherflow/jobs/worker.py`
- `backend/tests/test_phase4a.py`
- related architecture, reliability, traceability, and limitations docs

## Verification

- Focused Phase 4A tests: 7 passed.
- Full suite, Ruff, and mypy are run as part of the Phase 4A completion check.
- No PostgreSQL behavior is claimed as verified.

## Limitations and deferred work

This phase does not provide durable broker delivery, Kafka consumer groups,
exactly-once execution, execution deduplication, retries/backoff, dead-letter
handling, scheduling, provider integration, Redis coordination, or production
worker deployment. These remain Phase 4B and later work.
