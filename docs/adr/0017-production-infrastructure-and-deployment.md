# ADR-0017: Production Infrastructure and Deployment Foundation

## Status

Accepted — Phase 8.

## Decision

AetherFlow runs as three application processes: the FastAPI API, a Kafka
worker, and an independent transactional-outbox publisher. PostgreSQL stores
jobs, attempts, lifecycle events, results, and outbox intent. Kafka transports
published dispatch messages. The API never publishes directly to Kafka.

The application is packaged as a non-root Python container. Docker Compose
provides PostgreSQL, a single-node KRaft Kafka broker, a one-shot migration
service, and the three application processes. Migrations are an explicit
deployment step and are not run from API replicas.

The API liveness endpoint remains dependency-free. API readiness checks
PostgreSQL. Kafka-dependent worker and publisher processes fail clearly during
startup when the broker is unavailable; Kafka availability is not allowed to
make API liveness fail.

## Consequences

Separate processes preserve failure isolation and allow the API, worker, and
publisher to be scaled or restarted independently later. Compose credentials
are supplied through environment substitution and are local-development
values only. The Compose stack is not a cloud deployment or a production
secret-management system. PostgreSQL and Kafka integration require an
available Docker daemon and are not verified when Docker is unavailable.

SQLAlchemy uses bounded PostgreSQL pools with pre-ping and recycling. Kafka
uses explicit producer acknowledgements/idempotence, a configured consumer
group, and disabled auto-commit. Existing at-least-once delivery and execution
semantics are unchanged.
