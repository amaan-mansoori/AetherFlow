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

