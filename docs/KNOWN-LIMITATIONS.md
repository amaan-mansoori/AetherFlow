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
- Phase 3 persists durable jobs and lifecycle data but does not execute jobs asynchronously. Workers, schedulers, Kafka dispatch, Redis, provider adapters, retry execution, distributed at-least-once processing, frontend, and deployment infrastructure are Phase 4 or later.
- The retry API action is deferred until retry execution infrastructure exists; retry policy is persisted as job data only.
- PostgreSQL-specific concurrency verification has not been performed in the current isolated test environment.
- Phase 4A provides provider-independent execution and worker contracts plus an in-process dispatcher for deterministic tests. Kafka, durable dispatch recovery, scheduler coordination, execution deduplication, retries, dead letters, and production workers remain deferred.
