# Observability

**Status:** Architecture / Specification Phase

The implemented application currently provides structured logs,
Prometheus-compatible process-local metrics, request IDs, and API
liveness/readiness. The tracing pipeline, external metrics storage, dashboards,
and alerts described below are target capabilities, not bundled services.

## Logs

Emit structured logs with timestamp, level, service/process, environment, request ID, correlation ID, job ID, attempt ID, worker ID, event, duration, and classified error. Redact secrets and sensitive payloads.

## Traces

OpenTelemetry spans cover HTTP handling, database operations where useful, Kafka publish/consume, job processing, provider calls, and result persistence. Propagate trace context through Kafka headers. Sampling and export endpoints are environment configuration.

## Metrics

Instrument real counters/histograms/gauges for request count/errors/latency, submissions, success/failure/retry counts, queue depth/age, processing duration, worker count/utilization, provider latency/errors/rate limits, and dependency health. Avoid unbounded labels such as raw user IDs or job IDs.

## Dashboards and alerts

Grafana dashboards answer: Is work arriving? Is it progressing? Is it failing or retrying? Are workers saturated? Is a dependency unhealthy? Are provider limits causing impact? Alerts are based on configured thresholds and documented as operational starting points, not service guarantees.
