# Known Limitations

This page describes limitations in the current implementation; it is not a
roadmap or a claim of production readiness.

## Execution and delivery

- Kafka delivery is at least once. A publisher crash after Kafka acknowledges
  a message but before PostgreSQL records publication can cause a duplicate.
- Worker leases and state/version checks protect durable state, but a provider
  request can execute more than once if a worker crashes after the provider
  performs work and before the result is durably recorded. There is no
  exactly-once execution or provider-side deduplication guarantee.
- Expired execution leases are recovered to a durable outcome; an interrupted
  provider call is not resumed. Cancellation cannot reliably stop a provider
  call that has already started.
- Execution retry is bounded to selected retryable failures. Backoff is
  capped and deterministic; the accepted retry-policy `jitter` setting is not
  currently applied. There is no operator retry/replay endpoint or outbox
  replay UI.
- Future schedules are one-shot and polling-based. Cancelling scheduled work
  while it remains `ACCEPTED` moves it directly to `CANCELLED`; immediate
  submissions and other jobs use `CANCEL_REQUESTED`. Recurring schedules and
  cron are not supported.
- The scheduler/outbox use PostgreSQL locking for multi-process coordination,
  but SQLite tests do not prove PostgreSQL `SKIP LOCKED` or race behavior.

## Operations and access

- Prometheus-compatible metrics are process-local and reset on restart.
  External scraping, durable metrics, bundled dashboards, alerting, distributed
  tracing, and a worker registry are not included.
- Redis-backed API rate limiting is optional and fails open during Redis
  outages; limits are not enforced during that degraded interval.
- The product does not implement email verification or password recovery.
  Recruiter demo access is an explicitly provisioned, read-only account; its
  shared password must be distributed and protected by the operator.
- The Compose configuration is for local development. Production requires
  independent secret management, TLS termination, backups, high availability,
  capacity planning, and deployment hardening. No cloud deployment is claimed.

## Verification boundaries

- The deterministic test suite uses SQLite and fakes for many service
  boundaries. It does not replace PostgreSQL concurrency, Kafka broker
  rebalancing, cross-process Redis, restart, or high-availability tests.
- A local Compose smoke check in this workspace exercised mock-provider
  success, retry exhaustion, and a due scheduled job through PostgreSQL,
  Kafka, the publisher, scheduler, and worker. This is a limited local
  integration check, not production validation or a concurrency guarantee.
- The OpenAI-compatible adapter is covered with mock HTTP transport; no live
  provider credential or external provider request is part of the verified
  demo.
- No reproducible performance benchmark has been run, so the project makes no
  throughput or latency claim.
