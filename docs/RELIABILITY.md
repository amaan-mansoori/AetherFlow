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
4A did not claim exactly-once processing, retries, backoff, dead-lettering, or
provider-side cancellation. Dispatch retry and worker crash recovery are
defined in the later sections; execution retry orchestration remains deferred.

## Phase 4B Kafka acknowledgement model

Kafka dispatch uses the `aetherflow.jobs` topic, job UUID keys, the
`aetherflow.job-dispatch.v1` envelope, and the `aetherflow-workers` consumer
group by default. Auto-commit is disabled. The consumer validates a message,
the `KafkaWorkerRunner` invokes the existing worker, and only then is the
offset committed. A malformed or unsupported message is surfaced as a dispatch
failure and is not acknowledged. A worker crash before commit can redeliver the
message. Publication belongs to the independent outbox runtime; consumption
belongs to an independent worker runtime.

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

## Phase 4D/4E publisher runtime and retry policy

The independent publisher runtime polls bounded batches and preserves the
claim-commit-publish-finalize sequence. It stops polling before closing Kafka
and database resources. Individual failures do not terminate the runtime.

Transient dispatch failures use deterministic exponential backoff capped by
configuration. The outbox stores attempt count, failure category, bounded
error text, failure timestamp, and next eligible attempt. Once the configured
attempt limit is reached, the row becomes `PERMANENT_FAILURE`; the original
intent remains auditable and is not silently deleted. Invalid schema/type data
is permanent and is never retried.

## Phase 4F worker recovery

The worker records an execution lease and the dispatch version that started it
before invoking the executor. A duplicate message during an active lease is
ineligible. After lease expiry, a redelivery of that execution's dispatch
recovers a `RUNNING` job to `FAILED`, unless a durable result already exists,
in which case it completes the job as `SUCCEEDED`. A different stale message
cannot trigger recovery for a newer execution. This closes the
committed-running crash window without an in-memory deduplication mechanism.
Cancellation races continue to use the existing state machine and CAS rules.

## Phase 5 provider execution

Provider selection and provider-specific behavior are isolated behind
`ProviderExecutor`, `ProviderRegistry`, and `ProviderAdapter`. The worker
enforces the durable job timeout with `asyncio.wait_for`; a timeout records a
failed attempt with `TIMEOUT`, clears the execution lease, and transitions the
job through the existing CAS service. Provider failures are classified
explicitly and are not automatically retried in Phase 5. Dispatch retry
remains the outbox concern.

## Phase 6 execution retry and failure recovery

Execution retry is distinct from dispatch publication retry. The centralized
`ExecutionRetryPolicy` retries only `RATE_LIMIT`, `TIMEOUT`, and
`TRANSIENT_PROVIDER` failures, subject to the persisted per-job maximum
attempt budget. `VALIDATION`, `AUTHENTICATION`, `PERMANENT_PROVIDER`,
`CANCELLATION`, `UNEXPECTED`, and legacy `EXECUTION` failures are terminal.
Backoff is deterministic, capped exponential, and jitter is not applied.

The Phase 9 OpenAI-compatible adapter maps rate limits, network timeouts, and
5xx responses to these retryable categories. Authentication, malformed
responses, and rejected requests remain terminal. The adapter has no
provider-specific retry loop.

The worker atomically records bounded failure metadata, clears the execution
lease, transitions `RUNNING -> RETRY_SCHEDULED`, and creates a future-dated
outbox intent. The outbox publisher is the retry dispatcher: it claims only
due intents whose job state and version still match. Once published, the
worker advances `RETRY_SCHEDULED -> QUEUED -> RUNNING`. Cancellation wins over
scheduled retry; a due cancellation message is consumed only to complete
`CANCEL_REQUESTED -> CANCELLED`, while stale or duplicate retry messages are
acknowledged as ineligible. Retry exhaustion transitions to `FAILED`. Publication and
execution remain at least once, and provider-side work may still occur more
than once.
