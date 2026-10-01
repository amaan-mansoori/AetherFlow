# Phase 4B — Kafka-Backed Asynchronous Dispatch

## Objective

Add Kafka as the asynchronous transport behind the Phase 4A
`JobDispatcher` boundary without redesigning the durable job domain or
claiming exactly-once execution.

## Starting checkpoint

`a3284a2` — `feat: establish AetherFlow Phase 4A asynchronous execution foundation`.

## Reused architecture

The implementation reuses `DispatchMessage`, `JobDispatcher`, `Worker`,
Phase 3 job state/CAS transitions, durable attempts/results/events, and the
existing idempotent submission path. Kafka code is isolated under
`infrastructure/kafka.py`.

## Kafka decisions

- Topic: `aetherflow.jobs`.
- Key: UTF-8 job UUID for per-job partition affinity.
- Envelope: deterministic JSON `aetherflow.job-dispatch.v1`.
- Group: `aetherflow-workers`.
- Producer: `send_and_wait`, `acks=all`, idempotence enabled by default.
- Consumer: auto-commit disabled; explicit offset commit after a durable
  worker decision.
- Duplicate delivery is expected and protected by existing state/version/CAS
  rules.

## Implementation and tests

Added typed Kafka settings, the async producer/consumer adapter, API dispatch
when Kafka is explicitly enabled, a `KafkaWorkerRunner` consumer-to-worker
boundary, explicit failure propagation, envelope validation, and transport
tests with fake clients. The API creates only a producer; a later worker
runtime creates the consumer dispatcher. Tests do not require Kafka.

## Verification and limitations

The final verification commands and results are recorded in the completion
report. No Kafka broker or PostgreSQL instance is assumed available. The
PostgreSQL/Kafka publication boundary is not atomic; an outbox/recovery
mechanism remains deferred.

## Deferred work

Redis, scheduler, retries/backoff, dead letters, AI providers, production
consumer deployment, broker integration tests, outbox/recovery, observability,
Kubernetes, frontend, and cloud deployment remain future work.
