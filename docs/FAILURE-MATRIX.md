# Failure Matrix

**Status:** Architecture / Specification Phase

| Failure | Classification | Expected behavior |
|---|---|---|
| Invalid input/model/auth | Non-retryable | Reject request; no job execution |
| Provider timeout/network error | Retryable | Record attempt; bounded backoff; retry or dead-letter |
| Provider 429/5xx | Retryable | Honor provider hints when safe; bounded retry budget |
| Malformed AI output | Policy decision | Record validation failure; retry only under explicit configured policy |
| Duplicate submission | Not a failure | Return original job for same fingerprint |
| Idempotency payload mismatch | Conflict | Reject with stable error |
| Duplicate Kafka delivery | Expected | CAS claim and unique result/attempt safeguards |
| Worker crash | Expected | Uncommitted message is redelivered; running lease/recovery policy handles stale work |
| Kafka unavailable | Dependency failure | Submission is not falsely acknowledged as dispatched; recovery path is observable |
| Redis unavailable | Degraded dependency | Apply documented fail-open/fail-closed policy by feature; never lose durable state |
| Database unavailable | Critical dependency | Return dependency error; do not acknowledge durable mutation |
| Retry exhaustion | Terminal | Mark `DEAD_LETTERED`, retain attempts/events, expose operator action |
| Cancellation before run | Valid request | Prevent execution and mark `CANCELLED` |
| Cancellation during provider call | Best effort | Record request; prevent follow-up work; final state reflects provider limitation |
| Unauthorized action | Security failure | Return `FORBIDDEN`/not-found policy without leaking existence |

