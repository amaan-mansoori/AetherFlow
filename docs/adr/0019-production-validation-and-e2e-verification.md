# ADR-0019: Production Validation and E2E Verification

## Status

Accepted — Phase 10 validation record.

## Scope

Phase 10 validates the existing execution path without changing the job state
machine, retry authority, provider boundary, or at-least-once delivery model:

```text
API -> PostgreSQL -> outbox -> publisher -> Kafka -> worker
    -> ProviderExecutor -> PostgreSQL result/state -> acknowledgement
```

## Evidence policy

SQLite and injected Kafka/HTTP clients are used only for deterministic
component tests. They cannot establish PostgreSQL locking, Kafka broker
delivery, consumer-group offset behavior, or Compose process recovery.
Infrastructure results are reported as **VERIFIED** only after the actual
Compose services are started and exercised. Missing infrastructure or
credentials is reported as **UNVERIFIED**.

## Validation result

The complete deterministic suite passed: 115 tests. Ruff formatting/checks,
mypy, diff checks, and the isolated Alembic upgrade -> downgrade -> upgrade
lifecycle passed. The lifecycle check found and fixed a missing retry-index
recreation in the existing `0005_execution_retry` downgrade.
Docker CLI inspection showed that the Docker Linux engine was unavailable, so
Compose startup, PostgreSQL/Kafka integration, API-to-result E2E, runtime
restart/concurrency/shutdown checks, and real-provider smoke testing were
**UNVERIFIED**. No provider credential was used.

No architecture change was required. No integration test was made dependent
on Docker, and no exactly-once execution guarantee is claimed.
