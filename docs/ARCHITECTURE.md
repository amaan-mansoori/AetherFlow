# Architecture

**Status:** Architecture / Specification Phase; Phase 6 execution retry implemented

## Decision summary

AetherFlow starts as a modular monolith with independently runnable API, scheduler capability, and worker processes. Modules share contracts and a PostgreSQL database but are separated by runtime responsibility where scaling and failure isolation justify it. The scheduler may initially run inside the backend process and must retain an interface that permits later extraction.

## Components

- **Next.js console:** authenticated operator and developer UI; consumes versioned API only.
- **FastAPI API:** authentication, authorization, validation, idempotent submission, query APIs, cancellation, and operational endpoints.
- **Retry dispatcher:** the existing outbox publisher identifies due retry intents; no general-purpose scheduler is introduced.
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

## Phase 4B Kafka dispatch

Kafka is an explicit transport adapter behind `JobDispatcher`, implemented in
`aetherflow.infrastructure.kafka`. It is enabled only with
`AETHERFLOW_KAFKA_ENABLED=true`; the API otherwise retains the deterministic
database-only submission behavior. Kafka publication is performed by the
independent outbox publisher, not by the API request handler.

The outbox publisher creates or receives a producer-capable dispatcher. A
worker runtime creates a producer/consumer dispatcher with
`create_worker_dispatcher()` and passes it to `KafkaWorkerRunner`, which invokes
the existing `Worker`; this keeps Kafka consumption out of the FastAPI
lifecycle and avoids starting an idle consumer in every API replica.

- **Topic:** `AETHERFLOW_KAFKA_TOPIC`, default `aetherflow.jobs`.
- **Key:** the UTF-8 job UUID, preserving per-job partition affinity.
- **Payload:** deterministic UTF-8 JSON with schema
  `aetherflow.job-dispatch.v1`, `schema_version`, `job_id`, `job_version`, and
  timezone-aware `enqueued_at`.
- **Consumer group:** `AETHERFLOW_KAFKA_CONSUMER_GROUP`, default
  `aetherflow-workers`.
- **Producer:** waits for `send_and_wait` with `acks=all`; idempotent producer
  mode is configurable and defaults on. A publish exception is surfaced.
- **Consumer:** disables auto-commit, validates the envelope, and hands only a
  `DispatchMessage` to `Worker` through `KafkaWorkerRunner`. Malformed or
  unsupported messages are rejected without acknowledgement.
- **Acknowledgement:** the worker commits the record offset only after it has
  made a durable worker decision. A worker crash or offset-commit failure can
  cause redelivery; stale versions, terminal state, and CAS protect the durable
  job state.

The API stores the job and immutable dispatch intent in one PostgreSQL
transaction. `OutboxPublisher` claims an unpublished row with a short lease,
publishes outside the database transaction, and marks it published in a
separate short transaction. Kafka publication failure leaves the row
recoverable; PostgreSQL and Kafka are not a distributed transaction.

## Phase 4C transactional outbox

`outbox_dispatches` contains versioned dispatch intents. The initial
submission intent and each execution retry intent use a unique `(job_id,
job_version)` pair. Retry intents carry `available_at`; this keeps future
publication durable without a second scheduler or an in-memory timer. The
`(published_at, created_at)` index supports oldest-unpublished scans.

`OutboxPublisher` uses `SELECT ... FOR UPDATE SKIP LOCKED` where supported,
commits a lease before Kafka I/O, then publishes and finalizes the row in a
new transaction. Lease expiry makes a crashed claim recoverable. A crash after
Kafka success but before finalization may publish a duplicate; existing worker
version/state/CAS protections remain authoritative. SQLite tests validate
portable publication behavior only; PostgreSQL locking semantics remain
unverified.

## Phase 4D/4E/4F reliability runtime

`aetherflow.runtime.outbox_publisher` is an independent process entrypoint.
`OutboxPublisherRuntime` polls bounded batches, continues after individual
recoverable failures, and shuts down by stopping polling before closing the
dispatcher and database engine. Poll interval, batch size, lease duration,
publisher identity, retry limit, and backoff bounds are settings.

