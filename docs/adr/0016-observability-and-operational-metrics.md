# ADR-0016: Application Observability and Operational Metrics

## Status

Accepted — Phase 7.

## Decision

AetherFlow exposes lightweight, application-side Prometheus text metrics through
`GET /metrics`. A small in-process registry keeps domain code independent of a
metrics vendor or server. Metrics use only bounded labels: HTTP method, route
template, status class, job type, state, failure category, and configured
provider name. Job IDs, request IDs, user data, exception text, credentials,
and raw paths are never metric labels.

The liveness endpoint remains dependency-free at `GET /health/live`. Readiness
at `GET /health/ready` checks the database with a short query and returns 503
when it is unavailable. Kafka is not required for API liveness.

## Consequences

Metrics are cheap local counters and observations with no network or database
work on the request path. They reset on process restart and are therefore not
a replacement for a metrics server or durable time-series store. Provider
labels are limited to names selected by the provider registry/configuration.
Structured logs retain request correlation and may contain operational IDs,
but credentials and sensitive payloads remain excluded.
