# Known Limitations

**Status:** Implementation limitations through Phase 15

- External AI calls may execute twice under at-least-once delivery; durable result deduplication cannot undo provider-side work or cost.
- Provider cancellation may be unavailable after a request starts.
- Kafka, Redis, PostgreSQL, and observability add local operational complexity.
- Initial polling is less immediate and less efficient than streaming.
- One tenant does not demonstrate tenant isolation or cross-tenant quotas.
- The mock provider is deterministic and must not be represented as model-quality evidence.
- Cloud deployment, retention, and malformed-output retry policy remain open decisions. Browser session restoration follows the existing rotating HttpOnly refresh-cookie contract.
- No performance numbers are known at this phase.
- Phase 3 persisted durable jobs and lifecycle data but did not execute jobs asynchronously. Later phases added execution contracts, Kafka transport, durable dispatch intent, bounded dispatch retry, worker crash recovery, a provider boundary, a deterministic mock provider, durable scheduling, and the Phase 14 console; cloud deployment remains deferred.
- Phase 6 adds durable execution retry for bounded retryable provider failures;
  there is still no retry API action, operator replay workflow, or provider-call
  resumption after a process crash.
- Phase 7 metrics are process-local and reset on restart. External scraping,
  dashboards, alerting, and durable telemetry storage are not included.
- Phase 8 provides a local Compose deployment foundation only. Docker Compose
  credentials are not production secret management; Kubernetes, cloud
  deployment, backups, broker/database HA, and external smoke verification are
  deferred.
- PostgreSQL-specific concurrency verification has not been performed in the current isolated test environment.
- Phase 4A provides provider-independent execution and worker contracts plus an in-process dispatcher for deterministic tests. Later phases add durable scheduling and retries, but do not provide exactly-once execution, a DLQ/operator replay API, or live production-worker verification.
- Phase 4B introduced the Kafka adapter; Phase 4C moved publication behind the
  durable outbox. Kafka broker integration and PostgreSQL concurrency remain
  unverified in this environment.
- The worker and outbox publisher have independent runtime entrypoints, but
  their real broker/database behavior remains environment-gated.
- Phase 4C closes the database job/dispatch-intent gap but does not provide a distributed transaction with Kafka. A crash after Kafka publication and before outbox finalization can publish a duplicate. PostgreSQL `SKIP LOCKED` behavior is not verified in the current environment.
- Phase 4D/4E provides bounded retry scheduling for dispatch publication. It
  intentionally does not add a DLQ, operator replay API, or scheduler.
- Phase 4F recovers expired `RUNNING` executions to an explicit terminal
  outcome; Phase 6 retries only the resulting durable failure path and does
  not resume an interrupted provider call or claim exactly-once execution.
- Phase 5 implements the provider boundary and deterministic mock provider,
  and Phase 9 includes one OpenAI-compatible adapter, but external provider
  credentials and smoke validation remain environment-dependent. Phase 6 execution
  retry is locally tested with SQLite and deterministic fakes; PostgreSQL row
  locking and Kafka broker behavior remain unverified.
- Phase 10 deterministic checks passed, but Docker's Linux engine was
  unavailable. PostgreSQL/Kafka Compose startup, API-to-result E2E, runtime
  restart recovery, infrastructure concurrency, and shutdown observation are
  therefore **UNVERIFIED**, not successful production validation.
- Phase 11 rate limiting is fixed-window and process-independent only when
  Redis is available. It intentionally fails open during Redis outages, so
  request limits are not enforced during that degraded interval. Real Redis
  startup and cross-process sharing remain **UNVERIFIED** when Docker is
  unavailable.
- Phase 12 scheduling is one-shot only; recurring schedules and cron syntax
  are intentionally out of scope. The scheduler's PostgreSQL row-locking and
  restart behavior are **UNVERIFIED** against a live PostgreSQL/Kafka Compose
  stack when Docker is unavailable. Scheduling does not provide exactly-once
  publication or execution.
- Phase 13 does not expose manual admin retry/requeue because the current
  state machine has no safe transition for it. Execution retry remains
  worker-owned and durable. Admin inspection and cancellation are covered by
  SQLite tests; live PostgreSQL/Kafka behavior remains unverified when Docker
  is unavailable.
- Phase 14's overview uses a bounded recent-job sample because no count or
  aggregate job endpoint exists. `/activity` shows recent job records ordered
  by `updated_at`; the API has no global event feed, worker registry, or
  cross-process service health. Admin detail intentionally omits result bodies.
  Job detail polling is per open detail route and remains polling-based; live
  PostgreSQL/Kafka/Redis Compose verification is unverified when Docker is
  unavailable.
- Phase 15 does not implement email verification, account activation, or
  password recovery; public registration proves neither email ownership nor
  credential recovery. Demo access is explicitly read-only and sample fixtures
  remain `ACCEPTED` and `CANCEL_REQUESTED` without worker dispatch or fabricated
  results. Operators must protect and distribute the shared demo password
  outside the application. Redis-backed auth/API limiting remains optional
  outside Compose and fails open on Redis errors.
- Phase 15 acceptance verification passed against isolated SQLite and fake
  service boundaries. Docker Desktop's Linux engine was unavailable, so
  PostgreSQL migrations on the deployed database, Kafka/Redis service
  integration, real worker processing, and Compose startup remain
  **UNVERIFIED**. Production still requires external HTTPS termination,
  operational secret management, production-specific CORS origins, and
  deployment hardening beyond the local Compose template.