Transient publication failures persist a bounded error, category, timestamp,
attempt count, and deterministic next-attempt time. Attempts are capped; a
permanent/invalid record becomes `PERMANENT_FAILURE` and is retained for
diagnosis. Kafka I/O remains outside claim and finalization transactions.

Workers persist an execution owner and lease while running. A restarted worker
that receives a message for an expired execution lease deterministically
recovers the job to `FAILED`, or to `SUCCEEDED` when a durable result already
exists. Active leases are not stolen. This is crash recovery, not exactly-once
execution.

## Phase 5 provider execution boundary

Phase 5 keeps the worker provider-independent while making the execution
boundary operational:

```text
Worker -> JobExecutor -> ProviderExecutor -> ProviderRegistry -> ProviderAdapter
```

`ProviderExecutor` selects a provider from the non-secret job configuration,
falling back to the environment-configured `provider_default`. The registry
validates provider and model support, and adapters return the existing
`ExecutionOutcome` contract, which the boundary validates before persistence.
The deterministic `MockProviderAdapter` is the
local/CI implementation; it does not represent external model quality or
provider availability. No adapter receives database sessions or changes job
state.

The worker wraps execution in the job timeout and maps timeout to a durable
`TIMEOUT` attempt failure. Provider failures are normalized into validation,
authentication, rate-limit, timeout, transient-provider, permanent-provider,
cancellation, and unexpected categories. Provider execution remains outside
database transactions. Execution retry orchestration and external provider
transport remain separate future decisions.

Phase 9 adds one `OpenAICompatibleAdapter` behind this same boundary. It uses
a reusable bounded async HTTP client in the worker process, allowlists
`temperature` and `max_tokens`, and normalizes chat content and usage into
`ExecutionOutcome`. It does not contain retry logic; Phase 6 remains the
single retry authority.

## Phase 6 durable execution retry

Phase 6 distinguishes dispatch publication retry from provider execution
retry. `ExecutionRetryPolicy` centrally classifies failures: rate limits,
timeouts, and transient provider failures are retryable; validation,
authentication, permanent-provider, cancellation, unexpected internal errors,
and legacy execution failures are terminal. The per-job retry policy supplies a
bounded attempt budget and deterministic capped exponential backoff. Jitter is
not applied.

For a retryable failure, the worker atomically updates the failed attempt,
clears the execution lease, transitions `RUNNING -> RETRY_SCHEDULED`, and
creates a future outbox intent. The existing outbox publisher claims that
intent only when `available_at` is due and the job version/state still match.
The worker then processes `RETRY_SCHEDULED -> QUEUED -> RUNNING` through the
existing CAS state machine. Cancellation can transition a scheduled retry to
`CANCEL_REQUESTED`; the publisher may deliver the due intent only to let the
worker complete cancellation, never execution.
At-least-once publication and execution remain in force; this is not an
exactly-once guarantee.

## Data and consistency

The API transaction creates the job, idempotency record, and outbox intent
before publication. Publication failures leave an observable recoverable state.
Job state transitions use compare-and-set predicates and short transactions,
with row locks for claim-sensitive operations.

## Retry dispatch design

The existing outbox publisher scans due retry intents using `available_at`.
There is no general-purpose scheduler, deployment leader, or in-memory sleep
loop. Job version/state matching prevents cancellation and stale retry intents
from being published. Retry budgets are bounded; dead-letter redesign and
operator replay remain deferred.

## Future Kafka event contract

Future lifecycle/event topics may use JSON or another explicitly versioned
serialization with a schema version, message ID, job ID, event time, principal
ID where needed, attempt metadata, and trace headers. The Phase 4B job dispatch
topic is `aetherflow.jobs` and is partitioned by job ID to preserve per-job
ordering; partition count is configuration, not a capacity promise. Workers
share a stable consumer group per environment and process each message at
least once. Retention is longer than the expected operational replay window and
is environment-configured. Broker errors cause backpressure/retry and are
never reported as successful dispatch. Lifecycle consumers must tolerate
duplicates and out-of-order events; PostgreSQL remains authoritative.

