# Architecture

**Status:** Architecture / Specification Phase; Phase 4A contracts implemented

## Decision summary

AetherFlow starts as a modular monolith with independently runnable API, scheduler capability, and worker processes. Modules share contracts and a PostgreSQL database but are separated by runtime responsibility where scaling and failure isolation justify it. The scheduler may initially run inside the backend process and must retain an interface that permits later extraction.

## Components

- **Next.js console:** authenticated operator and developer UI; consumes versioned API only.
- **FastAPI API:** authentication, authorization, validation, idempotent submission, query APIs, cancellation, and operational endpoints.
- **Scheduler:** identifies due queued/retry-scheduled jobs; initially co-located with API or worker deployment, later extractable.
- **Worker:** Kafka consumer-group process; claims jobs, calls provider abstraction, validates output, persists attempts/results, and emits lifecycle events.
- **PostgreSQL:** authoritative users, jobs, attempts, results, events, workers, audit data, and idempotency records.
- **Kafka:** durable job dispatch and lifecycle event transport; not current-state storage.
- **Redis:** configurable rate limits, short-lived cache, and narrowly justified coordination.
- **Provider adapter:** normalized AI interface with external and mock implementations.
- **Telemetry stack:** OpenTelemetry instrumentation, Prometheus metrics, Grafana dashboards, structured logs.

## Boundaries

Domain services must not import vendor SDK types. API handlers must not implement state-transition rules. Infrastructure adapters own Kafka, Redis, database, and provider details. Shared state changes occur through domain services and transactional repositories.

## Phase 4A execution foundation

Phase 4A introduces broker-neutral contracts in `aetherflow.jobs`:

- `JobExecutor` receives an immutable `ExecutionRequest` and returns a typed
  `ExecutionOutcome`; it has no FastAPI, Kafka, Redis, or provider dependency.
- `JobDispatcher` publishes and receives a versioned `DispatchMessage`.
  `LocalDispatcher` is an in-process development/test adapter only and does not
  provide durable delivery, consumer-group coordination, or distributed
  guarantees.
- `Worker` validates eligibility, claims `ACCEPTED`/`QUEUED` work through the
  existing state machine and CAS service, records attempts/results, and emits
  lifecycle events through those same domain services.

The worker commits the claim and attempt before invoking an executor. Execution
therefore happens outside a database transaction. A later short transaction
records the attempt outcome and result, then applies the final CAS-protected
state transition. Stale dispatch messages are rejected. This is a contract and
local orchestration foundation, not Kafka delivery or exactly-once execution.

## Data and consistency

The API transaction creates the job and idempotency record before publishing dispatch. Publication failures leave an observable recoverable state; a scheduler/outbox-compatible design is reserved for implementation design if direct publication cannot provide the required reliability. Job state transitions use compare-and-set predicates and short transactions, with row locks for claim-sensitive operations.

## Scheduler and retry design

The scheduler scans only due `QUEUED` or `RETRY_SCHEDULED` work using indexed timestamps and claims a bounded batch. A deployment lease prevents duplicate scheduling when more than one scheduler runs. Retry delay is persisted with the job/attempt decision; the scheduler, not a busy worker loop, makes due work eligible. Exponential backoff has a configured cap and randomized jitter. A retry budget and maximum attempts prevent retry storms; poison messages are isolated and dead-lettered.

## Kafka contract

Messages are JSON or another explicitly versioned serialization with a schema version, message ID, job ID, event time, principal ID where needed, attempt metadata, and trace headers. `jobs.submit` is partitioned by job ID to preserve per-job ordering; partition count is configuration, not a capacity promise. Workers share a stable consumer group per environment and process each message at least once. Retention is longer than the expected operational replay window and is environment-configured. Consumer offsets are committed after the durable decision. Broker errors cause backpressure/retry and are never reported as successful dispatch. Lifecycle consumers must tolerate duplicates and out-of-order events; PostgreSQL remains authoritative.

## Redis contract

Keys use namespaced, versioned formats such as `aetherflow:v1:ratelimit:user:{id}:{window}` and `aetherflow:v1:cache:job:{id}`. Rate-limit keys expire at the window boundary. Cache entries have short configurable TTLs, are invalidated on job mutation where practical, and are never used to authorize access. Redis unavailability follows feature policy: rate limiting fails closed for abuse-sensitive submission routes unless an explicitly configured degraded mode is selected; cache reads miss and durable reads continue; durable mutations never depend on Redis.

## Scaling

API replicas scale on request load; worker replicas scale by Kafka consumer-group partition capacity and queue lag; scheduler instances use a lease/leader mechanism if independently deployed. PostgreSQL remains the bottleneck to measure, not hide. No service split is justified until independent scaling, failure isolation, or ownership requires it.

## Deployment

The production cloud is an open decision until Phase 1 constraints and cost are reviewed. Only one provider will be selected. Kubernetes manifests will be the initial deployment format; Helm is deferred unless repeated environment templating proves its value.
