# Reliability

**Status:** Architecture / Specification Phase

Reliability is based on durable state, explicit transitions, at-least-once processing, bounded retries, backpressure, health probes, and observable degradation.

## Job state machine

Valid transitions:

```text
ACCEPTED -> QUEUED
ACCEPTED -> CANCEL_REQUESTED
QUEUED -> RUNNING
QUEUED -> CANCEL_REQUESTED
QUEUED -> RETRY_SCHEDULED
QUEUED -> DEAD_LETTERED
RUNNING -> SUCCEEDED
RUNNING -> FAILED
RUNNING -> RETRY_SCHEDULED
RUNNING -> CANCEL_REQUESTED
RETRY_SCHEDULED -> QUEUED
RETRY_SCHEDULED -> DEAD_LETTERED
CANCEL_REQUESTED -> CANCELLED
CANCEL_REQUESTED -> SUCCEEDED
CANCEL_REQUESTED -> FAILED
```

`CANCEL_REQUESTED -> SUCCEEDED` or `FAILED` is allowed when an in-flight provider call cannot be interrupted; the terminal result records that cancellation was not effective. Terminal states are `SUCCEEDED`, `FAILED`, `CANCELLED`, and `DEAD_LETTERED`. All transitions not listed above are invalid, including terminal-state mutation and arbitrary state assignment by clients.

## Invariants

- A visible job has one authoritative state.
- Only valid transitions are accepted.
- Every execution attempt is recorded.
- A job has at most one accepted durable result.
- Duplicate messages do not bypass terminal-state or attempt protections.
- Retry attempts are bounded and eventually terminal.
- Cancellation requests are durable and do not falsely claim provider cancellation.
- Dependencies failing produce explicit errors or recoverable backlog, not silent success.

Database transactions are short and state changes are compare-and-set guarded. Kafka consumer offsets are committed only after the worker has made the relevant durable decision. Poison messages are isolated and observable.

## Phase 4A failure and delivery model

The Phase 4A worker distinguishes validation, execution, cancellation, and
unexpected executor failures. Dispatcher failures are surfaced as
`DispatchFailure`; they are not converted into successful submission. The local
dispatcher is only a deterministic test adapter.

Submission idempotency remains a durable database guarantee. It is distinct from
future at-least-once message delivery and from execution deduplication. Phase
4A does not claim exactly-once processing, retries, backoff, dead-lettering, or
provider-side cancellation. Those require later broker, scheduler, and provider
work.

## Phase 4B Kafka acknowledgement model

Kafka dispatch uses the `aetherflow.jobs` topic, job UUID keys, the
`aetherflow.job-dispatch.v1` envelope, and the `aetherflow-workers` consumer
group by default. Auto-commit is disabled. The consumer validates a message,
the `KafkaWorkerRunner` invokes the existing worker, and only then is the
offset committed. A malformed or unsupported message is surfaced as a dispatch
failure and is not acknowledged. A worker crash before commit can redeliver the
message. The API owns a producer-only dispatcher; consumption belongs to an
independent worker runtime.

The producer waits for Kafka acknowledgement with `acks=all` and producer
idempotence enabled by default. This is producer delivery behavior, not an
exactly-once execution guarantee. The API database commit records the outbox
intent before Kafka is attempted; Kafka publication remains a separate
operation with no distributed transaction.

## Phase 4C transactional outbox

Job insertion, idempotency persistence, lifecycle acceptance, and the
`outbox_dispatches` dispatch intent commit atomically. The API does not publish
Kafka and does not hold its database transaction open while waiting for Kafka.

An independent publisher leases unpublished records, publishes outside a
database transaction, and marks the record published only after Kafka confirms
publication. Failures clear the lease and retain attempt/error metadata for
recovery. A publisher crash after Kafka publication and before the marker
commit can cause duplicate publication; this is at-least-once dispatch, not
exactly-once delivery or execution.
