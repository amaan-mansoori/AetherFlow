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
