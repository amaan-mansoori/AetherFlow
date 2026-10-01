# Phase 7 — Observability and Operations Foundation

## Problem and scope

The application had structured logs and health checks but no consistent
application metrics. This phase adds only an in-process metrics abstraction,
Prometheus exposition, HTTP/job/worker/outbox/retry/provider counters and
durations, and clearer liveness/readiness semantics.

## Implementation

`aetherflow.observability.metrics` provides bounded-label counters and
histogram observations. `GET /metrics` returns plain Prometheus exposition.
HTTP middleware records normalized routes and status classes. Job services,
workers, the outbox publisher, and provider executor record lifecycle outcomes.

## Security and cardinality

Metric labels never contain job IDs, request IDs, user IDs, raw paths, error
messages, credentials, or payloads. Provider labels come from the configured
registry. Logs retain the existing request-ID JSON formatter and no sensitive
headers or tokens are added.

## Verification and limitations

Local tests verify endpoint format, normalized routes, status classes, and
cardinality boundaries. Ruff, mypy, and the full backend suite are the
verification targets. External Prometheus scraping, PostgreSQL concurrency,
and Kafka integration remain infrastructure-dependent and are not claimed as
verified. Metrics reset when the process restarts; durable aggregation and
alerting are deferred.