## Redis contract

Keys use namespaced, versioned formats such as `aetherflow:v1:ratelimit:user:{id}:{window}` and `aetherflow:v1:cache:job:{id}`. Rate-limit keys expire at the window boundary. Cache entries have short configurable TTLs, are invalidated on job mutation where practical, and are never used to authorize access. Redis unavailability follows the Phase 11 non-critical rate-limit policy: rate limiting fails open, cache reads miss, durable reads continue, and durable mutations never depend on Redis.

## Scaling

API replicas scale on request load; worker replicas scale by Kafka consumer-group partition capacity and queue lag; scheduler instances use PostgreSQL row locking and bounded polling rather than a Redis leader. PostgreSQL remains the bottleneck to measure, not hide. No service split is justified until independent scaling, failure isolation, or ownership requires it.

## Deployment

The production cloud is an open decision until Phase 1 constraints and cost are reviewed. Only one provider will be selected. Kubernetes manifests will be the initial deployment format; Helm is deferred unless repeated environment templating proves its value.

## Phase 10 validation status

The intended production-like path remains:

```text
API -> PostgreSQL -> transactional outbox -> OutboxPublisher -> Kafka
    -> Worker -> ProviderExecutor -> PostgreSQL result/state -> acknowledgement
```

Phase 10 does not change this architecture. Docker's Linux engine was
unavailable during validation, so the PostgreSQL/Kafka runtime path and
Compose E2E are **UNVERIFIED**. Existing SQLite/fake-client tests remain
deterministic component verification only.

## Phase 11 responsibility split

The storage and transport boundaries are explicit:

```text
PostgreSQL = durable source of truth
Kafka      = asynchronous transport
Redis      = ephemeral coordination and API rate limiting
```

Redis is created only in the API application lifecycle when explicitly
enabled. A bounded pooled async client executes one atomic Lua fixed-window
increment with a TTL. The worker and outbox publisher do not receive Redis
configuration because their correctness does not depend on it.

## Phase 12 durable one-shot scheduling

`jobs.schedule_at` is nullable UTC metadata. Immediate submissions and
past-due schedules create the same initial outbox intent as before. A future
schedule remains `ACCEPTED` and has no Kafka-facing intent until due. The
independent scheduler polls a bounded indexed query and, in a short
PostgreSQL transaction, locks one due `ACCEPTED` row with `SKIP LOCKED`,
applies `ACCEPTED -> QUEUED` through the versioned CAS state machine, records
`SCHEDULED_JOB_ACTIVATED`, and inserts the versioned outbox intent.

The scheduler never connects to Kafka or Redis. The outbox publisher remains
the only publication bridge. A crash before commit rolls back activation; a
crash after commit leaves the outbox intent recoverable. Concurrent schedulers
are protected by row locking, CAS, and the unique `(job_id, job_version)`
outbox index. SQLite tests cover deterministic behavior but not PostgreSQL
locking.

Initial scheduling is distinct from execution retry: retry intents remain
`RETRY_SCHEDULED` with `available_at` and continue to be handled by the
existing outbox publisher. Cancellation of a future `ACCEPTED` job wins by
the existing CAS transition, and the scheduler only selects `ACCEPTED` rows.

## Phase 13 administrative control plane

The administrative API is a thin, server-side `ADMIN`-authorized view over
existing PostgreSQL primitives. It does not create a second state machine,
retry system, scheduler, or Kafka publication path. Job inspection uses
bounded indexed queries and stable offset ordering. Detail responses read
durable attempts, lifecycle events, and outbox rows while omitting job input
and configuration.

Administrative cancellation calls the existing job cancellation service, which
performs the authoritative versioned CAS transition. The successful mutation
and its safe audit record are committed in the same transaction. Manual retry
is intentionally not exposed because no existing state transition can express
it without bypassing durable retry policy.
