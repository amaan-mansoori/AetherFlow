# Known Limitations

**Status:** Architecture / Specification Phase

- External AI calls may execute twice under at-least-once delivery; durable result deduplication cannot undo provider-side work or cost.
- Provider cancellation may be unavailable after a request starts.
- Kafka, Redis, PostgreSQL, and observability add local operational complexity.
- Initial polling is less immediate and less efficient than streaming.
- One tenant does not demonstrate tenant isolation or cross-tenant quotas.
- The mock provider is deterministic and must not be represented as model-quality evidence.
- Cloud, token refresh, retention, and malformed-output retry policy remain open decisions.
- No performance numbers are known at this phase.
- Phase 3 persisted durable jobs and lifecycle data but did not execute jobs asynchronously. Phase 4A/4B/4C/4D/4E/4F and Phase 5 now provide execution contracts, Kafka transport, durable dispatch intent, bounded dispatch retry, worker crash recovery, a provider boundary, and a deterministic mock provider; schedulers, Redis, external providers, frontend, and deployment infrastructure remain deferred.
- Phase 6 adds durable execution retry for bounded retryable provider failures;
  there is still no retry API action, operator replay workflow, or provider-call
  resumption after a process crash.
- PostgreSQL-specific concurrency verification has not been performed in the current isolated test environment.
- Phase 4A provides provider-independent execution and worker contracts plus an in-process dispatcher for deterministic tests. Scheduler coordination, execution deduplication, retries, dead letters, and production worker deployment remain deferred.
- Phase 4B introduced the Kafka adapter; Phase 4C moved publication behind the
  durable outbox. Kafka broker integration and PostgreSQL concurrency remain
  unverified in this environment.
- A worker runtime entrypoint/deployment is not yet provided; `KafkaWorkerRunner` is the explicit integration boundary for a later worker process. The API does not consume Kafka.
- Phase 4C closes the database job/dispatch-intent gap but does not provide a distributed transaction with Kafka. A crash after Kafka publication and before outbox finalization can publish a duplicate. PostgreSQL `SKIP LOCKED` behavior is not verified in the current environment.
- Phase 4D/4E provides bounded retry scheduling for dispatch publication. It
  intentionally does not add a DLQ, operator replay API, or scheduler.
- Phase 4F recovers expired `RUNNING` executions to an explicit terminal
  outcome; Phase 6 retries only the resulting durable failure path and does
  not resume an interrupted provider call or claim exactly-once execution.
- Phase 5 implements the provider boundary and deterministic mock provider,
  but no external provider adapter is included or verified. Phase 6 execution
  retry is locally tested with SQLite and deterministic fakes; PostgreSQL row
  locking and Kafka broker behavior remain unverified.
