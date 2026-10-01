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
- Phase 3 persisted durable jobs and lifecycle data but did not execute jobs asynchronously. Phase 4A/4B/4C now provide execution contracts, Kafka transport, and durable dispatch intent; schedulers, Redis, provider adapters, retry execution, frontend, and deployment infrastructure remain deferred.
- The retry API action is deferred until retry execution infrastructure exists; retry policy is persisted as job data only.
- PostgreSQL-specific concurrency verification has not been performed in the current isolated test environment.
- Phase 4A provides provider-independent execution and worker contracts plus an in-process dispatcher for deterministic tests. Scheduler coordination, execution deduplication, retries, dead letters, and production worker deployment remain deferred.
- Phase 4B introduced the Kafka adapter; Phase 4C moved publication behind the
  durable outbox. Kafka broker integration and PostgreSQL concurrency remain
  unverified in this environment.
- A worker runtime entrypoint/deployment is not yet provided; `KafkaWorkerRunner` is the explicit integration boundary for a later worker process. The API does not consume Kafka.
- Phase 4C closes the database job/dispatch-intent gap but does not provide a distributed transaction with Kafka. A crash after Kafka publication and before outbox finalization can publish a duplicate. PostgreSQL `SKIP LOCKED` behavior is not verified in the current environment.
